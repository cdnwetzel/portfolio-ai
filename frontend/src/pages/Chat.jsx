import { useEffect, useRef } from 'react'
import ChatWindow from '../components/ChatWindow'
import MessageInput from '../components/MessageInput'
import Header from '../components/Header'
import SystemInfo from '../components/SystemInfo'
import { useChat } from '../hooks/useChat'

export default function Chat() {
  const { messages, status, suggestions, error, sendMessage, retry, clearChat, stopGeneration } = useChat()
  const messagesEndRef = useRef(null)
  const containerRef = useRef(null)

  // Auto-scroll only if near bottom or newly generating
  useEffect(() => {
    if (status === 'generating' || status === 'searching') {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [status])

  // Scroll on new messages only if already near bottom
  useEffect(() => {
    if (!containerRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 200
    if (isNearBottom) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  return (
    <div className="h-screen flex flex-col bg-primary">
      <Header onNewChat={clearChat} canClear={messages.length > 0} />

      <div className="flex-1 overflow-y-auto" ref={containerRef}>
        <div className="max-w-4xl mx-auto">
          <ChatWindow
            messages={messages}
            status={status}
            suggestions={suggestions}
            error={error}
            onSuggestion={sendMessage}
            onRetry={retry}
            ref={messagesEndRef}
          />
        </div>
      </div>

      <div className="bg-secondary border-t border-gray-700 p-4">
        <div className="max-w-4xl mx-auto">
          <MessageInput
            onSend={sendMessage}
            status={status}
            placeholder="Ask about infrastructure, AI systems, startup work…"
            onStop={stopGeneration}
          />
          {/* The clear control moved to the header "New chat" button — one obvious
              affordance beats two differently-worded ones doing the same thing.
              "stays in your browser" is literal: localStorage, so it survives a
              reload and a browser restart until New chat is pressed. */}
          <p className="text-center text-xs text-gray-600 mt-2">
            Chat history stays in your browser until you press New chat ·
            Nothing stored or logged server-side · No cloud GPU
          </p>
        </div>
      </div>

      <SystemInfo />
    </div>
  )
}
