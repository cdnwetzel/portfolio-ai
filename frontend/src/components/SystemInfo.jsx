import { useState } from 'react'
import useSystemInfo from '../hooks/useSystemInfo'

// Only genuinely STATIC facts belong here. Anything the fleet can change —
// the model, the context window, KB size, the verifier GPU — is served by
// /api/system-info so a hardware or model swap does not require a frontend
// rebuild. This panel displayed "Qwen2.5-Coder 14B Instruct / 16 384 tokens"
// for a week after the T5810 moved to Qwen3.8-27B-FP8 at 32K, because those
// were hardcoded here.
const STACK = [
  { label: 'GPU',        value: '2× RTX A4500 20GB NVLink (T5810)' },
  { label: 'Inference',  value: 'vLLM (tensor parallel)' },
  { label: 'Vector DB',  value: 'Qdrant (dense cosine)' },
  { label: 'Embeddings', value: 'bge-base-en-v1.5 (768-d)' },
  { label: 'Reranker',   value: 'bge-reranker-base (GPU, asrock)' },
  { label: 'Servers',    value: 'T5810 + asrock B550 (Gentoo)' },
  { label: 'Frontend',   value: 'React + Vite + Tailwind' },
]

export default function SystemInfo() {
  const [open, setOpen] = useState(false)
  // '—' until the fetch lands; stays '—' if the proxy is down.
  const info = useSystemInfo()

  const live = [
    {
      label: 'Model',
      value: info ? info.model : '—',
    },
    {
      label: 'Context',
      value: info ? `${info.context_tokens.toLocaleString('en-US')} tokens` : '—',
    },
    {
      label: 'Knowledge base',
      value: info ? `${info.docs} docs · ${info.chunks} chunks` : '—',
    },
    {
      label: 'Verifier',
      value: info ? `Qwen2.5-14B judge · ${info.verifier_gpu} box (asrock)` : '—',
    },
  ]

  // Keep the original row order: KB sits between Vector DB and Embeddings,
  // Verifier between Reranker and Servers.
  const rows = [
    ...STACK.slice(0, 5),
    live[0],
    ...STACK.slice(5, 7),
    live[1],
    ...STACK.slice(7),
  ]

  return (
    <div className="fixed bottom-4 right-4 z-50 text-xs">
      {open && (
        <div className="mb-2 bg-gray-900 border border-gray-700 rounded-lg shadow-xl
                        p-3 w-60 text-gray-300">
          <p className="font-semibold text-white mb-2">About this system</p>
          <dl className="space-y-1">
            {rows.map(({ label, value }) => (
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
