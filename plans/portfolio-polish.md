# Portfolio Polish Plan — dev.cwetzel.com

> **Status (2026-06-28): largely executed / historical snapshot.** The backend items shipped
> (bge-base embeddings, reranker, eval harness, verifier, guardrail — see `rag-improvements.md`
> and `verifier-faithfulness-layer.md`). Embedding/UI references below that mention
> `all-MiniLM-L6-v2` describe the *pre-upgrade* state this plan proposed changing — production is
> now `bge-base-en-v1.5` (768-d). Frontend-polish items may be partially done.

**Goal:** Transform the chat demo into a polished professional portfolio that communicates who Chris is,
demonstrates the infrastructure he built, and leaves a strong impression on technical visitors and recruiters.

**App structure:** `App.jsx` → `Landing.jsx` | `Chat.jsx` → `ChatWindow.jsx` + `MessageInput.jsx` + `useChat.js`

---

## Phase 1 — Suggested Starter Questions + AI Follow-Up Suggestions

**Effort:** Low–Medium (~2–3 hours)
**Impact:** Visitors don't know what to ask. Chips immediately demonstrate the system's depth.
After each response, follow-up chips reduce friction for continuing the conversation.

### 1a — Starter question chips

**Where:** `ChatWindow.jsx` empty state (when `messages.length === 0`), wired to `sendMessage` via `Chat.jsx`.

**Starter questions (include startup + infrastructure + AI angles):**
```
"What has Chris built?"
"Tell me about the GPU home lab setup"
"What startup experience does Chris have?"
"What's psaios?"
"How does this AI system work?"
"Walk me through a major infrastructure project"
```

**Code changes:**

`Chat.jsx` — pass `sendMessage` down to `ChatWindow`:
```jsx
<ChatWindow messages={messages} ref={messagesEndRef} onSuggestion={sendMessage} />
```

`ChatWindow.jsx` — render chips in empty state:
```jsx
const STARTER_CHIPS = [
  "What has Chris built?",
  "Tell me about the GPU home lab setup",
  "What startup experience does Chris have?",
  "What's psaios?",
  "How does this AI system work?",
  "Walk me through a major infrastructure project",
]

// In render, replace empty state <p> with:
{messages.length === 0 && (
  <div className="text-center py-16 px-4">
    <p className="text-gray-400 mb-6 text-lg">Ask me anything about Chris's work</p>
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
)}
```

### 1b — AI follow-up suggestions after each response

**Approach:** Instruct the model via system prompt to append a JSON block of follow-up questions
after each response. Parse and strip this block in `useChat.js` before rendering, surface as chips.

**System prompt addition** in `cloud/api-proxy.py` (append to existing system prompt):
```
After your response, on a new line append exactly:
FOLLOWUPS:["question 1","question 2","question 3"]
These are suggestions for what the user might ask next, based on what you just said.
Keep each under 60 characters.
```

**`useChat.js` changes:**
- Add `suggestions` to state: `const [suggestions, setSuggestions] = useState([])`
- On `done` event: scan the last assistant message for `FOLLOWUPS:[...]`, parse JSON,
  store in `suggestions`, strip the `FOLLOWUPS:` line from the displayed message content
- On next user send: clear `suggestions`
- Return `suggestions` from the hook

**`ChatWindow.jsx` changes:**
- Accept `suggestions` and `onSuggestion` props
- Render suggestion chips below the last assistant message when `suggestions.length > 0`:
```jsx
{idx === messages.length - 1 && suggestions.length > 0 && (
  <div className="flex flex-wrap gap-2 mt-3">
    {suggestions.map(s => (
      <button key={s} onClick={() => onSuggestion(s)}
        className="px-3 py-1 rounded-full border border-blue-800 text-blue-300
                   hover:border-blue-500 hover:text-white text-xs transition">
        {s}
      </button>
    ))}
  </div>
)}
```

**Files:** `useChat.js`, `ChatWindow.jsx`, `Chat.jsx`, `cloud/api-proxy.py`

---

