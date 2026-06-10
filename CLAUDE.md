# Portfolio AI SaaS Platform

## Current Status

**GATE 0: Project Initiation** ⏳  
**Phase:** Charter + Context Documentation Complete  
**Next Gate:** GATE 1 (Planning) — Awaiting approval to proceed to design & requirements  

---

## Project Overview

This is a production-grade, multi-tenant AI SaaS platform built on your personal infrastructure (2x A4500 GPUs + 300 Mbps fiber). The platform serves as both your professional portfolio showcase and a revenue-generating SaaS product.

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
├─ Nginx (SSL, reverse proxy)
├─ FastAPI API Proxy (port 8000)
│  └─ Routes to T5810 via SSH tunnel
└─ Static HTML frontend
    ↓ [SSH Tunnel]
    ↓ (ai.cwetzel.com:8004)
T5810 Home Server (Gentoo, Your Hardware)
├─ vLLM (port 8004, local LAN only)
│  └─ Model: Qwen2.5-Coder-14B-Pscode
│  └─ 2x A4500 NVLink, tensor parallel
├─ Qdrant (port 6333, vector DB)
└─ Knowledge base (indexed docs)
```

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
│   ├── nginx.conf
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
- [ ] Nginx configuration with SSL
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
| **Vector DB** | Qdrant | Semantic search + RAG retrieval |
| **Embeddings** | BAAI/bge-small-en-v1.5 | Document → vector conversion |
| **Frontend** | Standalone HTML + vanilla JS | Simple, no build step |
| **Reverse Proxy** | Nginx | SSL termination, static HTML serving |
| **Networking** | SSH Tunnel | Secure T5810 ↔ Cloud communication (LAN-only access) |
| **Knowledge Base** | Local filesystem | Indexed documents + case studies |
| **Caching** | Browser localStorage | Per-session chat history |

## Key Configuration Files

1. **docker-compose.yml** - Local dev environment (PostgreSQL, Redis, FastAPI)
2. **src/main.py** - FastAPI application entry point
3. **.env.example** - Environment variables template
4. **cloud/docker-compose.yml** - Production cloud stack
5. **cloud/nginx.conf** - Nginx reverse proxy configuration
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

**On T5810 (Home Server):**
```bash
# vLLM Service (systemd: vllm-qwen.service)
MODEL=qwen2.5-coder-14b-pscode
PORT=8004
TENSOR_PARALLEL_SIZE=2
CUDA_VISIBLE_DEVICES=0,1
GPU_MEMORY_UTILIZATION=0.85

# Qdrant Vector DB (systemd: qdrant.service)
QDRANT_PORT=6333
STORAGE_PATH=/opt/qdrant/storage
```

**On Cloud Server (cwetzel.com):**
```bash
# API Proxy (systemd: api-proxy.service)
VLLM_URL=http://ai.cwetzel.com:8004  # via SSH tunnel
QDRANT_URL=http://ai.cwetzel.com:6333  # via SSH tunnel
EMBED_URL=http://127.0.0.1:8005  # Embedding service
```

**SSH Tunnel (maintains T5810 access):**
```bash
# Cloud → T5810 forward tunnel
# Port 8004 accessible as ai.cwetzel.com:8004 locally
```

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
