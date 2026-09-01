import { useState, useRef, useEffect, useCallback } from 'react'

const DEBUG = typeof localStorage !== 'undefined' && localStorage.getItem('debug') === 'true'
const log = DEBUG ? console.log.bind(console) : () => {}

// FOLLOWUPS appears as a trailing block. The mandated form is a JSON array:
//   FOLLOWUPS:["q1","q2","q3"]
// but the model intermittently emits a numbered/bulleted list instead. Parse
// both forms, and ALWAYS strip the block from the stored message — even when no
// suggestions are extracted — so a malformed FOLLOWUPS never leaks into history.
// (Retained malformed blocks poisoned follow-ups on the 2nd+ turn.)
const FOLLOWUPS_MARKER = /\n?\s*FOLLOWUPS:/gi

// How long to hold the socket open post-`done` for the out-of-band verdict.
// Sized for the 14B judge on the RTX 5060 Ti (~10–20s) with headroom, and to
// outlast the proxy's own VERIFIER_TIMEOUT (20s) — a shorter window silently
// drops late verdicts, which makes the Tier 2 judge upgrade look broken.
// Was 9000 (fit the 7B's 6.5s median).
const VERDICT_WINDOW_MS = 25000

// Chat history persistence (browser localStorage).
//
// NOT per-session, despite what this comment and the UI both used to claim:
// localStorage has no session scope, so a transcript survives reload, tab close and
// browser restart until it is explicitly cleared. That is deliberate — you can close
// the tab mid-conversation and pick it up later — but it means the ONLY way to start
// fresh is the header's "New chat" button (clearChat below). Without a visible
// control, every visit silently resumed the previous conversation.
//
// Scope is per-origin/profile/device: nothing is shared between visitors, between
// your phone and your laptop, or with the server. All access is try/catch'd, so in
// private mode or with storage disabled every operation no-ops and the chat works
// exactly as before — just without persistence.
const STORAGE_KEY = 'portfolio_chat_messages'

function loadMessages() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) return []
    const parsed = JSON.parse(stored)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