## Phase 2 — Loading / Typing Indicator

**Effort:** Low (~1–2 hours)
**Impact:** The blank pause between send and first token looks like a broken page.

### State changes in `useChat.js`

Replace `loading` boolean with `status` enum:
```js
// Remove:   const [loading, setLoading] = useState(false)
// Add:
const [status, setStatus] = useState('idle') // 'idle' | 'searching' | 'generating'
```

Status transitions:
- `sendMessage()` called → `setStatus('searching')`
- `ws.onopen` fires (WebSocket connected, request sent) → stay `'searching'`
- First `chunk` message received → `setStatus('generating')`
- `done` message received → `setStatus('idle')`
- `onerror` / `onclose` → `setStatus('idle')`

Return `status` instead of `loading`:
```js
// Remove: return { messages, loading, sendMessage }
// Add:
return { messages, status, sendMessage, suggestions }
```

### Component changes

`Chat.jsx` — update prop threading:
```jsx
const { messages, status, sendMessage, suggestions } = useChat()
// Pass to MessageInput:
<MessageInput onSend={sendMessage} disabled={status !== 'idle'} ... />
// Pass to ChatWindow:
<ChatWindow messages={messages} status={status} suggestions={suggestions} onSuggestion={sendMessage} ref={messagesEndRef} />
// Update send button label:
{disabled ? (status === 'searching' ? 'Searching...' : '●●●') : 'Send'}
```

`ChatWindow.jsx` — render status bubble after last message:
```jsx
{status === 'searching' && (
  <div className="flex justify-start">
    <div className="bg-gray-700 text-gray-400 px-4 py-3 rounded-lg text-sm italic">
      Searching knowledge base...
    </div>
  </div>
)}
{status === 'generating' && messages[messages.length - 1]?.role !== 'assistant' && (
  <div className="flex justify-start">
    <div className="bg-gray-700 px-4 py-3 rounded-lg">
      <span className="flex gap-1">
        <span className="animate-bounce delay-0">●</span>
        <span className="animate-bounce delay-100">●</span>
        <span className="animate-bounce delay-200">●</span>
      </span>
    </div>
  </div>
)}
```

**Files:** `useChat.js`, `ChatWindow.jsx`, `Chat.jsx`, `MessageInput.jsx`

---

## Phase 3 — Hero Header

**Effort:** Low–Medium (~2 hours)
**Impact:** First impression. Visitors understand who Chris is and why this chat is impressive in 5 seconds.

### What to build

Replace the current minimal `Chat.jsx` header (`<h1>Chat with AI</h1>`) with a richer header component.

**Design:**
```
┌──────────────────────────────────────────────────────────┐
│ Chris Wetzel                              [GH] [LI] [✉]  │
│ Infrastructure & AI Engineer                              │
│ Ask me about 26 years of enterprise work, home lab        │
│ builds, or how this AI runs on my own GPU hardware.       │
│                          · Powered by Qwen 14B · 2× A4500│
└──────────────────────────────────────────────────────────┘
```

**New file:** `frontend/src/components/Header.jsx`
```jsx
const GITHUB_URL  = 'https://github.com/PLACEHOLDER'   // ← fill in
const LINKEDIN_URL = 'https://linkedin.com/in/PLACEHOLDER' // ← fill in
const EMAIL       = 'mailto:PLACEHOLDER@PLACEHOLDER.com'   // ← fill in

export default function Header() {
  return (
    <div className="bg-secondary border-b border-gray-700 px-4 py-3">
      <div className="max-w-4xl mx-auto flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-white">Chris Wetzel</h1>
            <span className="text-xs text-gray-500 hidden sm:inline">
              · Qwen 14B · 2× RTX A4500 · vLLM · Qdrant
            </span>
          </div>
          <p className="text-sm text-gray-400 mt-0.5">Infrastructure & AI Engineer</p>
          <p className="text-xs text-gray-500 mt-1 max-w-lg hidden md:block">
            Ask me about enterprise infrastructure, home lab GPU builds, AI systems,
            or 26 years of hands-on engineering work.
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0 pt-1">
          <a href={GITHUB_URL} target="_blank" rel="noreferrer"
             className="text-gray-400 hover:text-white transition" title="GitHub">
            {/* GitHub SVG icon */}
          </a>
          <a href={LINKEDIN_URL} target="_blank" rel="noreferrer"
             className="text-gray-400 hover:text-white transition" title="LinkedIn">
            {/* LinkedIn SVG icon */}
          </a>
          <a href={EMAIL}
             className="text-gray-400 hover:text-white transition" title="Email">
            {/* Email SVG icon */}
          </a>
        </div>
      </div>
    </div>
  )
}
```

