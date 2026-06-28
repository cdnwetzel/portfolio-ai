# Portfolio AI Chat

> **What this actually is:** a single-tenant **portfolio RAG chat** at dev.cwetzel.com — a
> React frontend + FastAPI proxy on a VPS, talking over an SSH tunnel to vLLM (Qwen2.5-Coder-14B
> + pscode LoRA), Qdrant, a CPU embedder, and a CPU reranker on the T5810. **The multi-tenant
> SaaS / Stripe / billing / auth content below is archived aspiration** — that scaffold lived in
> `src/` and is preserved on the `legacy/saas-scaffold` branch; it is NOT part of the running
> system. See the "Actual Deployment Config" and "Documentation Alignment" sections for reality.

## Project Overview

This is a single-tenant portfolio RAG chat built on personal infrastructure (2x A4500 GPUs +
300 Mbps fiber) — a professional-portfolio showcase, not a revenue-generating SaaS product. The
original multi-tenant SaaS vision (below) was scoped down; the SaaS scaffold is archived on
`legacy/saas-scaffold`.

Following the **5-Gate Workflow** (psplan framework):
- **GATE 0** ✅ Initiation (Charter, Vision, Red-lines, Invariants)
- **GATE 1** ⏳ Planning (PRD, Architecture, Test Plan, .cursorrules)
- **GATE 2** 🔲 Development (Code + Tests)
- **GATE 3** 🔲 Review & Testing (QA + Code Review)
- **GATE 4** 🔲 Release (Deployment + Handoff)
- **GATE 5** 🔲 Production Validation (Monitoring + Closure)

## Core Architecture

```
User Browser
    ↓ HTTPS
cwetzel.com Cloud Server
├─ Apache (SSL, reverse proxy, WSS)
├─ FastAPI API Proxy (port 8000)
│  └─ Routes to T5810 via SSH tunnel
└─ Static HTML frontend
    ↓ [SSH Tunnel]
    ↓ (ai.cwetzel.com:8004)
T5810 Home Server (Gentoo/OpenRC, Your Hardware)
├─ vLLM (port 8004, local LAN only)
│  └─ Model: Qwen2.5-Coder-14B-Pscode (BF16, 16K context)
│  └─ 2x A4500 NVLink, tensor parallel
├─ Qdrant (port 6333, vector DB — dense 768-d cosine)
├─ Embedding service (port 8005, BAAI/bge-base-en-v1.5 768-d, CPU)
├─ Reranker service (port 8006, bge-reranker-base, CPU)
└─ Knowledge base (indexed docs)
    ↓ tunnel also forwards :8007 → asrock B550 (10.0.1.115) on the LAN
asrock B550 Home Server (Gentoo/OpenRC)
└─ Faithfulness verifier (port 8007, Qwen2.5-7B via Ollama, CPU)
```

**RAG pipeline:** query → alias-expand → embed (8005, bge-base 768-d) → Qdrant cosine
top-15 → rerank to top-5 (8006, CPU cross-encoder, ≤1 chunk/doc) → fit to token budget
→ vLLM stream → (out-of-band) fire-and-forget faithfulness verify (8007, asrock). The
reranker adds precision the bi-encoder can't: cosine surfaces candidates, the
cross-encoder picks the best 5. CPU-only on the T5810's idle 256GB DDR4 — no VRAM
contention with vLLM. Fails open (cosine top-5) if the reranker is down; the verifier
is fully fail-open (chat unaffected if asrock is down).

A deterministic **prompt-extraction guardrail** (`cloud/guardrails.py`) refuses
"reveal/repeat your prompt"-style attacks before the LLM. A **graded eval**
(`scripts/eval_graded.py` + `eval/golden_set.yaml`) gates changes; a **hybrid dense+BM25**
path exists (`HYBRID_SEARCH`) but is OFF — an A/B showed it regressed on this small KB.

## Key Features

