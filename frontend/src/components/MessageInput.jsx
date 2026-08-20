import { useState, useRef, useEffect } from 'react'

const MAX_CHARS = 4000

export default function MessageInput({ onSend, status, placeholder, onStop }) {
  const [input, setInput] = useState('')
  const [rows, setRows] = useState(1)
  const textareaRef = useRef(null)
  const busy = status !== 'idle'

  const handleSubmit = (e) => {
    e.preventDefault()
    if (input.trim() && !busy) {
      onSend(input)
      setInput('')
      setRows(1)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const handleChange = (e) => {
    const text = e.target.value.slice(0, MAX_CHARS)
    setInput(text)
    // Auto-grow textarea: count newlines, cap at 8 rows
    const lineCount = (text.match(/\n/g) || []).length + 1
    setRows(Math.min(8, Math.max(1, lineCount)))
  }

  // Reset rows when input clears
  useEffect(() => {
    if (!input.trim()) setRows(1)
  }, [input])

  const btnLabel = status === 'searching' ? 'Searching…' : status === 'generating' ? 'Writing…' : 'Send'
  const isOver = input.length >= MAX_CHARS

  return (
    <form onSubmit={handleSubmit}>
      {/* The counter must live OUTSIDE this row. Inside it, `items-end` aligned the
          button to the bottom of the counter rather than the textarea, pushing the
          button ~20px low. The buttons carry a transparent border so their box height
          matches the textarea's bordered box exactly (50px at rows=1). */}
      <div className="flex gap-2 items-end">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={busy}
          rows={rows}
          className="flex-1 px-4 py-3 rounded-lg bg-primary border border-gray-600 text-white
                     placeholder-gray-400 focus:outline-none focus:border-blue-600
                     disabled:opacity-50 text-base font-sans resize-none overflow-y-auto
                     max-h-[200px]"
        />

        {busy ? (
          <button
            type="button"
            onClick={onStop}
            className="px-6 py-3 bg-red-600 hover:bg-red-700 text-white font-semibold
                       rounded-lg transition min-w-[5rem] border border-transparent"
          >
            Stop
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim()}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600
                       text-white font-semibold rounded-lg transition min-w-[5rem]
                       border border-transparent"
          >
            {btnLabel}
          </button>
        )}
      </div>

      <div className="text-xs text-gray-500 mt-1">
        {input.length}/{MAX_CHARS}
        {isOver && <span className="ml-1 text-red-400">at limit</span>}
      </div>
    </form>
  )
}
