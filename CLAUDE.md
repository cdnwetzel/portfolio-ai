# Portfolio AI Chat

A single-tenant **portfolio RAG chat** at [dev.cwetzel.com](https://dev.cwetzel.com): a React
frontend and a FastAPI proxy on an Ubuntu VPS, talking over an SSH tunnel to a **labrouter**
front-end that fans out to vLLM backends (**Qwen3.8-27B-FP8**, 32K context), Qdrant and a CPU
embedder on the T5810 in a home office, plus a GPU reranker and a faithfulness verifier on the
asrock B550.

> **Ground truth for the fleet lives on the T5810**, not here:
> `/home/chris/ai/inference/FLEET-ENDPOINTS.md` (topology, port contracts) and
> `MODEL-LEDGER.md` (which model holds which role, and why). This file describes how *cwdotcom*
> uses that fleet. When the two disagree, those files win — they are edited by the person
> changing the hardware. See also `plans/fleet-assessment-2026-08-30.md` for a verified snapshot.

It is a professional-portfolio showcase running on owned hardware (2x A4500 GPUs, ~400 Mbps
symmetric Verizon FIOS), not a revenue product. An earlier multi-tenant SaaS scope (tenants,
Postgres, JWT/API keys, Stripe billing) was **cut**: its code is on the `legacy/saas-scaffold`
branch and its design docs are in [`docs/archive/`](docs/archive/). Nothing in the running system
has a database, an account, or a tenant — so if you find `tenant_id` anywhere, it's archaeology.

**Status:** deployed and in production. Model is **Qwen3.8-27B-FP8** as of 2026-08-26 (see
`MODEL-LEDGER.md` on the T5810, which marks it FINAL for this role). Quality baseline re-measured
against it on 2026-08-29: graded eval PASSED, 32 grounded evals, **mean grounding 4.78**, 0 safety
hard-fails; consistency battery 7/7. Numbers predating the model change are void.

The 7-tier quality upgrade below is complete and still describes the software; the hardware and
model beneath it have since changed. All tiers live:
1. Credibility gates (6/6 passed), 2. 14B judge on RTX 5060 Ti (9/9 fixtures), 3. GPU reranker
(15.8x faster), 4. First-person voice & query routing, 5. UX polish (stop button, textarea, 
auto-scroll, sources readability), 6. KB expansion (indexer post-loading
bug fixed), 7. Ops maturity (incident runbook, deploy-stamped version endpoint; **verdicts.db backups
and the weekly digest were written but are NOT scheduled — see DEFECT_LEDGER #4**). Self-test gate passing. Health monitoring active.
Continuous improvement: weekly flagged-queue review + defect ledger (DEFECT_LEDGER.md).

## Core Architecture

```
User Browser
    ↓ HTTPS / WSS
cwetzel.com Cloud Server (Ubuntu VPS)
├─ Apache (SSL termination, reverse proxy, WSS)
├─ FastAPI API proxy (port 8000, systemd: api-proxy.service)
└─ Static React build (/var/www/dev.cwetzel.com/) — Tier 5 UX: stop button, textarea, auto-scroll
    ↓ [SSH tunnel — portfolio-ai-tunnel.service, initiated by the VPS]
T5810 Home Server / precision-t5810 (Gentoo/OpenRC) — 2x RTX A4500 NVLink, 256 GB RAM
├─ labrouter (port 8004, loopback) — **THE STABLE CONTRACT PORT.** The tunnel forwards
│  │  this and only this for generation. Models are swapped BEHIND it, so changing a
│  │  model never touches the VPS. Never bind a model directly on 8004.
│  └─ routes to vLLM backend slots:
│     ├─ :8007 — Qwen3.8-27B-FP8, 32K ctx, TP=2  ← what cwdotcom uses (MODEL_ID)
│     ├─ :8008 — Qwen3.6-35B-A3B-FP8   (slot defined; not running)
│     └─ :8009 — pscode-14b            (slot defined; not running)
├─ Qdrant (port 6333) — dense 768-d cosine. Live counts: `/api/system-info`, which reads
│  them from the collection. Deliberately not written here — see the note below.
├─ Embedding service (port 8005) — BAAI/bge-base-en-v1.5, 768-d, CPU
└─ compress service (port 8788) — token compression (COMPRESS_URL)
    ↓ tunnel also forwards :8016 → asrock:8006 (GPU reranker) and :8007 → asrock (verifier)
asrock B550 (Gentoo/OpenRC) — RTX 5060 Ti 16 GB, 64 GB RAM
├─ Reranker service (port 8006, GPU) — bge-reranker-base, 15.8x faster than CPU
├─ Faithfulness verifier (port 8007) — Qwen2.5-14B-Instruct via Ollama
└─ Ollama (11434) — judge backend + other lab models
```

**Port-numbering trap:** vLLM's backend slot on the T5810 is `:8007`, and the *verifier* on the
asrock is also `:8007`. They are different hosts. The VPS's `:8007` is the **verifier** (the
tunnel maps it to `asrock:8007`); the VPS reaches generation only via `:8004` → labrouter.

**RAG pipeline:** query → alias-expand → embed (8005, bge-base 768-d) → Qdrant cosine top-15 →
rerank to top-5 (via VPS :8016 → asrock:8006, GPU cross-encoder, ≤2 chunks/doc) → fit to token
budget → labrouter :8004 → vLLM stream → (out-of-band) fire-and-forget faithfulness verify (8007).

The reranker adds precision the bi-encoder can't: cosine surfaces candidates, the cross-encoder
picks the best 5. It **fails open** to cosine top-5 if the reranker is down, and the verifier is
fully fail-open (chat is unaffected if asrock is down). Failing open is the right behaviour and
also the reason both can vanish unnoticed — see the supervision note below.

**The proxy pins the model server-side** (`MODEL_ID`, default `qwen3.8-27b`) and ignores whatever
`model` the browser sends. The client used to choose it, so renaming a model on the T5810 took the
whole site down while `/health` stayed green (2026-08-29). A client must never select the backend
model. `DISABLE_THINKING=1` also strips chain-of-thought: Qwen3.8 is a reasoning build that spends
the whole `max_tokens` budget thinking and returns empty `content` on long answers otherwise.

**Every service on the critical path must be supervised, unlimited-respawn, and logged.** Four
separate incidents in one week traced to the same root: `respawn_max=N` latches a service OFF
permanently after a transient squeeze, and a unit with no `output_log` leaves nothing behind to
diagnose. `respawn_max=0` everywhere. vLLM additionally needs an orphan reaper — its TP workers are
separate processes that survive the API server and hold ~19 GB of VRAM each, which deadlocks
restarts. See `home/vllm-service/` and `plans/fleet-assessment-2026-08-30.md` §3.

**Query routing** (`cloud/query_router.py`) runs before retrieval: `meta` and `off_topic` return
instant canned responses with no GPU call, everything else goes to full RAG. Its default is
`on_topic` **by design** — the router is a cost optimization, not a grounding gate, and inverting
that assumption is what caused it to deflect a third of the golden set (DEFECT_LEDGER #6). Grounding
is enforced by `RAG_MIN_SCORE`; adversarial input by the guardrail below. Both run independently of
the router. Every canned path carries a `FOLLOWUPS` block so it renders suggestion chips instead of
being a dead end.

`/ws/chat` is limited to **2 concurrent connections per IP** (`cloud/rate_limit.py`). Not 1: the
client opens the next turn's socket before the previous close is processed, and a limit of 1
rejected real users' own follow-ups with a 429 the browser shows as "Connection lost"
(DEFECT_LEDGER #7). Relatedly, the `done` frame carries `verify` — the client must only hold the
socket open for a verdict when one is actually coming.

A deterministic **prompt-extraction guardrail** (`cloud/guardrails.py`) refuses
"reveal/repeat your prompt"-style attacks before they reach the LLM. A **graded eval**
(`scripts/eval_graded.py` + `eval/golden_set.yaml`) gates changes. A **hybrid dense+BM25** path
exists (`HYBRID_SEARCH`) but is **OFF** — an A/B showed it regressed on this small KB (4.41 vs 4.82).

**"More retrieval" has now lost three A/Bs in a row on this KB.** Hybrid dense+BM25 (4.41 vs
4.82), `chunk_size=250` (19/20 vs 20/20), and — measured 2026-09-01 — wider retrieval:
`RAG_TOP_K` 5→8 with `MAX_CONTEXT_TOKENS` 14384→28000 moved mean grounding 4.594 → 4.656,
which a paired test over the same 32 questions calls noise (**t(31)=0.70**, 95 % CI
**[-0.12, +0.24]**, 24/32 rows scored identically) while costing **+6 % latency**. Reverted.
On a corpus this size the reranked top-5 already carries the answer; candidates 6-8 add
tokens, not evidence. Details in `plans/ups-sizing-2026-09-01.md` §5. **Do not reopen without
a hypothesis about what the pipeline is actually missing** — "try a bigger number" is
measured and settled.

### Known characteristic: the reranker truncates (real, but not worth fixing — A/B'd)

`bge-reranker-base` caps each (query, chunk) pair at **512 tokens** — an XLM-RoBERTa
`max_position_embeddings=514` limit, not a tunable. Measured 2026-08 on the 62 chunks live at
the time: median **662**
tokens, so **71%** are scored on part of their text. It affects **ranking only**:
`rerank_documents()` returns indices and the caller re-reads the full payload (`api-proxy.py:234`),
so the LLM always receives whole chunks.

The truncation is *not* cosmetic — a head/tail probe (score each over-budget chunk's kept head vs
its discarded tail against the query) found **23%** of long chunks carry stronger signal in the
tail that truncation throws away, sometimes starkly (head 0.02 / tail 0.95). So individual-chunk
ranking is genuinely distorted.

**But fixing it is net-negative, measured by a real A/B.** A parallel `documents_c250` collection
at `chunk_size=250` cut truncation 71% → 9%, yet through the full embed→search→rerank→cap pipeline
(`scripts/compare_retrieval.py`) it did *not* improve recall of the golden set's `expect_substrings`:
20/20 → **19/20** at top-5, because smaller chunks (a) halve the evidence the generator receives
(11,549 → 6,017 median chars, since `RAG_TOP_K` is a fixed *count* of chunks) and (b) fragment
multi-part facts across chunks (0 → 3 questions split). The ranking gain is real but the fact still
reaches the generator via the per-doc cap on the larger chunks, so at the system level it's a wash
trending slightly worse. A `v2-m3` reranker upgrade (bigger window) would likewise add latency we
now print under every answer, for a ranking fix that doesn't move answers. **Declined on evidence.**
Do not reopen without a metric that beats 20/20 end-to-end.

Separately: the earlier single miss was the **per-doc cap**, not truncation. For the AVD question
the rank-3 chunk had "AVD" in its first 498 tokens but was discarded because rank-1 came from the
same doc. **`RAG_MAX_PER_DOC` is now 2** (env-overridable), which gives 20/20 at ~zero evidence cost.

## Key Features

- **Grounded answers** — every claim comes from the retrieved KB; the model says "I don't have that
  documented" rather than inventing, and the UI shows the exact source chunks it used.
- **Owned GPU inference** — vLLM on 2x A4500s with tensor parallelism. Zero cloud GPU cost.
- **Edge/compute split** — cloud frontend for latency, home GPUs for compute, joined by one SSH tunnel.
- **Out-of-band faithfulness verification** — an independent 14B-Instruct judge on a separate machine grades
  whether an answer's claims are grounded, without ever blocking the response.
- **Per-message telemetry** — time-to-first-token, decode throughput and total latency under each
  answer (metadata only, never content).
- **Regression-gated** — graded eval, plus a live self-test that `cloud/deploy.sh` runs before it
  finishes.
- **Monitored** — a 5-minute VPS health aggregator (`scripts/health_aggregate.py`) probing proxy,
  labrouter/vLLM, Qdrant `points_count`, embed, rerank and verifier, plus a real end-to-end WS
  query throttled to every 30 min (`SMOKE_INTERVAL_SEC`), an external healthchecks.io dead-man's
  switch, and ntfy paging on severity **transitions** only.

  Two things worth knowing. The E2E probe **works** — it caught the 2026-08-26 vLLM outage and
  paged `[urgent] Portfolio AI DOWN` on Aug 27 and Aug 28 with the message "outage signature". The
  gap was that nobody acted on it, and that it ran only once a day because the 5-min unit was
  launched with `--no-smoke`. Detection latency is now ≤30 min. **A "30-minute T5810 canary" is
  documented in a few places and does not exist** — not in any runlevel, no cron entry. Do not
  count it as coverage.

## Directory Structure

```
cwdotcom/
├── .github/workflows/ci.yml    # CI: offline unit tests + frontend build (deliberately no deploy)
├── cloud/                      # FastAPI proxy — deployed to the VPS
│   ├── api-proxy.py            # WS chat, /api/search, /api/retrieve, RAG orchestration
│   ├── guardrails.py           # prompt-extraction refusal (pre-LLM, deterministic)
│   ├── context_manager.py      # prompt/history caps + token-budget context fitting
│   ├── query_expansion.py      # curated alias expansion
│   ├── sparse_bm25.py          # BM25 for the (disabled) hybrid path
│   ├── systemd/                # api-proxy, tunnel, health timers
│   └── deploy.sh               # the real deploy: build → rsync → restart → self-test gate
├── home/                       # services that run on the GPU / LAN boxes
│   ├── embed-service/          # bge-base-en-v1.5, CPU, port 8005
│   ├── rerank-service/         # bge-reranker-base, CPU, port 8006
│   ├── verifier-service/       # faithfulness judge (asrock), port 8007
│   └── qdrant/                 # OpenRC unit for Qdrant
├── frontend/                   # React + Vite + Tailwind; built and rsync'd
├── scripts/                    # indexer, graded eval, self-test, health aggregator
├── knowledge_base/             # the indexed corpus (resume, case studies, posts, infra)
├── eval/golden_set.yaml        # graded-eval questions
├── integrations/mcp/           # MCP server exposing this RAG to an external agent
├── tests/                      # offline unit tests (stdlib-only modules)
├── plans/                      # design docs, for work done and work proposed
└── docs/archive/               # the scoped-out SaaS design docs
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **GPU inference** | vLLM 0.27.1 + Qwen3.8-27B-FP8 (32K ctx) | LLM serving on 2x A4500s (T5810), behind labrouter :8004 |
| **API framework** | FastAPI + Uvicorn | Async Python proxy (cloud server) |
| **Vector DB** | Qdrant | Dense cosine retrieval, top-15 candidates |
| **Embeddings** | BAAI/bge-base-en-v1.5 (768-d) | Query/document → vector (CPU, port 8005) |
| **Reranker** | bge-reranker-base | Cross-encoder precision, top-15 → top-5 (GPU RTX 5060 Ti on asrock, 15.8x faster) |
| **Faithfulness verifier** | Qwen2.5-14B-Instruct via Ollama (RTX 5060 Ti) | Out-of-band claim grounding (asrock, port 8007) |
| **Eval / guardrail** | graded eval + golden set; prompt-extraction guardrail | Regression gate + pre-LLM refusal |
| **Frontend** | React + Vite + Tailwind | Built + rsynced to dev.cwetzel.com |
| **Reverse proxy** | Apache | SSL termination, static serving, WSS proxy |
| **Networking** | SSH tunnel | VPS → T5810 → asrock (services stay LAN-only) |
| **Chat history** | Browser localStorage | Per-browser; cleared by the header's "New chat" button. Nothing server-side |

## Endpoints

The proxy exposes four routes. There is no auth layer — the chat is public and anonymous.

| Method | Endpoint | Purpose |
|--------|----------|---------|
| **GET** | `/health` | Liveness, for the health aggregator |
| **POST** | `/api/search` | Debug: retrieve chunks for a query |
| **POST** | `/api/retrieve` | Text-in / chunks-out seam (used by the MCP server) |
| **WS** | `/ws/chat` | Stream a grounded answer, then source + timing metadata |

## Actual Deployment Config

**On the T5810 (Gentoo/OpenRC):**
```bash
# vLLM backend slot — OpenRC: vllm-qwen38
#   unit     /etc/init.d/vllm-qwen38      (repo: home/vllm-service/vllm-qwen38.openrc)
#   config   /etc/conf.d/vllm-qwen38      (repo: home/vllm-service/conf.d-vllm-qwen38)
#   launcher /opt/vllm-service/start-qwen38.sh
# The old `pscode-vllm` / `/etc/init.d/vllm` unit is RETIRED — it pointed at a deleted
# venv, the wrong model, and --port 8004, which would have stolen labrouter's contract
# port. Backup at /root/init.d-vllm.retired-20260830.bak.
VLLM_MODEL=/data/models/Qwen3.8-27B-FP8
VLLM_SERVED_NAME=qwen3.8-27b     # labrouter routes to this id; the proxy pins the same
                                 # string via MODEL_ID. Change it here and you must change
                                 # it in BOTH places.
VLLM_PORT=8007                   # backend slot. NEVER 8004 — unit and launcher refuse it.
VLLM_TP=2
VLLM_UTIL=0.93                   # 0.95 OOMs on this box
VLLM_CTX=32768

# *** DO NOT CHANGE THESE THREE WITHOUT RE-BENCHMARKING — they are the 4.4x. ***
# Measured: eager 6.2 tok/s -> CUDA graphs on 27.7 tok/s
# (../psaios/docs/t5810-vllm-cudagraph-tuning-2026-08-19.md). Losing any one is SILENT:
# the server still answers, just ~4x slower, and no health check notices.
#   1. CUDA graphs ON        (i.e. NO --enforce-eager)
#   2. --disable-custom-all-reduce   custom AR breaks graph capture on this A4500 pair
VLLM_CUDAGRAPH_SIZES=[1,2,4,8]   # 3. vLLM captures ~70 sizes by default; capture memory
                                 #    scales with the count, which is what OOMed before
CUDAHOSTCXX=/usr/bin/g++-14      # Gentoo ships gcc 15; CUDA hard-fails above 14 and
                                 # flashinfer JIT-compiles at engine init
# Verify after any restart:  /opt/vllm-service/bench-vllm.sh 8007 3   -> expect ~27-30 tok/s

# labrouter (OpenRC: labrouter) — :8004, the contract port. Supervised since 2026-08-31
# (supervise-daemon, respawn_max=0); validates labrouter.yaml before start and waits
# for /health. `rc-service labrouter reload` SIGHUPs config only, never code.
# Qdrant (OpenRC) 6333, embed-service 8005 (bge-base, CPU), compress 8788
QDRANT_PORT=6333
```

**On the asrock B550 (Gentoo/OpenRC):**
```bash
# Reranker (Tier 3: moved from T5810 CPU → RTX 5060 Ti GPU, 15.8x faster)
RERANK_DEVICE=cuda
RERANK_BIND=10.0.1.115            # LAN IP; tunneled to VPS as port 8016
RERANK_PORT=8006

# Faithfulness verifier (Tier 2: 14B-Instruct judge, RTX 5060 Ti)
VERIFIER_PORT=8007
JUDGE_MODEL=qwen2.5:14b-instruct-q4_k_m  # independent variant of the 14B-Coder (echo-bias mitigation)
JUDGE_NUM_CTX=16384                      # ollama defaults to 4096 and truncates silently
OLLAMA_CONTEXT_LENGTH=16384              # lockstep with JUDGE_NUM_CTX (ollama-side window)
JUDGE_KEEP_ALIVE=30m                     # ollama evicts idle models after 5m

# GPU VRAM allocation: Reranker ~1.3GB + Judge ~11.7GB = ~13GB / 16GB (87% util, 3GB headroom)
```

**On the cloud server (cwetzel.com):**
```bash
# API proxy (systemd: api-proxy.service; Apache terminates SSL/WSS in front)
VLLM_URL=http://127.0.0.1:8004      # via SSH tunnel -> T5810 labrouter (NOT vLLM directly)
MODEL_ID=qwen3.8-27b                # pinned server-side; client-supplied model is ignored
DISABLE_THINKING=1                  # strip CoT: reasoning builds spend max_tokens thinking
                                    # and return empty content on long answers
QDRANT_URL=http://127.0.0.1:6333    # via SSH tunnel to T5810
EMBED_URL=http://127.0.0.1:8005     # via SSH tunnel to T5810
RERANK_URL=http://127.0.0.1:8016    # via SSH tunnel (T5810 forwards 8016 → asrock:8006, GPU)
VERIFIER_URL=http://127.0.0.1:8007  # via SSH tunnel (T5810 forwards 8007 → asrock:8007)
VERIFY_MIN_SCORE=0.002              # skip the verifier when top rerank score < this (off-topic gate,
                                    # verify_gate.py). Calibrated 2026-07-14: off-topic clusters at ~0,
                                    # on-topic ≥0.0046. Code default 0.0 (disabled); enabled via env here.
HYBRID_SEARCH=0                     # hybrid dense+BM25 built but OFF (lost its A/B)
```

**SSH tunnel (single connection, VPS → T5810, with the T5810 as jump host to asrock):**
Forwards to T5810 (8004 vLLM, 8005 embed, 6333 Qdrant) plus **8016 → asrock:8006** (GPU reranker, Tier 3, 15.8x faster) and **8007 → asrock:8007** (verifier, Tier 2) routed over home LAN. Managed by
`portfolio-ai-tunnel.service` (systemd on the VPS). Single persistent connection; if down, 
degraded mode: reranker fails open to cosine top-5, verifier is fully fail-open.

## Working On This Repo

**Constraints that bind.** `red-lines.md` and `invariants.md` govern the running system and are
cited from live code. The one that catches people: **never log query or response content** —
metadata only (`red-lines.md` #2). Where `.cursorrules` and `red-lines.md` disagree, red-lines wins.

**Do not write KB doc/chunk counts into this file.** It has carried four different chunk
counts (94, 94, 99, 62) and two doc counts (34, 35) simultaneously, all stale, because a
reindex changes them and nothing updates prose. `/api/system-info` reads the count live from
the Qdrant collection, so it cannot drift; quote that, or quote a number *with the date it was
measured*. The same rule killed the golden-set size in the KB, which had drifted through ~30,
35 and 42.

**The knowledge base must not contain real internal IP addresses.** Public hostnames are fine.

**PII policy (red-lines.md #6):** the contact emails in the KB (`cwe@thepslawfirm.com`,
`chris@cwetzel.com` in `RESUME.md`) are indexed **intentionally** — public contact info, the
right vector for professional inquiries. Phone numbers, SSNs, private addresses and any third
party's personal data are excluded. If PII is ever indexed, the red-line must document why.

**Retrieval returns ≤2 chunks per source doc** (`RAG_MAX_PER_DOC`, env-overridable). A fact isolated
in one chunk may still not surface for a differently-phrased query, so put a corrected fact in the
chunk whose topic matches the likely question — or duplicate it — and verify live with several
phrasings.

**Don't hand-patch the Qdrant index.** Rebuild it from the committed KB with `./scripts/reindex_kb.sh`.

**Production actions need explicit authorization** — `cloud/deploy.sh`, `scripts/reindex_kb.sh`, and
any vLLM change. CI deliberately does not deploy.

## Commands

```bash
# Offline unit tests — stdlib-only modules, no live stack needed (this is what CI runs)
python3 -m pytest tests/ home/verifier-service/test_verifier_core.py -v

# Frontend dev server (proxies /ws and /api to localhost:8000)
cd frontend && npm install && npm run dev

# Full-stack integration test — needs the live stack (proxy, vLLM, Qdrant, embed)
python3 test_rag_system.py

# Graded eval against the golden set (regression gate)
python3 scripts/eval_graded.py

# Deploy: build → rsync → restart → live self-test gate. Requires authorization.
./cloud/deploy.sh

# Rebuild the Qdrant index from the committed KB. Requires authorization.
./scripts/reindex_kb.sh
```

## Further Reading

- **Architecture (current):** this file, plus [`README.md`](README.md)
- **Deploy / operate:** [`DEPLOYMENT.md`](DEPLOYMENT.md), [`OPERATIONS.md`](OPERATIONS.md)
- **Constraints:** [`red-lines.md`](red-lines.md), [`invariants.md`](invariants.md)
- **Design docs:** [`plans/`](plans/)
- **Test plan:** [`docs/03-test-plan.md`](docs/03-test-plan.md)
- **Historical planning:** [`docs/02-architecture.md`](docs/02-architecture.md) — the Gate-1 design.
  It specifies WireGuard and Llama 2 70B; what shipped is an SSH tunnel and Qwen2.5-Coder-14B.
- **The SaaS that wasn't:** [`docs/archive/`](docs/archive/)

---

## Documentation Alignment

Docs here describe reality, not aspiration. That took deliberate correction, and the corrections are
worth remembering:

- **2026-06-10** — Aligned docs with the deployed system: React Vite build replaced standalone HTML;
  the model is Qwen2.5-Coder-14B-Pscode (never Llama 2 70B); removed multi-tenant references.
- **2026-07-10** — Removed the fictional CI (a workflow that rsync'd deleted `src/`), corrected the
  README's embedder (`all-MiniLM-L6-v2` → `bge-base-en-v1.5`, 384-d → 768-d) and reverse proxy
  (Nginx → Apache), rewrote `requirements.txt` to what the code imports (it had listed Stripe,
  SQLAlchemy, Alembic, Redis), archived the SaaS design docs, and reconciled `.cursorrules` with
  `red-lines.md` — it had instructed agents to log query text.
- **2026-08-03** — Updated architecture after Tier 3 (GPU reranker moved T5810 CPU → asrock RTX 5060 Ti,
  15.8x faster at 259ms) and Tier 5 (UX polish: stop button, textarea, auto-scroll, sources readability).
  All 5 tiers live. Self-test gate passing. Health monitoring active with baselines established.
- **2026-08-31** — Rewrote the architecture from a live audit after the fleet changed underneath
  the docs. This file had been wrong about the model (Qwen2.5-Coder-14B + pscode LoRA →
  **Qwen3.8-27B-FP8**), the context window (16K → **32K**), what `:8004` is (**labrouter**, not
  vLLM — vLLM backends are 8007/8008/8009), the reranker's location, and it omitted labrouter and
  the compress service entirely. Fleet ground truth now lives in `FLEET-ENDPOINTS.md` /
  `MODEL-LEDGER.md` **on the T5810**; this file defers to them. Full verified snapshot:
  `plans/fleet-assessment-2026-08-30.md`.
- **2026-08-19** — Corrected a claim this file made by implication. The "20/20 end-to-end" figure
  below is a *retrieval* measurement (`compare_retrieval.py`) and never invokes the query router.
  The router was meanwhile defaulting to `off_topic`, deflecting **13 of 40 golden-set `grounded`
  questions** with a canned redirect — a routing bug that no retrieval metric could see. Default is
  now `on_topic`, with grounding left to `RAG_MIN_SCORE` where it always was. See DEFECT_LEDGER #6–8.

**When you change the system, change the docs in the same commit.** A wrong doc is worse than a
missing one: it is confidently wrong, and it survives long after the person who knew better moved on.