**`Chat.jsx` changes:**
- Import and replace the existing `<div className="bg-secondary p-4 ...">` header block with `<Header />`
- Remove the "← Back" button (or keep it as a subtle link if Landing page is still useful)

**SVG icons:** Use inline SVGs from heroicons.com (no extra dependency needed):
- GitHub: `<path d="M12 2C6.477 ..." />` (standard GitHub mark)
- LinkedIn: standard LinkedIn square logo
- Email: heroicons `envelope` icon

**Files:** `frontend/src/components/Header.jsx` (new), `Chat.jsx`

---

## Phase 4 — Audit and Expand Knowledge Base

**Effort:** Medium (~half day)
**Impact:** The model answers are only as good as what's in Qdrant. Critical gaps exist.

### Current state (78 Qdrant points)

From sampling the collection:
- **Blog posts** (source: `blog_post`): M365 Copilot security, DLP policies, permission sprawl — strong content
- **Case studies** (source: `case_study`): SAP B1 integration, AVD migration — detailed and technical
- **Missing:** Resume/experience, infrastructure docs, psaios/pscode descriptions, startup experience,
  home lab / T5810 write-up, `pxx_docs/` content, `infrastructure/` dir is empty

### Gaps to fill

**1. Resume / experience** — `RESUME.md` exists in the KB dir but check if indexed (indexer loads it if present at `{kb_path}/RESUME.md`).

**2. `infrastructure/` directory is empty** — Add markdown files:
- `t5810_homelab.md` — T5810 hardware, dual A4500 NVLink, Gentoo, vLLM, Qdrant, SSH tunnel setup
- `gentoo_sysadmin.md` — Gentoo expertise, kernel builds, custom scripts, gentoo-machines repo
- `networking.md` — WireGuard, SSH tunnels, cloud/home hybrid architecture

**3. `pxx_docs/` not indexed** — The indexer (`index_with_embeddings.py`) doesn't walk `pxx_docs/`.
Add a loader section or point the indexer at this subdir.
Files: `API.md`, `ARCHITECTURE.md`, `CHANGELOG.md`, `DEPLOY.md`, `INSTALL.md`, `README.md`, `STATUS.md`

**4. Startup experience** — Add `case_studies/startup_experience.md` describing any startup roles,
founding/advisory work, early-stage company infrastructure.

**5. psaios / pscode** — Add `case_studies/psaios_project.md` describing the project, what it does,
tech stack, what your role was.

### How to re-index

The indexer runs on T5810 directly (uses `localhost:6333`). Steps:

```bash
# 1. Sync updated KB content to T5810
rsync -avz /Users/cwetzel/ai/cwdotcom/knowledge_base/ \
  chris@T5810:/tmp/knowledge_base/

# 2. SSH to T5810 and run indexer
ssh chris@T5810
cd /tmp
# Delete existing collection first (clean re-index):
curl -X DELETE http://localhost:6333/collections/documents
# Run indexer (uses all-MiniLM-L6-v2 on CPU):
python3 /path/to/index_with_embeddings.py
```

**Update `index_with_embeddings.py`** to also walk `pxx_docs/` and `infrastructure/`:
```python
# Add after case_studies loader:
for subdir in ['infrastructure', 'pxx_docs']:
    d = kb_dir / subdir
    if d.exists():
        for f in sorted(d.glob("*.md")):
            content = f.read_text()
            title = f.stem.replace("_", " ").title()
            docs.append({"id": f"{subdir}_{f.stem}", "title": title,
                         "content": content, "source": subdir})
```

