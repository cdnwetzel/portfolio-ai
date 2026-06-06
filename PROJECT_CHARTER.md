# Portfolio AI SaaS — Project Charter

**Project Name:** Portfolio AI SaaS Platform  
**Project Lead:** Chris Wetzel (cdnwetzel)  
**Tech Architect:** Chris Wetzel  
**Start Date:** 2026-06-06  
**Target Launch Date:** 2026-07-06 (30 days)  
**GitHub:** github.com/cdnwetzel/portfolio-ai-saas (Private)

---

## Problem Statement

Professional portfolios are static. Recruiters want interactive experiences that demonstrate technical depth in real-time. Current AI portfolio tools use paid APIs (OpenAI, Anthropic), requiring monthly subscriptions. This project builds a self-hosted, GPU-powered SaaS that:

1. **Showcases your skills** via live AI interactions (chat with your resume, code, LinkedIn)
2. **Demonstrates infrastructure** (distributed GPU inference, WireGuard tunnels, edge caching)
3. **Generates revenue** (multi-tenant SaaS with usage-based billing)
4. **Remains cost-efficient** (40GB GPU on home fiber costs ~$50/month vs. $500+ cloud equivalents)

---

## Success Metrics

### Must-Have (MVP - 30 days)
- [ ] **Performance:** First token latency < 200ms, throughput > 100 tok/sec on 2x A4500s
- [ ] **Architecture:** WireGuard tunnel stable (99.5% uptime), cloud-home latency < 50ms
- [ ] **Revenue:** Stripe integration working, checkout flow validated with test cards
- [ ] **Security:** Row-level security in PostgreSQL, JWT auth functional, no secrets in git
- [ ] **Deployment:** Docker build succeeds, GitHub Actions CI/CD runs, health checks pass

### Should-Have (Post-launch)
- [ ] **Accuracy:** RAG retrieval relevance > 0.8 (semantic match to queries)
- [ ] **Coverage:** 10+ Pro tier customers signups in first month
- [ ] **Uptime:** 99.5% service availability for first 30 days
- [ ] **Docs:** Complete runbooks for on-call, monitoring dashboards live

---

## Team

| Role | Name | Responsibility | Status |
|------|------|---|---|
| **Project Lead** | Chris Wetzel | Timeline, scope, stakeholder communication | ✅ |
| **Tech Architect** | Chris Wetzel | Stack, design decisions, code quality | ✅ |
| **Core Developer** | Chris Wetzel | Implementation, testing, deployment | ✅ |
| **DevOps** | Chris Wetzel | Infrastructure, WireGuard, CI/CD | ✅ |
| **QA** | TBD (post-launch) | Load testing, edge cases, production monitoring | 📝 |

---

## Key Dependencies

### External Services
- **GitHub:** CI/CD workflows, private repo hosting
- **Stripe:** Payment processing, subscription management
- **Certbot:** SSL certificate renewal (automatic)
- **Cloudflare:** DNS, optional DDoS protection

### Infrastructure
- **Home:** 2x NVIDIA A4500 (40GB NVLink), Gentoo, 300 Mbps fiber, fixed IP
- **Cloud:** $5/month VPS (Ubuntu 24.04), PostgreSQL, Redis, Nginx
- **Domain:** chris.cwetzel.com (owned), app.chris.cwetzel.com (CNAME)

### Data
- **Public GitHub repos:** Auto-ingested via webhook
- **Resume:** Markdown file, version controlled
- **LinkedIn:** Manual PDF export (LinkedIn ToS restriction)

---

## Scope: What We're Building

### In Scope (MVP)
✅ Multi-tenant SaaS with JWT + API key auth  
✅ Real-time chat with LLM (Llama 70B via vLLM)  
✅ RAG pipeline (Qdrant vector DB + semantic search)  
✅ Stripe billing (Pro tier $29/month)  
✅ GitHub webhook auto-indexing  
✅ WireGuard tunnel (cloud ↔ home)  
✅ React dashboard (Shadcn UI)  
✅ Docker deployment (local + cloud)  

