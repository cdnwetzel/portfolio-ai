import { useState, useRef } from 'react'

export function useChat() {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const wsRef = useRef(null)

  const sendMessage = (content) => {
    const userMessage = { role: 'user', content }
    setMessages(prev => [...prev, userMessage])
    setLoading(true)

    // Determine WS URL (dev vs prod)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/chat`

    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      ws.send(JSON.stringify({
        type: 'chat',
        payload: {
          messages: [...messages, userMessage],
          model: 'Qwen2.5-14B',
          temperature: 0.7,
          max_tokens: 1024
        }
      }))
    }

    let assistantMessage = ''
    let closed = false

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.type === 'chunk' && data.data?.choices?.[0]?.delta?.content) {
          assistantMessage += data.data.choices[0].delta.content
          setMessages(prev => {
            const updated = [...prev]
            if (updated[updated.length - 1]?.role === 'assistant') {
              updated[updated.length - 1].content = assistantMessage
            } else {
              updated.push({ role: 'assistant', content: assistantMessage })
            }
            return updated
          })
        } else if (data.type === 'done') {
          closed = true
          setLoading(false)
          ws.close()
        }
      } catch (e) {
        console.error('Parse error:', e)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      if (!closed) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: 'Error connecting to API. Please try again.'
        }])
        closed = true
      }
      setLoading(false)
    }

    ws.onclose = () => {
      if (!closed) {
        closed = true
        setLoading(false)
      }
    }

    wsRef.current = ws
  }

  return { messages, loading, sendMessage }
}
