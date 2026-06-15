# pxx — Offline-Capable aider Orchestrator

## What It Is

`pxx` is a command-line orchestrator I built that wraps [aider](https://aider.chat) with LLM endpoint detection, persistent observation memory, safety gates, and cross-machine coordination. It's designed for local-first AI-assisted development — no cloud dependency, all inference stays on the network.

**Repo:** https://github.com/cdnwetzel/pxx  
**Install:** `pip install pxx-orchestrator` (core); services require a repo checkout

## What Problem It Solves

Aider is a powerful AI coding assistant but it's stateless — every session starts cold. pxx adds:

1. **Endpoint detection**: probes which LLM is reachable (Mac Studio Ollama → T5810 vLLM via SSH tunnel → fallback) and picks the right model automatically
2. **Persistent memory**: captures what aider does (tool calls, edits) into an observation store. Future sessions retrieve relevant prior context via hybrid BM25 + vector search
3. **Safety gates**: ask mode (read-only) is the default; `--edit` flag required to allow file changes. Path-prefix scoping prevents accidental edits outside trusted directories
4. **Cross-machine drift detection**: checks if the Mac Studio and T5810 are out of sync before an edit session

## Fleet It Runs On

- **Mac Studio** (M4 Max, 36GB) — runs pxx and Ollama locally (`devstral:24b` default, plus `qwen2.5:32b`, `qwen2.5-coder:7b`)
- **T5810** (Dell Precision, 2× RTX A4500) — remote vLLM serving `qwen2.5-coder-14b` via SSH tunnel on `:8003`. Used for tier-2/3 sessions requiring more GPU headroom

## Architecture

```
Your Project
    ↓
  pxx
    ├→ detect_endpoint()  — probe Mac Studio → T5810 vLLM → first reachable wins
    ├→ start agentmemory  — optional: observation storage with hybrid search
    ├→ start 9router      — optional: OpenAI-compatible proxy with token tracking
    └→ os.execv → aider   — pxx is out once aider takes over
                   ↓
             Tool calls captured → agentmemory
             Files modified + observation stored
                   ↓
             Next session sees prior context
```

## Key Features

### Persistent Observation Memory (agentmemory service)
- Captures aider tool calls and edits automatically
- Hybrid search: 40% BM25 keyword + 60% semantic vector similarity
- HNSW index for fast retrieval at scale (100x speedup at 100k+ observations)
- TTL cleanup (configurable; 90-day default), archived to JSONL on delete
- Slash commands in session: `/recall <query>`, `/remember`, `/forget`

### Safety Design
- Ask mode default — nothing edits without `--edit` flag
- Git safety tags before each edit session for rollback
- Trusted-path gates: restrict `--edit` to specific directory prefixes
- Audit log of every session (for post-mortems and distillation)

### Dogfooding Modes (pxx improving itself)
- `pxx --self-test` — run pytest against pxx
- `pxx --self-lint` — ruff check + format
- `pxx --self-improve` — ask-mode aider session suggesting improvements
- `pxx --self-fix "<task>" --scope X` — bounded autonomous edit

## Optional Services

**9router** — OpenAI-compatible proxy running on `127.0.0.1:20128`. Routes requests to primary (Studio Ollama) with configurable fallback chains. Token tracking.

**agentmemory** — observation storage API on `127.0.0.1:3111`. SQLite backend. Not authenticated — designed for LAN/VPN only.

Both services are opt-in (`pxx --with-memory`, `pxx --with-router`) and auto-started by pxx's supervisor mode. They run on the Mac Studio alongside pxx itself.

## Python Stack

- Python 3.11+ (3.12 day-to-day)
- `aider-chat` (pinned version — aider releases weekly and can break pxx behavior)
- `uv` for dependency management
- `ruff` for linting and formatting
- `pytest` for tests

## What I Learned Building This

The interesting engineering problem was the memory system: making a RAG pipeline useful for *short-horizon developer context* (what did I edit yesterday? what did aider try that didn't work?) rather than document retrieval. Hybrid BM25 + vector search outperforms either alone for code-adjacent text. The TTL + archive pattern keeps the observation store lean without losing history permanently.

The aider pin discipline was also non-trivial — aider changes behavior across minor releases in ways that break orchestrator assumptions (`os.execv` semantics, `--chat-mode` handling, edit format defaults). Treating it like a sensitive dependency rather than a casually-bumped library saved several debugging sessions.