**Note:** The embed service on port 8005 is what `api-proxy.py` uses for query-time embeddings.
The indexer uses `sentence_transformers` locally — both use the same `all-MiniLM-L6-v2` model
(384 dimensions, matches Qdrant collection config). Keep them consistent.

**Files:** `knowledge_base/infrastructure/*.md` (new), `knowledge_base/case_studies/startup_experience.md` (new), `knowledge_base/case_studies/psaios_project.md` (new), `scripts/index_with_embeddings.py` (add subdir walker)

---

## Phase 5 — "About This System" Tech Stack Panel

**Effort:** Low (~1–2 hours)
**Impact:** Surfaces the infrastructure story to technical visitors without disrupting chat UX.

### What to build

A collapsible info drawer toggled by a small "ⓘ About this system" button in the header or
as a fixed bottom-right corner widget.

**New file:** `frontend/src/components/SystemInfo.jsx`
```jsx
import { useState } from 'react'

const STACK = [
  { label: 'Model',     value: 'Qwen 2.5 Coder 14B Instruct + LoRA adapter' },
  { label: 'Hardware',  value: '2× NVIDIA RTX A4500 (NVLink, 40 GB total VRAM)' },
  { label: 'Host',      value: 'Dell Precision T5810 — Gentoo Linux' },
  { label: 'Serving',   value: 'vLLM v0.14 — tensor parallel across both GPUs' },
  { label: 'RAG',       value: 'Qdrant vector DB + all-MiniLM-L6-v2 embeddings' },
  { label: 'Proxy',     value: 'FastAPI on cloud VPS via SSH tunnel to home GPU' },
  { label: 'Frontend',  value: 'React + Vite + Tailwind CSS' },
]

export default function SystemInfo() {
  const [open, setOpen] = useState(false)

  return (
    <div className="fixed bottom-4 right-4 z-50">
      {open && (
        <div className="mb-2 bg-gray-900 border border-gray-700 rounded-lg p-4 w-80 shadow-xl">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
            About This System
          </h3>
          <dl className="space-y-1.5">
            {STACK.map(({ label, value }) => (
              <div key={label} className="grid grid-cols-[80px_1fr] gap-2 text-xs">
                <dt className="text-gray-500">{label}</dt>
                <dd className="text-gray-300">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="text-xs text-gray-600 mt-3 border-t border-gray-800 pt-3">
            Inference runs on Chris's home hardware, proxied through a cloud VPS.
          </p>
        </div>
      )}
      <button
        onClick={() => setOpen(o => !o)}
        className="bg-gray-800 hover:bg-gray-700 border border-gray-600 text-gray-400
                   hover:text-white text-xs px-3 py-1.5 rounded-full transition"
      >
        {open ? '✕ Close' : 'ⓘ About this system'}
      </button>
    </div>
  )
}
```

**`Chat.jsx`** — import and render `<SystemInfo />` inside the page div (it's fixed-position so placement doesn't matter structurally).

**Files:** `frontend/src/components/SystemInfo.jsx` (new), `Chat.jsx`

---

## Phase 6 — Error Recovery / Reconnect

**Effort:** Medium (~2–3 hours)
**Impact:** WebSocket connections drop on tunnel hiccups. Currently the user is silently stuck.

### State changes in `useChat.js`

Add `lastUserMessage` ref to track the last sent message for retry:
```js
const lastMessageRef = useRef(null)
```

Store on send:
```js
lastMessageRef.current = content
```

Add `error` state:
```js
const [error, setError] = useState(null) // null | 'connection_lost' | 'server_error'
```

