import { forwardRef } from 'react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

const CodeBlock = ({ className, children }) => {
  const language = /language-(\w+)/.exec(className || '')?.[1]
  return language ? (
    <SyntaxHighlighter style={oneDark} language={language} PreTag="div">
      {String(children).replace(/\n$/, '')}
    </SyntaxHighlighter>
  ) : (
    <code className="bg-gray-900 text-pink-300 px-1 py-0.5 rounded text-sm font-mono">
      {children}
    </code>
  )
}

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
              {msg.role === 'user' ? (
                <p className="whitespace-pre-wrap">{msg.content}</p>
              ) : (
                <ReactMarkdown
                  className="prose prose-invert prose-sm max-w-none"
                  components={{ code: CodeBlock }}
                >
                  {msg.content}
                </ReactMarkdown>
              )}
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
