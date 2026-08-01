import { useEffect, useRef } from 'react'
import ChatWindow from '../components/ChatWindow'
import MessageInput from '../components/MessageInput'
import Header from '../components/Header'
import SystemInfo from '../components/SystemInfo'
import { useChat } from '../hooks/useChat'

export default function Chat() {
  const { messages, status, suggestions, error, sendMessage, retry, clearChat } = useChat()
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, status])

  return (
    <div className="h-screen flex flex-col bg-primary">
      <Header />

      <div className="flex-1 overflow-y-auto">
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
          />
          <div className="flex items-center justify-center gap-3 mt-2">
            <p className="text-center text-xs text-gray-600">
              Chat history stays in your browser · Nothing stored or logged server-side · No cloud GPU
            </p>
            {messages.length > 0 && (
              <button
                onClick={clearChat}
                className="text-xs text-gray-600 hover:text-gray-300 underline transition shrink-0"
              >
                Clear chat
              </button>
            )}
          </div>
        </div>
      </div>

      <SystemInfo />
    </div>
  )
}
