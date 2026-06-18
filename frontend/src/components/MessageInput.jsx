import { useState } from 'react'

export default function MessageInput({ onSend, status, placeholder }) {
  const [input, setInput] = useState('')
  const busy = status !== 'idle'

  const handleSubmit = (e) => {
    e.preventDefault()
    if (input.trim() && !busy) {
      onSend(input)
      setInput('')
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const btnLabel = status === 'searching' ? 'Searching…' : status === 'generating' ? 'Writing…' : 'Send'

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={busy}
        className="flex-1 px-4 py-3 rounded-lg bg-primary border border-gray-600 text-white
                   placeholder-gray-400 focus:outline-none focus:border-blue-600
                   disabled:opacity-50 text-base"
      />
      <button
        type="submit"
        disabled={busy || !input.trim()}
        className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600
                   text-white font-semibold rounded-lg transition min-w-[5rem]"
      >
        {btnLabel}
      </button>
    </form>
  )
}