- **Multi-Tenancy**: Row-level security, tenant isolation via JWT/API keys
- **GPU Inference**: vLLM on 2x A4500s, tensor parallelism across both cards
- **Scalable Edge Architecture**: Cloud frontend for low latency, home GPU for compute
- **Automated Data Sync**: GitHub webhooks trigger re-indexing of public repos
- **SaaS Ready**: Stripe integration, usage-based billing, API keys
- **Production Grade**: Docker, Alembic migrations, health checks, monitoring

## Directory Structure

```
portfolio-saas/
├── .github/workflows/          # CI/CD pipelines
├── alembic/                    # Database migrations
├── docs/                       # This documentation
│   ├── 01-architecture.md
│   ├── 02-backend-setup.md
│   ├── 03-frontend-setup.md
│   ├── 04-infrastructure.md
│   ├── 05-deployment.md
│   ├── 06-billing.md
│   └── 07-checklist.md
├── src/
│   ├── api/                    # API routes (chat, auth, billing, kb)
│   ├── core/                   # Config, security, database
│   ├── models/                 # SQLAlchemy models
│   ├── services/               # Business logic (inference, billing, RAG)
│   ├── middleware/             # Auth middleware, request tracking
│   └── main.py                 # FastAPI app entry point
├── frontend/
│   ├── src/
│   │   ├── pages/              # Dashboard, signup, login
│   │   ├── components/         # Reusable UI components
│   │   ├── lib/                # API client, utilities
│   │   └── styles/             # Tailwind + custom CSS
│   └── vite.config.ts
├── cloud/                      # Cloud Ubuntu deployment
│   ├── docker-compose.yml
│   ├── setup-proxy-apache.sh
│   ├── .env.example
│   └── deploy.sh
├── home/                       # Home Gentoo server config
│   ├── systemd/
│   ├── wg0.conf
│   └── requirements.txt
├── tests/                      # Unit and integration tests
├── docker-compose.yml          # Local dev environment
├── requirements.txt            # Python dependencies
├── .env.example
└── README.md
```

## Implementation Phases

### Phase 1: Foundation (Current)
- [x] Database schema design (PostgreSQL)
- [x] Multi-tenancy architecture
- [x] Auth middleware (JWT + API keys)
- [x] Docker orchestration
- [ ] **NEXT**: Create Alembic migrations
- [ ] **NEXT**: Implement auth endpoints (signup/login)
- [ ] **NEXT**: Deploy local dev environment

### Phase 2: Core API
- [ ] Chat streaming endpoints
- [ ] Knowledge base management
- [ ] Document upload/indexing
- [ ] RAG pipeline integration
- [ ] Usage tracking

### Phase 3: Frontend Dashboard
- [ ] Login/signup pages
- [ ] Dashboard overview
- [ ] Knowledge base management UI
- [ ] API key generation
- [ ] Billing/subscription UI

### Phase 4: Infrastructure
- [ ] WireGuard tunnel (Gentoo ↔ Cloud)
- [ ] Apache configuration with SSL (cloud/setup-proxy-apache.sh)
- [ ] Docker deployment (Cloud)
- [ ] Database migrations
- [ ] Health checks

### Phase 5: Billing & Revenue
- [ ] Stripe product configuration
- [ ] Webhook handlers
- [ ] Usage billing calculations
- [ ] Invoice generation

