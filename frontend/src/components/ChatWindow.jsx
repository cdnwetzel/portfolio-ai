import { forwardRef } from 'react'

const ChatWindow = forwardRef(({ messages }, ref) => {
  return (
    <div className="space-y-4 p-4">
      {messages.length === 0 ? (
        <div className="text-center text-gray-500 py-20">
          <p className="text-lg">Start a conversation above</p>
        </div>
      ) : (
        messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-2xl px-4 py-3 rounded-lg ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-100'
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
            </div>
          </div>
        ))
      )}
      <div ref={ref} />
    </div>
  )
})

ChatWindow.displayName = 'ChatWindow'
export default ChatWindow