**Reconnect logic:**
```js
let retryCount = 0
const MAX_RETRIES = 3

function connect(content, isRetry = false) {
  if (!isRetry) { retryCount = 0 }
  const ws = new WebSocket(wsUrl)
  // ... existing ws setup ...

  ws.onclose = (event) => {
    if (!closed && event.code === 1006) {
      // Abnormal closure — network drop or tunnel hiccup
      if (retryCount < MAX_RETRIES) {
        retryCount++
        const delay = Math.pow(2, retryCount) * 1000 // 2s, 4s, 8s
        setTimeout(() => connect(lastMessageRef.current, true), delay)
      } else {
        setError('connection_lost')
        setStatus('idle')
      }
    } else {
      closed = true
      setStatus('idle')
    }
  }
}
```

**Return `error` and `retry` from the hook:**
```js
const retry = () => {
  if (lastMessageRef.current) {
    setError(null)
    connect(lastMessageRef.current)
  }
}
return { messages, status, suggestions, error, sendMessage, retry }
```

### Component changes

`ChatWindow.jsx` — render error bubble with retry:
```jsx
{error === 'connection_lost' && (
  <div className="flex justify-start">
    <div className="bg-red-900/50 border border-red-700 text-red-300 px-4 py-3 rounded-lg
                    text-sm flex items-center gap-3">
      <span>Connection lost</span>
      <button onClick={onRetry}
        className="underline hover:text-white transition">
        Retry
      </button>
    </div>
  </div>
)}
```

**Files:** `useChat.js`, `ChatWindow.jsx`, `Chat.jsx`

---

## Phase 7 — Copy Button on Code Blocks

**Effort:** Low (~1 hour)
**Impact:** Standard expectation for any chat interface returning code. Missing reads as unfinished.

### Changes to `CodeBlock` in `ChatWindow.jsx`

```jsx
import { useState, useCallback } from 'react'

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
        className="absolute top-2 right-2 px-2 py-1 text-xs rounded
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
```

**Files:** `frontend/src/components/ChatWindow.jsx`

---

## Phase 8 — Disable enforce_eager / Enable CUDA Graphs

**Effort:** Medium (~1 hour change + monitoring)
**Impact:** `enforce_eager=1` costs ~20–40% token throughput. CUDA graphs allow vLLM to
pre-compile inference kernels, substantially faster token generation.

### Why it was set

The `pscode-vllm` init config at `/etc/conf.d/pscode-vllm` sets `PSCODE_ENFORCE_EAGER=1`.
Comment in `start-vllm.sh` explains: "needed on tighter-VRAM cards where cudagraph capture
workspace overruns gpu_memory_utilization." With `PSCODE_GPU_UTIL=0.95` this was an OOM risk.

### Now safe to try

With `PSCODE_GPU_UTIL=0.90` and LightDM disabled, free VRAM at startup is ~18.74 GiB with
only driver overhead. CUDA graph capture workspace for a 14B model at this context length
is approximately 1–2 GiB, which fits within the 10% headroom (1.87 GiB).

### Steps

```bash
# 1. Edit config on T5810
ssh root@T5810
# Change PSCODE_ENFORCE_EAGER=1 → PSCODE_ENFORCE_EAGER=0
sed -i 's/PSCODE_ENFORCE_EAGER=1/PSCODE_ENFORCE_EAGER=0/' /etc/conf.d/pscode-vllm

# 2. Restart service and watch logs
rc-service pscode-vllm restart
tail -f /var/log/pscode/vllm.log

# 3. Look for either:
#    SUCCESS: "CUDA graphs captured" or "Graph compilation complete"
#    FAILURE: "CUDA out of memory" during graph capture
```

### If capture fails

Lower GPU util further before retrying:
```bash
sed -i 's/PSCODE_GPU_UTIL=0.90/PSCODE_GPU_UTIL=0.85/' /etc/conf.d/pscode-vllm
rc-service pscode-vllm restart
```

### Benchmark before/after

Send a test request and measure tokens/sec from vLLM's response `usage` field:
```bash
ssh root@cwetzel.com "curl -s -X POST http://127.0.0.1:8004/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{\"model\":\"qwen2.5-coder-14b-pscode\",\"messages\":[{\"role\":\"user\",\"content\":\"Write a 200-word essay on networking.\"}],\"max_tokens\":300}' \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); u=d[\"usage\"]; print(u)'"
```

