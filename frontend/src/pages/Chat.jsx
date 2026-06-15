import { useEffect, useRef } from 'react'
import ChatWindow from '../components/ChatWindow'
import MessageInput from '../components/MessageInput'
import Header from '../components/Header'
import SystemInfo from '../components/SystemInfo'
import { useChat } from '../hooks/useChat'

export default function Chat() {
  const { messages, status, suggestions, error, sendMessage, retry } = useChat()
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
          <p className="text-center text-xs text-gray-600 mt-2">
            Conversations are not stored or logged · Running on owned hardware · No cloud GPU
          </p>
        </div>
      </div>

      <SystemInfo />
    </div>
  )
}
