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

function parseFollowups(content) {
  const marks = [...content.matchAll(FOLLOWUPS_MARKER)]
  if (marks.length === 0) return { content, suggestions: [] }

  const mark = marks[marks.length - 1]   // last occurrence = the trailing block
  const clean = content.slice(0, mark.index).trimEnd()
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
  const [messages, setMessages] = useState([])
  const [status, setStatus] = useState('idle') // 'idle' | 'searching' | 'generating'
  const [suggestions, setSuggestions] = useState([])
  const [error, setError] = useState(null)   // null | 'connection_lost' | 'server_error'
  const wsRef = useRef(null)
  const lastPayloadRef = useRef(null)

  const openConnection = useCallback((allMessages) => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/chat`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    let assistantText = ''
    let settled = false
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
          model: 'qwen2.5-coder-14b-pscode',
          max_tokens: 2048
        }
      }))
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'chunk') {
          const delta = data.data?.choices?.[0]?.delta?.content
          if (!delta) return
          setStatus('generating')
          assistantText += delta
          setMessages(prev => {
            const next = [...prev]
            if (next[next.length - 1]?.role === 'assistant') {
              next[next.length - 1] = { role: 'assistant', content: assistantText }
            } else {
              next.push({ role: 'assistant', content: assistantText })
            }
            return next
          })
        } else if (data.type === 'done') {
          settle()
          const { content: clean, suggestions: sugs } = parseFollowups(assistantText)
          if (clean !== assistantText) {
            // content = cleaned (for display); raw = full text with FOLLOWUPS
            // (sent back as history to keep the model emitting chips on later turns).
            setMessages(prev => {
              const next = [...prev]
              if (next[next.length - 1]?.role === 'assistant') {
                next[next.length - 1] = { role: 'assistant', content: clean, raw: assistantText }
              }
              return next
            })
          }
          setSuggestions(sugs)
          setStatus('idle')
          ws.close()
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

  return { messages, status, suggestions, error, sendMessage, retry }
}