**Files:** `/etc/conf.d/pscode-vllm` on T5810 (server-side only, not in repo)

---

## Phase 9 — Parallelize RAG + Stream Start

**Effort:** Medium (~2 hours)
**Impact:** Removes 200–500ms user-perceived latency by hiding embed+search time behind
connection setup.

### Current flow (sequential)

```
send → embed query (100–200ms) → Qdrant search (50ms) → open vLLM stream → first token
```

### Target flow (parallel)

```
send → [embed query + Qdrant search]
       [open httpx client connection  ] → vLLM POST with context docs → first token
```

The TCP connection setup to `127.0.0.1:8004` (~1ms) is hidden behind the RAG latency (~150–250ms).
Total user-perceived delay drops by roughly 150ms.

### Changes to `cloud/api-proxy.py` `websocket_chat` handler

```python
import asyncio

# Replace the sequential:
#   context_docs = await search_knowledge_base(user_query, limit=3)
#   async with httpx.AsyncClient(timeout=120.0) as client:
#       async with client.stream("POST", ...) as response:

# With parallel gather:
async with httpx.AsyncClient(timeout=120.0) as client:
    # Kick off RAG search concurrently with client setup
    rag_task = asyncio.create_task(search_knowledge_base(user_query, limit=3))

    # Await RAG result (client is already initialized, connection pools ready)
    context_docs = await rag_task

    # Build system prompt with docs, then stream
    # ... (existing system prompt assembly) ...

    async with client.stream("POST", f"{VLLM_URL}/v1/chat/completions", json=body) as response:
        # ... existing streaming loop ...
```

**Note:** The `httpx.AsyncClient` context manager setup doesn't open a connection until the first
request — so this optimization mainly hides Python object allocation (~1ms) rather than TCP.
The real gain is if we move embed call and client creation truly parallel. A cleaner version:

```python
async def websocket_chat(websocket: WebSocket):
    # ...existing setup...
    user_query = messages[-1].get("content", "")

    # Parallel: embed+search AND prepare client
    context_docs, _ = await asyncio.gather(
        search_knowledge_base(user_query, limit=3),
        asyncio.sleep(0)  # yields control so gather is truly concurrent
    )
    # Then stream with assembled context
```

The full speedup comes when `search_knowledge_base` itself parallelizes its two steps (embed → search).
Update that function:
```python
async def search_knowledge_base(query: str, limit: int = 3) -> list:
    async with httpx.AsyncClient(timeout=10.0) as client:
        embed_response = await client.post(f"{EMBED_URL}/embed",
                                           json={"text": query}, timeout=5.0)
        if embed_response.status_code != 200:
            return []
        query_embedding = embed_response.json()["embedding"]

        search_response = await client.post(
            f"{QDRANT_URL}/collections/documents/points/search",
            json={"vector": query_embedding, "limit": limit, "with_payload": True},
            timeout=10.0
        )
        if search_response.status_code == 200:
            return [r.get("payload", {}) for r in search_response.json().get("result", [])]
        return []
```
(Current version opens a new `AsyncClient` per step — consolidating to one client saves ~50ms.)

**Files:** `cloud/api-proxy.py`

---

## Phase 10 — Mobile Polish

**Effort:** Medium (~2–3 hours)
**Impact:** Portfolio visitors check on phones. The chat must work cleanly at 375px.

### Known issues to fix

**Chat bubbles:** `max-w-2xl` is fine on mobile (Tailwind's `2xl` is 672px, smaller than any phone width —
this is actually ok). The `px-4 py-3` padding is acceptable.

**Header (Phase 3):** The two-line name + subtitle + social links + tech tag will overflow at 375px.
Responsive plan:
- Tech tag: `hidden sm:inline` — hide on mobile, show on ≥640px
- Description paragraph: `hidden md:block` — hide on mobile and tablet, show on ≥768px
- Social icons: always visible, `gap-3` → `gap-2` on mobile

