const GITHUB_URL   = 'https://github.com/cdnwetzel'
const LINKEDIN_URL = 'https://linkedin.com/in/chris-wetzel'
const EMAIL        = 'mailto:chris@cwetzel.com'
const REPO_URL     = 'https://github.com/cdnwetzel/portfolio-saas'

const STACK = [
  'Qwen 14B', 'vLLM', 'Qdrant', 'RAG', 'React', 'Gentoo', '2× RTX A4500', 'Verifier'
]

const HOW_IT_WORKS = [
  {
    icon: '🗂',
    title: 'Knowledge Base',
    desc: '26 years of documented work — case studies, infrastructure write-ups, LinkedIn posts, resume — indexed as semantic vectors.',
  },
  {
    icon: '🔍',
    title: 'RAG Retrieval',
    desc: 'Your question is embedded and matched against the KB using cosine similarity. The top matching docs ground every answer.',
  },
  {
    icon: '⚡',
    title: 'Local Inference',
    desc: 'Qwen 14B runs on two RTX A4500 GPUs in my home office via tensor parallelism. No cloud GPU — owned hardware, no per-token cost.',
  },
  {
    icon: '✅',
    title: 'Faithfulness Verified',
    desc: 'After each answer, an independent model on a second home server (Ryzen 9 / RTX 3060 Ti) scores whether every claim is grounded in the retrieved sources.',
  },
]

export default function Landing({ onStart }) {
  return (
    <div className="min-h-screen bg-primary flex flex-col">
      {/* Hero */}
      <div className="flex-1 flex flex-col items-center justify-center px-4 py-12 text-center">
        <p className="text-xs font-mono text-blue-400 tracking-widest uppercase mb-4">
          Portfolio AI · dev.cwetzel.com
        </p>
        <h1 className="text-4xl sm:text-5xl font-bold text-white mb-4 max-w-2xl leading-tight">
          Ask anything about 26 years of enterprise infrastructure
        </h1>
        <p className="text-gray-400 text-lg mb-2 max-w-xl">
          Answers grounded in documented work — not generated from thin air.
          Every response cites real projects, real machines, real outcomes.
        </p>
        <p className="text-gray-500 text-sm mb-8">
          Chris Wetzel · IT Manager & Infrastructure Engineer · Trenton, NJ
        </p>

        <button
          onClick={onStart}
          className="px-10 py-4 bg-blue-600 hover:bg-blue-500 text-white font-semibold
                     rounded-lg transition text-lg shadow-lg shadow-blue-900/30 mb-6"
        >
          Start Chat
        </button>

        {/* Social links */}
        <div className="flex items-center gap-5 text-sm text-gray-400">
          <a href={GITHUB_URL} target="_blank" rel="noreferrer"
             className="hover:text-white transition">GitHub</a>
          <span className="text-gray-700">·</span>
          <a href={LINKEDIN_URL} target="_blank" rel="noreferrer"
             className="hover:text-white transition">LinkedIn</a>
          <span className="text-gray-700">·</span>
          <a href={EMAIL} className="hover:text-white transition">Email</a>
          <span className="text-gray-700">·</span>
          <a href={REPO_URL} target="_blank" rel="noreferrer"
             className="hover:text-white transition">View source</a>
        </div>
      </div>

      {/* How it works */}
      <div className="border-t border-gray-800 px-4 py-10">
        <p className="text-center text-xs text-gray-600 uppercase tracking-widest mb-8">
          How it works
        </p>
        <div className="max-w-3xl mx-auto grid sm:grid-cols-2 gap-6">
          {HOW_IT_WORKS.map(({ icon, title, desc }) => (
            <div key={title} className="bg-secondary rounded-lg p-5">
              <div className="text-2xl mb-2">{icon}</div>
              <h3 className="font-semibold text-white mb-1">{title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>

        {/* Tech stack pills */}
        <div className="flex flex-wrap justify-center gap-2 mt-8">
          {STACK.map(t => (
            <span key={t}
              className="px-3 py-1 rounded-full bg-gray-800 border border-gray-700
                         text-gray-400 text-xs font-mono">
              {t}
            </span>
          ))}
        </div>

        <p className="text-center text-xs text-gray-700 mt-6">
          Conversations are not stored or logged · Running on owned hardware · No cloud GPU
        </p>
      </div>
    </div>
  )
}
