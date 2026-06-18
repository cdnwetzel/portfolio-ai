import { useState } from 'react'

const STACK = [
  { label: 'Model',      value: 'Qwen2.5-Coder 14B Instruct' },
  { label: 'GPU',        value: '2× RTX A4500 20GB NVLink' },
  { label: 'Inference',  value: 'vLLM (tensor parallel)' },
  { label: 'Context',    value: '16 384 tokens' },
  { label: 'Vector DB',  value: 'Qdrant (cosine similarity)' },
  { label: 'Embeddings', value: 'all-MiniLM-L6-v2' },
  { label: 'Reranker',   value: 'bge-reranker-base (CPU)' },
  { label: 'Server',     value: 'Dell Precision T5810 (Gentoo)' },
  { label: 'Frontend',   value: 'React + Vite + Tailwind' },
]

export default function SystemInfo() {
  const [open, setOpen] = useState(false)

  return (
    <div className="fixed bottom-4 right-4 z-50 text-xs">
      {open && (
        <div className="mb-2 bg-gray-900 border border-gray-700 rounded-lg shadow-xl
                        p-3 w-60 text-gray-300">
          <p className="font-semibold text-white mb-2">About this system</p>
          <dl className="space-y-1">
            {STACK.map(({ label, value }) => (
              <div key={label} className="flex justify-between gap-2">
                <dt className="text-gray-500 shrink-0">{label}</dt>
                <dd className="text-right text-gray-300">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-2 pt-2 border-t border-gray-700 text-gray-500">
            Home lab · No cloud GPU costs
          </p>
        </div>
      )}
      <button
        onClick={() => setOpen(v => !v)}
        className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-full
                   bg-gray-800 border border-gray-700 text-gray-400
                   hover:text-white hover:border-gray-500 transition shadow-lg"
      >
        <span className="text-base leading-none">ⓘ</span>
        <span>About this system</span>
      </button>
    </div>
  )
}
