# pxx — Offline-Capable aider Orchestrator

## What It Is

`pxx` is a command-line orchestrator I built that wraps [aider](https://aider.chat) with LLM endpoint detection, persistent observation memory, safety gates, and cross-machine coordination. It's designed for local-first AI-assisted development — no cloud dependency, all inference stays on the LAN or VPN.

**Repo:** https://github.com/cdnwetzel/pxx  
**Install:** `pip install pxx-orchestrator` (core); services require a repo checkout  
**Also installable:** `pip install agentmemory` (memory service as a standalone tool)

---

## What Problem It Solves

Aider is a powerful AI coding assistant but it's stateless — every session starts cold. pxx adds:

1. **Endpoint detection**: probes which LLM is reachable (Mac Studio Ollama → T5810 vLLM → fallback) and picks the right model automatically
2. **Persistent memory**: captures what aider does (tool calls, edits) into an observation store; future sessions retrieve relevant prior context via hybrid BM25 + vector search
3. **Safety gates**: ask mode (read-only) is the default; `--edit` flag required to allow file changes; path-prefix scoping prevents accidental edits outside trusted directories
4. **Autonomous loop**: `--loop/--heal` mode runs bounded edit→test→review→heal rounds without manual intervention
5. **Cross-machine drift detection**: checks if the Mac Studio and T5810 are out of sync before an edit session

---

## Fleet It Runs On

- **Mac Studio** (M4 Max, 36GB) — primary machine. Runs pxx and Ollama locally. Default model: `devstral:24b`. Also available: `qwen2.5:32b`, `qwen2.5-coder:7b`
- **T5810** (Dell Precision, 2× RTX A4500) — remote vLLM serving `qwen2.5-coder-14b` via SSH tunnel on `:8003`. Used for tier-2/3 sessions requiring more GPU headroom

---

## Architecture

```
Your Project
    ↓
  pxx
    ├→ detect_endpoint()  — probe Mac Studio → T5810 vLLM → first reachable wins
    ├→ start agentmemory  — optional: observation storage with hybrid search
    ├→ start 9router      — optional: OpenAI-compatible proxy with token tracking
    └→ os.execv → aider   — pxx hands off to aider once configured
                   ↓
             Tool calls + edits captured → agentmemory
                   ↓
             Next session retrieves relevant prior context
```

The `os.execv` boundary is deliberate: pxx does setup then gets out, rather than wrapping aider's I/O. This makes pxx's surface area small and aider's behavior predictable.

---

## Key Features

### Persistent Observation Memory (agentmemory service)

- Captures aider tool calls and edits automatically during sessions
- Hybrid search: 40% BM25 keyword + 60% semantic vector similarity (`sentence-transformers`, 384-dim vectors)
- HNSW index: ~5ms retrieval at 100k+ observations (100× speedup over linear scan)
- LRU SearchCache layer above HNSW: additional 100× speedup on repeated queries; cache invalidated on all mutation endpoints; cache stats exposed at `/metrics`
- SQLite storage at `~/.pxx/memory.db`; <100MB per 10k observations; archived to JSONL on TTL expiry (90-day default)
- Per-project TTL overrides: `POST /retention/config` — e.g., `temp` project at 7-day retention
- Slash commands in session: `/recall <query>`, `/remember`, `/forget`
- `/inject` endpoint enforces a `max_chars` budget when preparing observations for context injection

### `--loop / --heal` Autonomous Mode

`pxx --loop "<task>" --scope <path>` runs bounded edit→test→review→heal rounds autonomously. The loop ships as a tested feature and has been dogfooded on the pxx repo itself.

The verdict engine that governs each cycle is designed to **fail closed**:
- Unknown severity → REVISE (not APPROVE)
- Missing review evidence → NO_REVIEW (never silent approval)
- Near-miss / partial findings → UNPARSEABLE (surfaces for human review)

This means the loop will stop and ask rather than silently approve ambiguous results.

### Safety Design

- Ask mode default — nothing edits without `--edit` flag
- `--anywhere` flag allows one-shot trusted-path bypass with a session banner marking it as "untrusted path" (auditable)
- `PXX_AUTOCHECK_DRIFT=1` env var: automatically runs cross-machine drift check before every `--edit` session
- Git safety tags before each edit session for rollback
- Audit log of every session
- `~/.config/pxx/env` for machine-local config (fleet URLs, model IDs) — never in the repo; real env vars override

### Multi-Reviewer Code Review

pxx uses three AI CLI tools simultaneously for code review, each in its own working namespace:
- `../review/claude/` — Claude CLI
- `../review/gemini/` — Gemini CLI  
- `../review/codex/` — Codex CLI

Different reviewers excel at different failure modes; parallel review catches more than any single reviewer.

### Dogfooding Modes

- `pxx --self-test` — run pytest against pxx (690 tests as of 2026-06)
- `pxx --self-lint` — ruff check + format
- `pxx --self-improve` — ask-mode aider session suggesting improvements
- `pxx --self-fix "<task>" --scope X` — bounded autonomous edit
- `pxx --doctor` — pre-flight: 9router + agentmemory health checks, git-mirror sync validation; exits non-zero when out of sync

---

## Optional Services

**9router** — OpenAI-compatible proxy on `127.0.0.1:20128`. Routes to primary (Studio Ollama) with configurable fallback chains. Token tracking via `/v1/usage` endpoint. SSH tunnel to T5810 is kept alive by a macOS launchd plist (`deploy/launchd/local.pxx.t5810-vllm-tunnel.plist`), not a manual SSH command.

**agentmemory** — Observation storage API on `127.0.0.1:3111`. Also installable standalone as `pip install agentmemory` for use in other tools. SQLite backend. Network-boundary-as-auth design (LAN/VPN only; if the Studio moves to an untrusted network, remediation is `OLLAMA_HOST=127.0.0.1:11434`).

Both services are opt-in (`pxx --with-memory`, `pxx --with-router`) and auto-started by pxx's supervisor mode with exponential backoff retry logic on startup.

---

## Engineering Quality

**Test suite:** 690 tests as of June 2026, up from 357 at project start. 11 previously-lost test suites were recovered during a merge-loss incident, which surfaced a real index-vs-worktree secrets-scanner bypass bug that was subsequently fixed. A full-history `gitleaks` scan confirmed no credential leaks in the git history.

**Aider pin discipline:** aider is treated as a sensitive dependency, not a casually-bumped library. A 7-step documented upgrade checklist covers every specific CLI flag and semantic pxx depends on: `--chat-mode`, `--read`, `--config`, `--model-settings-file`, edit format, exit codes, and the `os.execv` boundary. aider releases weekly and minor versions have broken pxx behavior multiple times.

**Post-commit hook + staleness detection:** `pxx --install-hook` installs a post-commit hook that detects core-file staleness. The bash hook and `pxx/_core_files.py` share the same core-file list via `python3 -c` invocation so they can never drift. On every launch, `cli._emit_core_restart_banner()` warns if a core pxx file was edited since the last session.

**Plans as stable contracts:** `plans/backlog.md` tracks plans with stable numeric IDs, explicit Blocks/Blocked-by columns, and a rule that status must update in the same commit as the work.

---

## Python Stack

- Python 3.11+ (3.12 day-to-day)
- `aider-chat` (pinned — version-locked per upgrade checklist)
- `uv` for dependency management
- `ruff` for linting and formatting
- `pytest` (690 tests)

---

## What I Learned Building This

The interesting engineering problem was the memory system: making RAG useful for *short-horizon developer context* (what did I edit yesterday? what did aider try that didn't work?) rather than document retrieval. Hybrid BM25 + vector search outperforms either alone for code-adjacent text. The LRU cache layer above HNSW was a late addition that meaningfully reduced latency on the repeated query patterns that show up in long edit sessions.

The aider pin discipline was the other hard-won lesson. aider is excellent but changes behavior across minor releases in ways that break orchestrator assumptions at the `os.execv` boundary. Treating it like a library with a formal upgrade checklist, rather than a tool you casually `pip install --upgrade`, has prevented several debugging sessions that would have looked like pxx bugs but were actually aider behavior changes.

The autonomous loop verdict engine's fail-closed design came from a specific incident where an ambiguous review was silently approved and the resulting edit introduced a regression. "Unknown = reject" is the correct default for safety-gated autonomous code modification.