// The model sometimes reproduces the system prompt's own heading before emitting
// the block — "…privacy red line.\n\n**Mandatory OUTPUT…FOLLOWUPS:[…]". Stripping
// from FOLLOWUPS: onward leaves that heading behind, so the visible answer ends
// with a dangling "**Mandatory" and reads as if it were cut off mid-sentence.
// (Reported 2026-09-01 as a truncated answer; it was not truncation — the reply was
// 838 tokens against a 2048 cap.) It is also a small prompt leak: internal
// instruction text reaching a visitor.
//
// Deliberately conservative. A trailing line is dropped ONLY if it lacks terminal
// punctuation AND is either pure markdown decoration or carries scaffold wording.
// A real closing sentence ends in punctuation and is never touched.
const SCAFFOLD_WORDS = /\b(mandatory|append this|nothing after|follow[-\s]?ups?)\b/i
function stripTrailingScaffold(text) {
  const lines = text.replace(/\s+$/, '').split('\n')
  const last = (lines[lines.length - 1] || '').trim()
  if (!last) return text.replace(/\s+$/, '')
  const looksFinished = /[.!?:;)\]`"'\u2019\u201d]$/.test(last)
  const isDecoration = /^[*_#>\-\s]+$/.test(last)
  if (!looksFinished && (isDecoration || SCAFFOLD_WORDS.test(last))) {
    lines.pop()
    return lines.join('\n').replace(/\s+$/, '')
  }
  return text.replace(/\s+$/, '')
}

function parseFollowups(content) {
  const marks = [...content.matchAll(FOLLOWUPS_MARKER)]
  if (marks.length === 0) return { content: stripTrailingScaffold(content), suggestions: [] }

  const mark = marks[marks.length - 1]   // last occurrence = the trailing block
  const clean = stripTrailingScaffold(content.slice(0, mark.index))
  const block = content.slice(mark.index + mark[0].length).trim()

  let suggestions = []
  // Preferred: JSON array
  const jsonMatch = block.match(/\[[\s\S]*?\]/)
  if (jsonMatch) {
    try {
      const parsed = JSON.parse(jsonMatch[0])
      if (Array.isArray(parsed)) suggestions = parsed.filter(s => typeof s === 'string' && s.trim())
    } catch { /* fall through to list parsing */ }
  }
  // Fallback: numbered / bulleted / line-separated questions
  if (suggestions.length === 0) {
    suggestions = block
      .split('\n')
      .map(l => l.replace(/^[\s\-*\d.)\]]+/, '').replace(/^["']|["']$/g, '').trim())
      .filter(l => l.length > 3)
  }

  return { content: clean, suggestions: suggestions.slice(0, 3) }
}

export function useChat() {
  const [messages, setMessages] = useState(loadMessages)
  const [status, setStatus] = useState('idle') // 'idle' | 'searching' | 'generating'
  const [suggestions, setSuggestions] = useState([])
  const [error, setError] = useState(null)   // null | 'connection_lost' | 'server_error'
  const wsRef = useRef(null)
  const lastPayloadRef = useRef(null)

  const openConnection = useCallback((allMessages) => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/chat`
    // Close any socket left over from the previous turn before opening a new one.
    // A lingering verdict-window socket counts against the per-IP connection limit,
    // so leaking it made the server 429 the next turn's handshake.
    const stale = wsRef.current
    if (stale && stale.readyState !== WebSocket.CLOSING && stale.readyState !== WebSocket.CLOSED) {
      try { stale.close(1000, 'superseded') } catch { /* noop */ }
    }

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    let assistantText = ''
    let pendingSources = []
    let settled = false
    let verdictTimer = null
    const settle = () => { settled = true }

    ws.onopen = () => {
      // Send raw assistant text (WITH its FOLLOWUPS block) as history. The model
      // relies on seeing its own prior FOLLOWUPS to keep emitting them on later
      // turns; sending the display-cleaned text made it drop chips after turn 1.
      // Strip UI-only fields so the model sees clean role/content.
      const history = allMessages.map(m =>
        m.role === 'assistant' && m.raw
          ? { role: 'assistant', content: m.raw }
          : { role: m.role, content: m.content }
      )
      ws.send(JSON.stringify({
        type: 'chat',
        payload: {
          messages: history,
          // The proxy PINS the model server-side (MODEL_ID) and ignores whatever
          // arrives here. This field is kept only for wire-format compatibility.
          // It used to be a real model id, and when the T5810 renamed that model
          // the whole site returned blank answers while /health stayed green
          // (2026-08-29). A client must never choose the backend model.
          model: 'server-pinned',
          max_tokens: 2048
        }
      }))
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'sources') {
          pendingSources = data.data || []
        } else if (data.type === 'chunk') {
          const delta = data.data?.choices?.[0]?.delta?.content
          if (!delta) return
          setStatus('generating')
          assistantText += delta
          setMessages(prev => {
            const next = [...prev]
            if (next[next.length - 1]?.role === 'assistant') {
              next[next.length - 1] = { ...next[next.length - 1], content: assistantText }
            } else {
              next.push({ role: 'assistant', content: assistantText, sources: pendingSources })
            }
            return next
          })
        } else if (data.type === 'done') {
          settle()
          const { content: clean, suggestions: sugs } = parseFollowups(assistantText)
          // Stamp the message with its request_id so a later out-of-band verdict can
          // be matched to THIS message, not just "the last one" (multi-turn safe).
          // content = cleaned (for display); raw = full text with FOLLOWUPS (sent back
          // as history to keep the model emitting chips on later turns).
          setMessages(prev => {
            const next = [...prev]
            const last = next[next.length - 1]
            if (last?.role === 'assistant') {
              next[next.length - 1] = {
                ...last,
                content: clean !== assistantText ? clean : last.content,
                raw: assistantText,
                sources: pendingSources,
                requestId: data.request_id,
                // metadata-only per-message telemetry (durations + token count)
                metrics: data.timing ? { ...data.timing, completion: data.tokens?.completion } : null,
              }
            }
            return next
          })
          setSuggestions(sugs)
          setStatus('idle')
          // The faithfulness verifier runs AFTER the answer. Keep the socket open
          // briefly to receive a {type:"verdict"}; close on verdict or timeout.
          // Non-blocking — the answer is already complete and usable.
          //
          // Only when the server says a verdict is actually coming. Canned paths
          // (guardrail, meta, off-topic, not-documented) and low-relevance answers
          // never run the verifier, and holding the socket open for them made the
          // per-IP limiter reject the user's own next turn as "Connection lost".
          if (data.verify === false) {
            try { ws.close(1000, 'no_verdict_expected') } catch { /* noop */ }
          } else {
            verdictTimer = setTimeout(() => { try { ws.close() } catch { /* noop */ } }, VERDICT_WINDOW_MS)
          }
        } else if (data.type === 'verdict') {
          if (data.flagged && data.request_id) {
            setMessages(prev => prev.map(m =>
              m.requestId === data.request_id
                ? { ...m, flagged: true, faithfulness: data.faithfulness }
                : m
            ))
          }
          clearTimeout(verdictTimer)
          try { ws.close() } catch { /* noop */ }
        } else if (data.type === 'error') {
          settle()
          const msg = data.message || ''
          setError(msg.toLowerCase().includes('too long') ? 'prompt_too_long' : 'server_error')
          setStatus('idle')
          ws.close()
        }
      } catch (e) { log('parse error', e) }
    }

    ws.onerror = () => {
      log('WebSocket error')
      if (!settled) { settle(); setError('connection_lost'); setStatus('idle') }
    }

    ws.onclose = (ev) => {
      if (verdictTimer) { clearTimeout(verdictTimer); verdictTimer = null }
      if (!settled) {
        settle()
        if (ev.code === 1006) setError('connection_lost')
        setStatus('idle')
      }
    }
  }, [])

  const sendMessage = useCallback((content) => {
    setError(null)
    setSuggestions([])
    setStatus('searching')
    const userMessage = { role: 'user', content }
    const allMessages = [...messages, userMessage]
    lastPayloadRef.current = allMessages
    setMessages(allMessages)
    openConnection(allMessages)
  }, [messages, openConnection])

  const retry = useCallback(() => {
    if (!lastPayloadRef.current) return
    setError(null)
    setStatus('searching')
    openConnection(lastPayloadRef.current)
  }, [openConnection])

  // Persist history on every change. Quota/private-mode failures no-op (logged at
  // debug level) — the chat keeps working for the session, just without persistence.
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
    } catch (e) {
      log('localStorage write failed; history not persisted this session', e)
    }
  }, [messages])

  // "New chat": wipe the transcript and start clean. Safe to press at any time,
  // including mid-stream — the socket is closed first so a in-flight answer can't
  // stream into the cleared transcript, and so the connection slot is released
  // rather than held for the rest of the verdict window.
  const clearChat = useCallback(() => {
    const ws = wsRef.current
    if (ws && ws.readyState !== WebSocket.CLOSING && ws.readyState !== WebSocket.CLOSED) {
      // 1000 = deliberate; onclose treats only 1006 as an error, so no false
      // 'connection_lost' banner appears after clearing.
      try { ws.close(1000, 'new_chat') } catch (e) { log('error closing WebSocket', e) }
    }
    wsRef.current = null
    lastPayloadRef.current = null   // nothing to Retry into — the transcript is gone
    setMessages([])
    setSuggestions([])
    setError(null)
    setStatus('idle')
    try { localStorage.removeItem(STORAGE_KEY) } catch { /* storage unavailable */ }
  }, [])

  const stopGeneration = useCallback(() => {
    // CONNECTING counts too — the user can stop during 'searching', before the
    // socket finishes opening. Close code 1000 marks it as a deliberate stop
    // (onclose treats only 1006 as an error, so no false 'connection_lost').
    const ws = wsRef.current
    if (ws && ws.readyState !== WebSocket.CLOSING && ws.readyState !== WebSocket.CLOSED) {
      try {
        ws.close(1000, 'user_stopped')
      } catch (e) {
        log('error closing WebSocket', e)
      }
    }
    setStatus('idle')
  }, [])

  // Mobile Safari: detect WS drop when tab re-foregrounds
  useEffect(() => {
    const onVisibility = () => {
      if (
        document.visibilityState === 'visible' &&
        wsRef.current?.readyState === WebSocket.CLOSED &&
        status !== 'idle'
      ) {
        setError('connection_lost')
        setStatus('idle')
      }
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  }, [status])

  return { messages, status, suggestions, error, sendMessage, retry, clearChat, stopGeneration }
}