### Phase 6: DevOps & Launch
- [ ] GitHub Actions CI/CD
- [ ] Automated deployment
- [ ] Monitoring setup
- [ ] DNS cutover
- [ ] Go-live

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **GPU Inference** | vLLM + Qwen2.5-Coder-14B-Pscode | LLM serving on 2x A4500s (T5810) |
| **API Framework** | FastAPI + Uvicorn | Async Python proxy (cloud server) |
| **Vector DB** | Qdrant | Semantic search + RAG retrieval (dense cosine top-15) |
| **Embeddings** | BAAI/bge-base-en-v1.5 (768-d) | Query/document → vector (CPU service, port 8005) |
| **Reranker** | bge-reranker-base | Cross-encoder precision, top-15 → top-5 (CPU, port 8006) |
| **Faithfulness verifier** | Qwen2.5-7B via Ollama (CPU) | Out-of-band claim grounding (asrock B550, port 8007) |
| **Eval / guardrail** | graded eval + golden set; prompt-extraction guardrail | Regression gate (`scripts/eval_graded.py`) + pre-LLM refusal (`cloud/guardrails.py`) |
| **Frontend** | React + Vite + Tailwind | Built + rsynced to dev.cwetzel.com |
| **Reverse Proxy** | Apache | SSL termination, static serving, WSS proxy |
| **Networking** | SSH Tunnel | Secure VPS → T5810 → asrock (LAN-only access) |
| **Knowledge Base** | Local filesystem | Indexed documents + case studies |
| **Caching** | Browser localStorage | Per-session chat history |

## Key Configuration Files