### Out of Scope (Post-Launch)
❌ Multi-language support  
❌ Custom model fine-tuning  
❌ Voice/video chat  
❌ White-label reseller program  
❌ Mobile app  
❌ Real-time collaboration features  
❌ Advanced analytics dashboard  

---

## Critical Path (Blocking Items)

### Phase 1: Foundation (Days 1–5)
1. **Alembic migrations** (database schema must be version-controlled)
2. **Auth endpoints** (signup/login must work before any feature builds)
3. **Docker local stack** (dev environment must be reproducible)

### Phase 2: Core Features (Days 6–20)
1. **Chat streaming** (WebSocket infrastructure)
2. **RAG pipeline** (vector retrieval + LLM integration)
3. **Knowledge base** (document upload + indexing)

### Phase 3: Revenue (Days 21–25)
1. **Stripe webhook handler** (billing must be production-ready)
2. **Usage tracking** (token counting, metering)

### Phase 4: Deployment (Days 26–30)
1. **WireGuard tunnel** (must be stable before soft launch)
2. **CI/CD pipeline** (automated deployment to cloud)
3. **Health checks** (monitoring + alerts)

---

## Budget & Resources

### Monthly Operating Costs
- Cloud Ubuntu: **$5** (VPS)
- Home electricity: **~$40** (2x A4500 @ 300W)
- Domain: **~$1** (pro-rated)
- **Total: ~$46/month**

### Revenue Model (Post-Launch)
- Free tier: $0 (100k tokens/month)
- Pro tier: $29/month (1M tokens/month)
- Enterprise: Custom pricing
- **Break-even:** 2 Pro customers = $58/month revenue > $46 costs ✅

### Time Investment
- **MVP (30 days):** ~480 hours (solo engineer, ~16 hours/day)
- **Post-launch:** ~20 hours/week (maintenance + feature development)

---

## Stakeholder Sign-Offs

| Role | Name | Sign-Off | Date |
|------|------|----------|------|
| Project Lead | Chris Wetzel | ☐ | — |
| Tech Architect | Chris Wetzel | ☐ | — |
| Co-owner (optional) | — | N/A | — |

---

## Known Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|---|---|
| WireGuard tunnel instability | Inference unavailable | Medium | Test failover weekly, document runbook |
| GPU memory OOM during inference | Service crash | Low | Monitor vLLM queue depth, implement request queuing |
| GitHub API rate limits | Webhook indexing fails | Low | Implement exponential backoff, cache responses |
| Stripe test mode bugs | Billing doesn't work in prod | Low | Thorough webhook testing before go-live |
| Home fiber internet outage | Service completely down | Low | Add fallback to cloud-only mode (degraded) |

---

## Success Criteria (Gate 0 → Gate 1)

Before advancing to Planning phase, confirm:

- [ ] All 5 team roles assigned (can be same person)
- [ ] PROJECT_CHARTER reviewed + stakeholder sign-off
- [ ] CLAUDE.md completed with all 8 sections
- [ ] vision.md defining success metrics
- [ ] red-lines.md with 5+ prohibitions
- [ ] invariants.md with 5+ architectural constants
- [ ] GitHub repo initialized (private, initial commit)
- [ ] Go/No-Go decision: **[ ] GO** [ ] HOLD [ ] CANCEL

---

## Next Steps (Gate 1: Planning)

1. **Create prd.md** — Detailed product requirements
2. **Create architecture.md** — Stack, data models, deployment
3. **Create test-plan.md** — Testing strategy (unit, integration, E2E)
4. **Create .cursorrules** — AI guardrails for code generation
5. **Review all documents with team**
6. **Gate 1 approval** → Ready for development

---

**Current Gate:** GATE 0 (Initiation)  
**Status:** ⏳ Awaiting planning approval  
**Last Updated:** 2026-06-06