**Starter chips (Phase 1):** `flex flex-wrap gap-2 justify-center` already wraps — should be fine.
Constrain to ~2 chips per row on very small screens: add `sm:max-w-lg` to the chips container.

**System info panel (Phase 5):** Fixed bottom-right `w-80` will overflow at 375px.
Add responsive width: `w-[calc(100vw-2rem)] sm:w-80` and `right-4 bottom-4`.

**MessageInput:** Input + button side-by-side (`flex gap-2`) is fine. The button text changes to
`'...'` while loading — ensure min button width so it doesn't collapse: add `min-w-[56px]`.

**Send button tap target:** Currently `px-6 py-3` which is ~48×44px — meets the 44px minimum. OK.

**WebSocket on mobile Safari:** iOS Safari closes WebSocket connections when the browser tab
backgrounds. Handle in `useChat.js`:
```js
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && wsRef.current?.readyState === WebSocket.CLOSED) {
    // Connection dropped while backgrounded — set error state so user sees retry
    setError('connection_lost')
  }
})
```

### Responsive breakpoints to audit

Test at: 375px (iPhone SE), 390px (iPhone 15), 768px (iPad).

```jsx
// Header responsive classes (Phase 3):
<h1 className="text-lg sm:text-xl font-bold text-white">
<p className="text-xs sm:text-sm text-gray-400 mt-0.5">
<p className="hidden md:block text-xs text-gray-500 ...">

// Chat page main layout — ensure full-height scroll on iOS:
<div className="h-screen flex flex-col bg-primary overflow-hidden">
  <div className="flex-1 overflow-y-auto -webkit-overflow-scrolling-touch">
```

**Files:** `ChatWindow.jsx`, `Chat.jsx`, `Header.jsx` (Phase 3), `SystemInfo.jsx` (Phase 5), `useChat.js`, `MessageInput.jsx`

---

## Prerequisites / Unknowns Requiring User Input Before Implementation

| Item | Needed for | Status |
|---|---|---|
| GitHub profile URL | Phase 3 Header | ⚠️ Placeholder in plan |
| LinkedIn profile URL | Phase 3 Header | ⚠️ Placeholder in plan |
| Contact email address | Phase 3 Header | ⚠️ Placeholder in plan |
| Startup experience content | Phase 4 KB | ⚠️ Need markdown write-up |
| psaios project description | Phase 4 KB | ⚠️ Need markdown write-up |
| T5810 / home lab write-up | Phase 4 KB | ⚠️ Need markdown write-up |
| Is GitHub repo public? | Phase 5 SystemInfo | ⚠️ For "View source" link |

---

## Summary Table

| Phase | Item | Effort | Primary Files |
|---|---|---|---|
| 1 | Starter chips + AI follow-up suggestions | Low–Med | `useChat.js`, `ChatWindow.jsx`, `Chat.jsx`, `api-proxy.py` |
| 2 | Loading / typing indicator | Low | `useChat.js`, `ChatWindow.jsx`, `Chat.jsx`, `MessageInput.jsx` |
| 3 | Hero header with social links | Low–Med | `Header.jsx` (new), `Chat.jsx` |
| 4 | Audit + expand knowledge base | Medium | `knowledge_base/**`, `scripts/index_with_embeddings.py` |
| 5 | "About this system" panel | Low | `SystemInfo.jsx` (new), `Chat.jsx` |
| 6 | Error recovery / reconnect | Medium | `useChat.js`, `ChatWindow.jsx`, `Chat.jsx` |
| 7 | Copy button on code blocks | Low | `ChatWindow.jsx` |
| 8 | Disable enforce_eager / CUDA graphs | Medium | `/etc/conf.d/pscode-vllm` (T5810) |
| 9 | Parallelize RAG + stream start | Medium | `cloud/api-proxy.py` |
| 10 | Mobile polish | Medium | `ChatWindow.jsx`, `Chat.jsx`, `Header.jsx`, `SystemInfo.jsx`, `useChat.js` |
