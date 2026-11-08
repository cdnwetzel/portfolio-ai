# pxx — Local-First AI Coding-Agent Runtime

## What It Is

`pxx` is an open-source AI coding-agent runtime I built and maintain. It runs against **your own
inference** — Ollama, vLLM, or any OpenAI-compatible endpoint — with no cloud dependency, no
telemetry and no API keys required. Since version 2.0 it is an **async, event-sourced runtime in
which pxx owns the agent loop**: a native tool-calling loop with persistent cross-session memory,
deterministic safety gates, a hash-chained audit log and MCP interop. It can delegate edits to
[aider](https://github.com/Aider-AI/aider) as an *optional* backend.

- **Repo:** https://github.com/cdnwetzel/pxx (default branch `v2`; the 1.x line is on `v1.x`)
- **Install:** `pip install pxx-orchestrator` — the command is `pxx`
- **License:** MIT
- **Current release:** **2.9.3** (2026-10-18), the latest on GitHub and PyPI
- **Pace:** 2.0.0 shipped 2026-07-17; **43 tagged 2.x releases** on GitHub through 2.9.3
- **Tests:** **1,863** collected on the default branch at commit 5be59d5 (2026-10-26, still
  versioned 2.9.3); **1,746** at the `v2.9.3` tag itself. Counted 2026-11-08 with
  `pytest --collect-only` on clean copies of the public repo. The README's "870+" is an old figure.
- **Size:** the `pxx/` Python package is about 22,800 lines (counted with `wc -l`, 2026-11-08)
- Solo-maintained. The public history is a curated series; full development history is private.

---

## Who It's For

pxx is built for environments where **code and inference can't leave the operator's perimeter** —
regulated, air-gapped, IP-sensitive or sovereignty-required work — and where every action an agent
takes has to be auditable. Its README is explicit that running locally is *not* unique (aider and
opencode run locally too); what pxx adds sits above the model:

- **Host-enforced, not model-trusted.** Scope, permissions, budgets and hooks are enforced by the
  host process, so a jailbroken or confused model still cannot write outside the allowed files.
  It is defense in depth *inside* your own isolation, not a replacement for it.
- **Open and inspectable.** MIT-licensed: read every gate, fork it, harden it to your own
  compliance regime.
- **Evidence-gated.** Every capability claim maps to a dated, reproducible record — with an
  explicit statement of what is *not* claimed — in `docs/RECEIPTS.md` (50 receipts as of 2.9.3).

It is deliberately not for every environment: where SaaS is allowed, a hosted frontier agent will do
more; pxx has no browser and leans on smaller local models, trading breadth for sovereignty and
auditability.

---

## How It Works

- **Two execution backends, chosen per run.** *native* — pxx drives the model directly through its
  own tool surface and gates; *aider* — edits are delegated to aider, still under pxx's scope,
  budget and hook gates. `pxx loop` and `pxx run` default to native.
- **Permission modes:** ask (read-only, the default) → plan → edit (writes in scope) → auto
  (unattended, budget-capped). Shell commands are gated in every write-capable mode: they need a
  hook, the shell sandbox, or an explicit opt-in, even in unattended mode.
- **Every run is bounded:** max rounds, tokens, cost, wall-clock time and diff lines.
- **Bounded edit→test→review loop** (`pxx loop`) stops on round cap, diff cap, budget, scope
  violation, non-improving test results (`NO_TEST_PROGRESS`), detected oscillation
  (`LOOP_DETECTED`), or a blocking review verdict.
- **Persistent memory:** a local SQLite store with hybrid search (FTS5 BM25 0.4 + embedding cosine
  0.6). Embeddings come from a local Ollama model when reachable, else a deterministic hash
  embedder, so search always works offline. Memory is project-scoped and is **context, never
  policy**. It is exposed to other agents (Claude Code, goose, opencode) as an MCP server.
- **MCP both ways:** pxx consumes MCP servers as tools and serves its own memory over MCP.
- **Headless API:** `pxx serve` — FastAPI with sessions, an SSE event stream and cancel;
  loopback-only by default.
- **Default model:** `qwen2.5-coder:7b` via Ollama; configurable, with fallback chains to vLLM or
  other OpenAI-compatible endpoints.

## Safety Model

- Before an edit-capable session writes anything, pxx stashes uncommitted work (including
  untracked files) and tags HEAD `pxx-pre/<timestamp>`; undo is `git reset --hard <tag>`.
- Paths are canonicalized with symlinks resolved before any gate decision — model output never
  defines the trust boundary.
- Hooks are deterministic gates (like Claude Code's PreToolUse) that model judgment cannot override.
- The audit log is **hash-chained and metadata-only** (no prompts, file contents or secrets) and is
  verifiable with `pxx audit verify`.
- Unknown config keys are rejected (fail-closed, no silent typos).
- Operator commands include a secret/PII scan (`pxx check`), a read-only diff review (`pxx review`)
  and setup diagnostics (`pxx doctor`).

## Self-Improvement, Gated

pxx includes an evaluation and improvement platform — `pxx eval`, `calibrate`, `improve`,
`compare`, `promote` — where improvement candidates are evaluated on held-out tasks and
**promotion is human-gated**. The improve daemon runs hourly and is propose-only. A dogfood run
confirmed the autonomous loop **cannot modify pxx's own protected control plane** (receipt R-014).

## Selected Receipts (from `docs/RECEIPTS.md`)

- **R-001 / R-048:** the hands-on tutorial completes 6/6 on 8 GB consumer hardware, and verbatim
  from PyPI on 2.9.0 across three setups from 8 GB to a GPU gateway.
- **R-011:** a true two-box run — GPU-box coder plus a Mac judge in one autonomous loop.
- **R-032:** an autonomous local loop builds a real feature that lands on a live production server.
- **R-034:** pxx fixes a bug in its own source in a fully local autonomous edit.
- **R-035 – R-040:** n8n orchestrates governed, audited pxx runs over the HTTP API — routing on
  terminal codes, a governed autonomous GitHub PR behind human approval, and parallel fan-out.
- **R-036, R-044 – R-046:** a fail-closed remote human-in-the-loop gate — a Slack approve/modify
  card releases a blocked pxx tool call over Socket Mode, with no public endpoint.
- **R-041 – R-043:** measured on the home GPU fleet — VRAM capacity beats GPU generation, dual-GPU
  NVLink makes fan-out real (198% at N=2), and throughput tracks *active* parameters.
- **R-047:** external AI reviewers measured against pxx's own calibration bar.
- **R-049 / R-050:** two prompt changes that **failed** their pre-registered bars and were not
  shipped — recorded as non-results.

---

## History: pxx 1.x (May – July 2026)

pxx started on 2026-05-10 as an **orchestrator around aider**: it detected which LLM endpoint was
reachable (Mac Studio Ollama, then the T5810's vLLM over an SSH tunnel), set up the session, and then
handed off to aider with `os.execv`. Around it sat optional sidecar services — **agentmemory** (an
observation store with hybrid BM25 + vector search), **9router** (an OpenAI-compatible proxy with
token tracking) and **docs-rag-sme** — plus a `--loop/--heal` autonomous mode, `--self-test` /
`--doctor` style flags, cross-machine drift checks, and a 7-step checklist for upgrading the pinned
aider dependency, whose minor releases had broken the `os.execv` boundary more than once. The 1.x
default model was `devstral:24b` on the Mac Studio (M4 Max, 36 GB). Tests grew from 357 at the start
to 690 in June 2026.

The 1.x agentmemory service stored observations in SQLite with 384-dimension sentence-transformers
vectors and an HNSW index (documented at ~5 ms retrieval at 100k+ observations), an LRU cache above
it for repeated queries, JSONL archiving on a 90-day TTL with per-project overrides, and in-session
`/recall`, `/remember` and `/forget` commands. Other 1.x practices: a post-commit hook that warned when
a core pxx file had changed since the last session, and a backlog with stable plan IDs whose status
had to change in the same commit as the work.

pxx 2.0 is a ground-up rewrite. It **kept the 1.x control-plane semantics** — fail-closed gates,
scope limits, bounded loops, audit — and **replaced the execution layer**: no more `os.execv` into
aider, argv scanning or sidecar services. Memory and routing moved in-process, and docs/tools moved
to MCP (`docs/MIGRATION.md`). The memory service was never published as a standalone package.

Lessons carried forward from 1.x:
- **Fail closed on ambiguity.** The 1.x loop's verdict engine treated unknown severity as REVISE and
  missing review evidence as NO_REVIEW, after an ambiguous review was once silently approved and
  introduced a regression. "Unknown = reject" remains the rule in 2.x.
- **Treat the edit engine as a sensitive dependency.** The aider pin discipline is why 2.x owns the
  loop itself and makes aider optional.
- **Multi-reviewer review.** pxx's code was reviewed in parallel by Claude, Gemini and Codex CLIs,
  each in its own namespace, because different reviewers catch different failure modes.
- **Recovering lost test suites** during a merge-loss incident surfaced a real index-vs-worktree
  secrets-scanner bypass, which was fixed; a full-history `gitleaks` scan found no leaked credentials.
