const GITHUB_URL   = 'https://github.com/cdnwetzel'
const LINKEDIN_URL = 'https://linkedin.com/in/chris-wetzel'
const EMAIL        = 'mailto:chris@cwetzel.com'
const REPO_URL     = 'https://github.com/cdnwetzel/portfolio-ai'

const GitHubIcon = () => (
  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839
      9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343
      -3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07
      1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338
      -2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446
      -1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844a9.59 9.59 0 012.504.337
      c1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595
      1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012
      2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522
      2 12 2z" clipRule="evenodd" />
  </svg>
)

const LinkedInIcon = () => (
  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136
      1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85
      3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065
      2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771
      C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227
      24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
  </svg>
)

const EmailIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75
         m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25
         2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0
         01-1.07-1.916V6.75" />
  </svg>
)

export default function Header() {
  return (
    <div className="bg-secondary border-b border-gray-700 px-4 py-3 shrink-0">
      <div className="max-w-4xl mx-auto flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
            <h1 className="text-lg sm:text-xl font-bold text-white whitespace-nowrap">
              Chris Wetzel
            </h1>
            <span className="text-xs text-gray-500 hidden sm:inline whitespace-nowrap">
              Qwen 14B · 2× RTX A4500 · vLLM · Qdrant
            </span>
          </div>
          <p className="text-xs sm:text-sm text-gray-400 mt-0.5">
            Infrastructure &amp; AI Engineer
          </p>
          <p className="hidden md:block text-xs text-gray-500 mt-1 max-w-lg">
            Ask about enterprise infrastructure, home lab GPU builds, AI systems,
            or 26 years of hands-on engineering work.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0 pt-0.5">
          <a href={GITHUB_URL} target="_blank" rel="noreferrer"
             className="text-gray-400 hover:text-white transition" title="GitHub">
            <GitHubIcon />
          </a>
          <a href={LINKEDIN_URL} target="_blank" rel="noreferrer"
             className="text-gray-400 hover:text-white transition" title="LinkedIn">
            <LinkedInIcon />
          </a>
          <a href={EMAIL}
             className="text-gray-400 hover:text-white transition" title="Email">
            <EmailIcon />
          </a>
          <a href={REPO_URL} target="_blank" rel="noreferrer"
             className="hidden sm:inline text-xs text-gray-500 hover:text-gray-300 transition border border-gray-700 hover:border-gray-500 rounded px-2 py-1">
            View source
          </a>
        </div>
      </div>
    </div>
  )
}