1. **docker-compose.yml** - Local dev environment (PostgreSQL, Redis, FastAPI)
2. **src/main.py** - FastAPI application entry point
3. **.env.example** - Environment variables template
4. **cloud/docker-compose.yml** - Production cloud stack
5. **cloud/setup-proxy-apache.sh** - Apache vhost + SSL + WSS reverse proxy setup
6. **alembic/versions/*.py** - Database migrations
7. **.github/workflows/deploy.yml** - GitHub Actions CI/CD

## Key Endpoints

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| **POST** | /api/auth/signup | Create new tenant | None |
| **POST** | /api/auth/login | User login | None |
| **POST** | /api/knowledge-base | Create KB | JWT |
| **WS** | /ws/chat | Stream LLM responses | JWT/API Key |
| **POST** | /api/api-keys | Generate API key | JWT |
| **GET** | /api/dashboard | Tenant metrics | JWT |
| **POST** | /api/billing/checkout | Create Stripe session | JWT |
| **POST** | /webhooks/github | GitHub push event | Secret |
| **POST** | /webhooks/stripe | Stripe event | Secret |

## Actual Deployment Config

**On T5810 (Home Server, Gentoo/OpenRC):**
```bash
# vLLM Service (OpenRC: pscode-vllm; config /etc/pscode/pscode.conf + /etc/conf.d/pscode-vllm)
MODEL=qwen2.5-coder-14b-pscode   # served-model-name; base Qwen2.5-Coder-14B + pscode-prod LoRA
PORT=8004
TENSOR_PARALLEL_SIZE=2
GPU_MEMORY_UTILIZATION=0.93  # 0.95 OOMs; 760 MiB free/A4500 — no room for spec-dec draft

# Qdrant (OpenRC), embed-service 8005 (bge-base, CPU), rerank-service 8006 (bge-reranker, CPU)
QDRANT_PORT=6333
```

**On asrock B550 (10.0.1.115, Gentoo/OpenRC):**
```bash
# Faithfulness verifier (OpenRC: verifier-service) + Ollama (OpenRC: ollama)
VERIFIER_PORT=8007
JUDGE_MODEL=qwen2.5:7b-instruct-q4_K_M   # CPU; independent of the 14B
```

**On Cloud Server (cwetzel.com):**
```bash
# API Proxy (systemd: api-proxy.service; Apache terminates SSL/WSS in front)
VLLM_URL=http://127.0.0.1:8004    # via SSH tunnel
QDRANT_URL=http://127.0.0.1:6333  # via SSH tunnel
EMBED_URL=http://127.0.0.1:8005   # embed-service (tunneled to T5810)
RERANK_URL=http://127.0.0.1:8006  # rerank-service (tunneled to T5810)
VERIFIER_URL=http://127.0.0.1:8007  # verifier (tunnel → T5810 → asrock); set via systemd drop-in
HYBRID_SEARCH=0                    # hybrid dense+BM25 built but OFF (lost A/B vs dense on this KB)
```

**SSH Tunnel (single connection, VPS → T5810, with T5810 as jump host to asrock):**
Forwards 8004 (vLLM), 8005 (embed), 8006 (rerank), 6333 (Qdrant) — all `127.0.0.1` on the
T5810 — plus **8007 → 10.0.1.115:8007** (asrock verifier, routed by the T5810 over the LAN).
Managed by `portfolio-ai-tunnel.service` (systemd on the VPS).

## Deployment Checklist

### Local Development
- [ ] Clone repository
- [ ] Copy `.env.example` → `.env` with local values
- [ ] Run `docker-compose up -d`
- [ ] Run `alembic upgrade head`
- [ ] Test `curl http://localhost:8000/health`

### Cloud Ubuntu Setup
- [ ] SSH key setup for deployment
- [ ] DNS A record pointed to cloud IP
- [ ] SSL certificate (Certbot)
- [ ] `.env` configured with production secrets
- [ ] `docker-compose up -d`

### Gentoo Home Server
- [ ] WireGuard keys generated
- [ ] `wg0.conf` configured
- [ ] vLLM running with tensor parallelism
- [ ] PostgreSQL accessible from cloud

### GitHub Integration
- [ ] Repository secrets configured
- [ ] GitHub webhook created
- [ ] CI/CD workflows enabled

### Go-Live
- [ ] DNS cutover
- [ ] SSL verification
- [ ] Smoke tests on production
- [ ] Monitoring active
- [ ] Slack notifications configured

## Quick Start Commands

```bash
# Local development
docker-compose up -d
alembic upgrade head

# Deploy to production
./cloud/deploy.sh

# View logs
docker logs -f portfolio-saas-api-1
docker exec portfolio-saas-api-1 tail -f /var/log/app.log

# Database
docker exec portfolio-saas-db-1 psql -U postgres -d saas_prod
```

## Resources & References

- **Architecture Docs**: See `docs/01-architecture.md`
- **Backend Setup**: See `docs/02-backend-setup.md`
- **Frontend Setup**: See `docs/03-frontend-setup.md`
- **Infrastructure**: See `docs/04-infrastructure.md`
- **Deployment**: See `docs/05-deployment.md`
- **Billing**: See `docs/06-billing.md`
- **Getting Started**: See `docs/07-checklist.md`

## Contact & Support

For issues during setup, refer to the troubleshooting section in each documentation file.

---

---

## Documentation Alignment

**Last Updated**: 2026-06-10  
**Current Phase**: MVP (RAG Chat Demo)

### Recent Changes (2026-06-10)

After aligning docs with actual deployment:

1. **Frontend**: Migrated from standalone HTML to React Vite build
   - Source: `/frontend/src/` (React components, hooks)
   - Deployed: `dev.cwetzel.com` (built via `npm run build`)
   - Deployment: `rsync -avz --delete frontend/dist/ root@cwetzel.com:/var/www/dev.cwetzel.com/`
   - See: [frontend/README-DEPLOYMENT.md](frontend/README-DEPLOYMENT.md)

2. **Model**: Qwen2.5-Coder-14B-Pscode (not Llama 2 70B)
   - Running on T5810 port 8004 (LAN-only)
   - Accessible via SSH tunnel from cloud server
   - Tensor parallel: 2x A4500 GPUs

3. **Architecture**: Fixed docs to match actual setup
   - Removed SaaS multi-tenant references (outdated)
   - Clarified T5810 + SSH tunnel + cloud proxy structure
   - Added actual tech stack (Qwen, Qdrant, BAAI embeddings, standalone HTML → React)

### What This Means

- **Documentation now reflects reality** (not aspirations)
- **Frontend code matches deployed version** (useChat.js has correct model)
- **Deployment is reproducible** (build + rsync script documented)
- **Future changes should update both code AND docs**

### Resources

- **Deployment guide**: [frontend/README-DEPLOYMENT.md](frontend/README-DEPLOYMENT.md)
- **Session notes**: Memory file `session-docs-alignment-2026-06-10.md`
- **Architecture**: This file (updated above)
