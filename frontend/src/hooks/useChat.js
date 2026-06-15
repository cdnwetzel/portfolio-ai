import { useState, useRef, useEffect, useCallback } from 'react'

const DEBUG = typeof localStorage !== 'undefined' && localStorage.getItem('debug') === 'true'
const log = DEBUG ? console.log.bind(console) : () => {}

const FOLLOWUPS_RE = /\n?FOLLOWUPS:(\[[\s\S]*?\])\s*$/

function parseFollowups(content) {
  const match = content.match(FOLLOWUPS_RE)
  if (!match) return { content, suggestions: [] }
  try {
    const parsed = JSON.parse(match[1])
    return {
      content: content.slice(0, match.index).trimEnd(),
      suggestions: Array.isArray(parsed) ? parsed.slice(0, 3) : []
    }
  } catch {
    return { content, suggestions: [] }
  }
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
      ws.send(JSON.stringify({
        type: 'chat',
        payload: {
          messages: allMessages,
          model: 'qwen2.5-coder-14b-pscode',
          temperature: 0.7,
          max_tokens: 1024
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
            setMessages(prev => {
              const next = [...prev]
              if (next[next.length - 1]?.role === 'assistant') {
                next[next.length - 1] = { role: 'assistant', content: clean }
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
