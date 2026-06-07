import { useState, useEffect, useRef } from 'react'
import ChatWindow from '../components/ChatWindow'
import MessageInput from '../components/MessageInput'
import { useChat } from '../hooks/useChat'

export default function Chat({ onBack }) {
  const { messages, loading, sendMessage } = useChat()
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="h-screen flex flex-col bg-primary">
      {/* Header */}
      <div className="bg-secondary p-4 border-b border-gray-700">
        <div className="max-w-4xl mx-auto flex justify-between items-center">
          <h1 className="text-2xl font-bold">Chat with AI</h1>
          <button
            onClick={onBack}
            className="px-4 py-2 text-gray-300 hover:text-white transition"
          >
            ← Back
          </button>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto">
          <ChatWindow messages={messages} ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="bg-secondary border-t border-gray-700 p-4">
        <div className="max-w-4xl mx-auto">
          <MessageInput
            onSend={sendMessage}
            disabled={loading}
            placeholder="Ask me about infrastructure, cloud, compliance..."
          />
        </div>
      </div>
    </div>
  )
}
