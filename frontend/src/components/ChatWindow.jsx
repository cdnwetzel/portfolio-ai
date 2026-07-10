import { forwardRef, useState, useCallback, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'

// Lazy-load the heavy syntax highlighter + prism style so they are not in the
// initial bundle. Only downloaded when a code block actually renders.
function useLazyHighlighter() {
  const [mod, setMod] = useState(null)
  useEffect(() => {
    let cancelled = false
    Promise.all([
      import('react-syntax-highlighter'),
      import('react-syntax-highlighter/dist/esm/styles/prism'),
    ]).then(([sh, style]) => {
      if (!cancelled) setMod({ Prism: sh.Prism, oneDark: style.oneDark })
    })
    return () => { cancelled = true }
  }, [])
  return mod
}

const STARTER_CHIPS = [
  "What has Chris built?",
  "Tell me about the GPU home lab setup",
  "What consulting and MSP experience does Chris have?",
  "Tell me about the pxx project",
  "How does this AI system work?",
  "Walk me through a major infrastructure project",
]

const CodeBlock = ({ className, children }) => {
  const [copied, setCopied] = useState(false)
  const highlighter = useLazyHighlighter()
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

  if (!highlighter) {
    return (
      <pre className="bg-gray-900 rounded p-3 overflow-x-auto text-sm font-mono text-gray-300">
        <code>{code}</code>
      </pre>
    )
  }

  const { Prism, oneDark } = highlighter
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
      <Prism style={oneDark} language={language} PreTag="div">
        {code}
      </Prism>
    </div>
  )
}

const SourceBlock = ({ sources }) => {
  const [open, setOpen] = useState(false)
  if (!sources || sources.length === 0) return null
  return (
    <div className="mt-2 pt-2 border-t border-gray-600/50">
      <button
        onClick={() => setOpen(v => !v)}
        className="text-xs text-gray-400 hover:text-blue-300 flex items-center gap-1 transition"
      >
        <span>{open ? '▾' : '▸'}</span>
        <span>Sources ({sources.length})</span>
      </button>
      {open && (
        <ul className="mt-2 space-y-2 text-xs text-gray-400">
          {sources.map((s, i) => (
            <li key={i} className="bg-gray-800/50 rounded p-2">
              <div className="flex justify-between gap-2 text-gray-300">
                <span className="font-medium truncate">{s.title || 'Unknown'}</span>
                <span className="shrink-0 text-gray-500">{s.score !== undefined ? s.score.toFixed(3) : ''}</span>
              </div>
              {s.source && <div className="text-gray-500 truncate">{s.source}</div>}
              {s.snippet && <div className="mt-1 text-gray-400 line-clamp-2">{s.snippet}</div>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// Subtle per-message performance footer — turns "runs on my own GPUs" into a shown fact.
// Fed by metadata-only timing/token counts on the `done` message (no content).
const MetricsFooter = ({ metrics }) => {
  if (!metrics) return null
  const { retrieval_ms, ttft_ms, generation_ms, completion } = metrics
  const parts = []
  // User-perceived time to first token = RAG retrieval + model prefill (not prefill alone).
  if (ttft_ms != null) {
    parts.push(`${(((retrieval_ms || 0) + ttft_ms) / 1000).toFixed(1)}s to first token`)
  }
  // Decode throughput = completion tokens over the streaming window (excludes prefill).
  const streamMs = (generation_ms != null && ttft_ms != null)
    ? Math.max(1, generation_ms - ttft_ms) : generation_ms
  if (streamMs && completion) parts.push(`${(completion / (streamMs / 1000)).toFixed(1)} tok/s`)
  if (retrieval_ms != null && generation_ms != null) {
    parts.push(`${((retrieval_ms + generation_ms) / 1000).toFixed(1)}s total`)
  }
  if (parts.length === 0) return null
  return (
    <div
      className="mt-2 text-[11px] text-gray-500 flex items-center gap-1"
      title="Generated live on Chris's own hardware — 2× RTX A4500 (T5810)"
    >
      <span aria-hidden="true">⚡</span>
      <span>{parts.join(' · ')}</span>
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
                {msg.role === 'assistant' && <SourceBlock sources={msg.sources} />}
                {msg.role === 'assistant' && <MetricsFooter metrics={msg.metrics} />}
                {msg.role === 'assistant' && msg.flagged && (
                  <div className="mt-2 pt-2 border-t border-amber-600/30 flex items-start gap-1.5 text-xs text-amber-400/90">
                    <span aria-hidden="true">⚠</span>
                    <span>A claim in this answer was flagged by the faithfulness check for review.</span>
                  </div>
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
