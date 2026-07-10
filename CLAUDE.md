# Portfolio AI Chat

A single-tenant **portfolio RAG chat** at [dev.cwetzel.com](https://dev.cwetzel.com): a React
frontend and a FastAPI proxy on an Ubuntu VPS, talking over an SSH tunnel to vLLM
(Qwen2.5-Coder-14B + pscode LoRA), Qdrant, a CPU embedder and a CPU reranker on a T5810 in a home
office, plus a faithfulness verifier on a second home box.

It is a professional-portfolio showcase running on owned hardware (2x A4500 GPUs, ~400 Mbps
symmetric Verizon FIOS), not a revenue product. An earlier multi-tenant SaaS scope (tenants,
Postgres, JWT/API keys, Stripe billing) was **cut**: its code is on the `legacy/saas-scaffold`
branch and its design docs are in [`docs/archive/`](docs/archive/). Nothing in the running system
has a database, an account, or a tenant — so if you find `tenant_id` anywhere, it's archaeology.

**Status:** deployed and in production, on the psplan 5-Gate workflow — Gate 0 (charter, vision,
red-lines, invariants) through Gate 5 (monitoring, closure) are complete for the current scope.

## Core Architecture

```
User Browser
    ↓ HTTPS / WSS
cwetzel.com Cloud Server (Ubuntu VPS)
├─ Apache (SSL termination, reverse proxy, WSS)
├─ FastAPI API proxy (port 8000, systemd: api-proxy.service)
└─ Static React build (/var/www/dev.cwetzel.com/)
    ↓ [SSH tunnel — portfolio-ai-tunnel.service, initiated by the VPS]
T5810 Home Server (Gentoo/OpenRC)
├─ vLLM (port 8004, LAN-only) — Qwen2.5-Coder-14B-Pscode, BF16, 16K context
│  └─ 2x RTX A4500, NVLink, tensor parallel
├─ Qdrant (port 6333) — dense 768-d cosine
├─ Embedding service (port 8005) — BAAI/bge-base-en-v1.5, CPU
├─ Reranker service (port 8006) — bge-reranker-base, CPU
└─ Knowledge base (indexed docs)
    ↓ the same tunnel forwards :8007 → asrock B550 over the home LAN
asrock B550 (Gentoo/OpenRC)
└─ Faithfulness verifier (port 8007) — Qwen2.5-7B via Ollama, RTX 3060 Ti
```

**RAG pipeline:** query → alias-expand → embed (8005, bge-base 768-d) → Qdrant cosine top-15 →
rerank to top-5 (8006, CPU cross-encoder, ≤2 chunks/doc) → fit to token budget → vLLM stream →
(out-of-band) fire-and-forget faithfulness verify (8007).

The reranker adds precision the bi-encoder can't: cosine surfaces candidates, the cross-encoder
picks the best 5. It runs CPU-only on the T5810's idle 256 GB DDR4, so it never contends with vLLM
for VRAM. It **fails open** to cosine top-5 if the reranker is down; the verifier is fully fail-open
(chat is unaffected if asrock is down).

A deterministic **prompt-extraction guardrail** (`cloud/guardrails.py`) refuses
"reveal/repeat your prompt"-style attacks before they reach the LLM. A **graded eval**
(`scripts/eval_graded.py` + `eval/golden_set.yaml`) gates changes. A **hybrid dense+BM25** path
exists (`HYBRID_SEARCH`) but is **OFF** — an A/B showed it regressed on this small KB (4.41 vs 4.82).

### Known characteristic: the reranker truncates (measured, and it does not matter)

`bge-reranker-base` caps each (query, chunk) pair at **512 tokens** — an XLM-RoBERTa
`max_position_embeddings=514` limit, not a tunable. The indexed corpus is 19 docs → 67 chunks
(62 live Qdrant points), median **668** tokens, so **71.6%** are scored on part of their text.

It affects **ranking only**: `rerank_documents()` returns indices and the caller re-reads the full
payload (`api-proxy.py:234`), so the LLM always receives whole chunks.

**It costs nothing measurable.** `scripts/compare_retrieval.py` scores the golden set's
`expect_substrings` through the real pipeline: **19/20** at top-5 and **19/20** at top-8 — raising
`top_k` recovers zero questions. So a `v2-m3` upgrade would buy latency we now print under every
answer, for noise. Declined on evidence, as with hybrid BM25. Do not reopen without new data.

The single retrieval miss was caused by **the per-doc cap**, not truncation: for the AVD question
the rank-3 chunk contains "AVD" inside its first 498 tokens but was discarded because rank-1 came
from the same doc. **`RAG_MAX_PER_DOC` is now 2** (was 1), which gives 20/20 at ~zero evidence cost
(11,549 vs 11,792 median chars). It is env-overridable.

## Key Features

- **Grounded answers** — every claim comes from the retrieved KB; the model says "I don't have that
  documented" rather than inventing, and the UI shows the exact source chunks it used.
- **Owned GPU inference** — vLLM on 2x A4500s with tensor parallelism. Zero cloud GPU cost.
- **Edge/compute split** — cloud frontend for latency, home GPUs for compute, joined by one SSH tunnel.
- **Out-of-band faithfulness verification** — an independent 7B judge on a separate machine grades
  whether an answer's claims are grounded, without ever blocking the response.
- **Per-message telemetry** — time-to-first-token, decode throughput and total latency under each
  answer (metadata only, never content).
- **Regression-gated** — graded eval, plus a live self-test that `cloud/deploy.sh` runs before it
  finishes.
- **Monitored** — a 5-minute VPS health aggregator, a 30-minute T5810 canary and an external
  healthchecks.io dead-man's switch, all paging via ntfy.

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
| **GPU inference** | vLLM + Qwen2.5-Coder-14B-Pscode | LLM serving on 2x A4500s (T5810) |
| **API framework** | FastAPI + Uvicorn | Async Python proxy (cloud server) |
| **Vector DB** | Qdrant | Dense cosine retrieval, top-15 candidates |
| **Embeddings** | BAAI/bge-base-en-v1.5 (768-d) | Query/document → vector (CPU, port 8005) |
| **Reranker** | bge-reranker-base | Cross-encoder precision, top-15 → top-5 (CPU, port 8006) |
| **Faithfulness verifier** | Qwen2.5-7B via Ollama (RTX 3060 Ti) | Out-of-band claim grounding (asrock, port 8007) |
| **Eval / guardrail** | graded eval + golden set; prompt-extraction guardrail | Regression gate + pre-LLM refusal |
| **Frontend** | React + Vite + Tailwind | Built + rsynced to dev.cwetzel.com |
| **Reverse proxy** | Apache | SSL termination, static serving, WSS proxy |
| **Networking** | SSH tunnel | VPS → T5810 → asrock (services stay LAN-only) |
| **Chat history** | Browser localStorage | Per-session; nothing persisted server-side |

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
# vLLM (OpenRC: pscode-vllm; config /etc/pscode/pscode.conf + /etc/conf.d/pscode-vllm)
MODEL=qwen2.5-coder-14b-pscode   # served-model-name; base Qwen2.5-Coder-14B + pscode-prod LoRA
PORT=8004
TENSOR_PARALLEL_SIZE=2
GPU_MEMORY_UTILIZATION=0.93      # 0.95 OOMs; 760 MiB free/A4500 — no room for spec-dec draft

# Qdrant (OpenRC), embed-service 8005 (bge-base, CPU), rerank-service 8006 (bge-reranker, CPU)
QDRANT_PORT=6333
```

**On the asrock B550 (Gentoo/OpenRC):**
```bash
# Faithfulness verifier (OpenRC: verifier-service) + Ollama (OpenRC: ollama)
VERIFIER_PORT=8007
JUDGE_MODEL=qwen2.5:7b-instruct-q4_K_M   # on the 3060 Ti; independent of the 14B
JUDGE_NUM_CTX=12288                      # ollama defaults to 4096 and truncates silently
JUDGE_KEEP_ALIVE=30m                     # ollama evicts idle models after 5m
```

**On the cloud server (cwetzel.com):**
```bash
# API proxy (systemd: api-proxy.service; Apache terminates SSL/WSS in front)
VLLM_URL=http://127.0.0.1:8004      # via SSH tunnel
QDRANT_URL=http://127.0.0.1:6333    # via SSH tunnel
EMBED_URL=http://127.0.0.1:8005     # embed-service (tunneled to T5810)
RERANK_URL=http://127.0.0.1:8006    # rerank-service (tunneled to T5810)
VERIFIER_URL=http://127.0.0.1:8007  # verifier (tunnel → T5810 → asrock); set via systemd drop-in
HYBRID_SEARCH=0                     # hybrid dense+BM25 built but OFF (lost its A/B)
```

**SSH tunnel (single connection, VPS → T5810, with the T5810 as jump host to asrock):**
Forwards 8004 (vLLM), 8005 (embed), 8006 (rerank) and 6333 (Qdrant) — all `127.0.0.1` on the
T5810 — plus **8007 → asrock:8007** (verifier, routed by the T5810 over the LAN). Managed by
`portfolio-ai-tunnel.service` (systemd on the VPS).

## Working On This Repo

**Constraints that bind.** `red-lines.md` and `invariants.md` govern the running system and are
cited from live code. The one that catches people: **never log query or response content** —
metadata only (`red-lines.md` #2). Where `.cursorrules` and `red-lines.md` disagree, red-lines wins.

**The knowledge base must not contain real internal IP addresses.** Public hostnames are fine.

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

**When you change the system, change the docs in the same commit.** A wrong doc is worse than a
missing one: it is confidently wrong, and it survives long after the person who knew better moved on.
