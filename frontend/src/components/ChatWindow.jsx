import { forwardRef, useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

const STARTER_CHIPS = [
  "What has Chris built?",
  "Tell me about the GPU home lab setup",
  "What startup experience does Chris have?",
  "What's psaios?",
  "How does this AI system work?",
  "Walk me through a major infrastructure project",
]

const CodeBlock = ({ className, children }) => {
  const [copied, setCopied] = useState(false)
  const language = /language-(\w+)/.exec(className || '')?.[1]
  const code = String(children).replace(/\n$/, '')

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }, [code])

  if (!language) {
    return (
      <code className="bg-gray-900 text-pink-300 px-1 py-0.5 rounded text-sm font-mono">
        {children}
      </code>
    )
  }

  return (
    <div className="relative group">
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 z-10 px-2 py-1 text-xs rounded
                   bg-gray-700 text-gray-400 hover:text-white hover:bg-gray-600
                   opacity-0 group-hover:opacity-100 transition"
      >
        {copied ? 'Copied ✓' : 'Copy'}
      </button>
      <SyntaxHighlighter style={oneDark} language={language} PreTag="div">
        {code}
      </SyntaxHighlighter>
    </div>
  )
}

const ChatWindow = forwardRef(({ messages, status, suggestions, error, onSuggestion, onRetry }, ref) => {
  return (
    <div className="space-y-4 p-4">
      {messages.length === 0 ? (
        <div className="py-12 px-4 text-center">
          <p className="text-gray-400 mb-6 text-base">Ask me anything about Chris's work</p>
          <div className="flex flex-wrap gap-2 justify-center max-w-2xl mx-auto">
            {STARTER_CHIPS.map(q => (
              <button
                key={q}
                onClick={() => onSuggestion(q)}
                className="px-4 py-2 rounded-full border border-gray-600 text-gray-300
                           hover:border-blue-500 hover:text-white text-sm transition"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      ) : (
        messages.map((msg, idx) => (
          <div key={idx}>
            <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[90%] sm:max-w-2xl px-4 py-3 rounded-lg ${
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

            {/* Follow-up suggestion chips after last assistant message */}
            {msg.role === 'assistant' && idx === messages.length - 1 && suggestions.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-3 pl-1">
                {suggestions.map(s => (
                  <button
                    key={s}
                    onClick={() => onSuggestion(s)}
                    className="px-3 py-1.5 rounded-full border border-blue-800 text-blue-300
                               hover:border-blue-500 hover:text-white text-xs transition"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))
      )}

      {/* Searching indicator */}
      {status === 'searching' && (
        <div className="flex justify-start">
          <div className="bg-gray-700 text-gray-400 px-4 py-3 rounded-lg text-sm italic">
            Searching knowledge base…
          </div>
        </div>
      )}

      {/* Generating indicator (only if no assistant message started yet) */}
      {status === 'generating' && messages[messages.length - 1]?.role !== 'assistant' && (
        <div className="flex justify-start">
          <div className="bg-gray-700 px-4 py-3 rounded-lg">
            <span className="flex gap-1">
              {[0, 150, 300].map(delay => (
                <span
                  key={delay}
                  className="inline-block w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce"
                  style={{ animationDelay: `${delay}ms` }}
                />
              ))}
            </span>
          </div>
        </div>
      )}

      {/* Error / reconnect */}
      {error && (
        <div className="flex justify-start">
          <div className="bg-red-900/50 border border-red-700 text-red-300 px-4 py-3
                          rounded-lg text-sm flex items-center gap-3">
            <span>
              {error === 'connection_lost' && 'Connection lost'}
              {error === 'server_error' && 'Something went wrong'}
              {error === 'prompt_too_long' && 'Message too long — please keep questions under 4,000 characters'}
            </span>
            {onRetry && error !== 'prompt_too_long' && (
              <button onClick={onRetry} className="underline hover:text-white transition">
                Retry
              </button>
            )}
          </div>
        </div>
      )}

      <div ref={ref} />
    </div>
  )
})

ChatWindow.displayName = 'ChatWindow'
export default ChatWindow
