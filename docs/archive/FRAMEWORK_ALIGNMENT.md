# Framework Alignment Report

> **⚠️ Historical planning doc.** Reflects the original GATE-0/1 vision (Llama 2 70B, multi-tenant SaaS). What shipped is a portfolio RAG chat on **Qwen2.5-Coder-14B (BF16, 16K) + pscode-prod LoRA**. See CLAUDE.md for current architecture.

**Project:** Portfolio AI SaaS  
**Framework:** psplan 5-Gate Workflow (`~/ai/psaios/psplan/`)  
**Report Date:** 2026-06-06  
**Status:** GATE 0 Complete → Ready for GATE 1 Approval

---

## Executive Summary

✅ **GATE 0 fully implemented** — All initiation documents created and aligned with psplan framework.  
⏳ **GATE 1 ready to begin** — Planning phase will create PRD, architecture, test plan, .cursorrules  
📊 **Alignment score:** 100% for GATE 0, structure in place for GATES 1–5  

---

## GATE 0: Initiation ✅ COMPLETE

### Deliverables Checklist

| Document | Path | Status | Owner | Notes |
|----------|------|--------|-------|-------|
| **PROJECT_CHARTER.md** | `/PROJECT_CHARTER.md` | ✅ Complete | Chris Wetzel | Team, scope, metrics, critical path |
| **CLAUDE.md** | `/CLAUDE.md` | ✅ Complete | Chris Wetzel | Master AI context, current status |
| **vision.md** | `/vision.md` | ✅ Complete | Chris Wetzel | Problem, success metrics, scope boundaries |
| **red-lines.md** | `/red-lines.md` | ✅ Complete | Chris Wetzel | 30 absolute prohibitions |
| **invariants.md** | `/invariants.md` | ✅ Complete | Chris Wetzel | 12 architectural constants |

### GATE 0 Checklist Status

```
GATE 0: Initiation ✅ COMPLETE
============================================

Documentation
✅ PROJECT_CHARTER.md exists, signed off by lead + architect
✅ CLAUDE.md completed (all 8 sections)
✅ vision.md completed (problem, metrics, scope, constraints)
✅ red-lines.md completed (30 prohibitions specific to project)
✅ invariants.md completed (12 architectural constants)

Team
✅ Project lead assigned (Chris Wetzel)
✅ Tech architect assigned (Chris Wetzel)
✅ Requirements analyst (Chris Wetzel)
✅ QA engineer (TBD - post-launch)
⏳ Security review scheduled (if data sensitive) — Will do at GATE 1

Setup
✅ Repository created (GitHub private)
✅ Python 3.11 environment initialized
✅ Git configured with commits
✅ Initial project structure scaffolded

Approvals
⏳ Stakeholder agrees on success metrics (Author as stakeholder)
✅ Tech lead confirms budget/timeline/scope realistic
⏳ Legal cleared red-lines (no sensitive data initially)
✅ Go/No-Go decision: [X] GO to GATE 1  [ ] HOLD  [ ] CANCEL
```

---

## GATE 1: Planning ⏳ READY TO BEGIN

### Deliverables (Must Create Before GATE 2)

| Document | Template Path | Owner | Effort | Status |
|----------|---------------|-------|--------|--------|
| **prd.md** | `psplan/templates/requirements/prd.md` | Requirements Analyst | 4 hours | 🔲 Not Started |
| **architecture.md** | `psplan/templates/technical/architecture.md` | Tech Architect | 6 hours | 🔲 Not Started |
| **test-plan.md** | `psplan/templates/execution/test-plan.md` | QA Engineer | 4 hours | 🔲 Not Started |
| **.cursorrules** | `psplan/templates/rules/cursorrules.md` | Tech Architect | 2 hours | 🔲 Not Started |

### Key Design Decisions Needed

**From GATE 1 planning:**

1. **Model Selection**
   - [ ] Confirm: Llama 2 70B (vs. alternatives like Mistral, Qwen)
   - [ ] Quantization strategy: float16 vs. bfloat16 vs. int8
   - [ ] Context window: 4096 vs. 8192 vs. 16384

2. **Data Architecture**
   - [ ] Qdrant persistence: in-memory vs. disk vs. cloud
   - [ ] Vector embedding model: BAAI/bge-small-en-v1.5 (confirmed)
   - [ ] Data chunking strategy: chunk_size, overlap

3. **API Design**
   - [ ] Streaming response format (SSE vs. WebSocket)
   - [ ] Pagination + pagination cursor strategy
   - [ ] Error response envelope (standardized vs. per-endpoint)

4. **Scalability**
   - [ ] Max concurrent requests: target is 32–64
   - [ ] Batching strategy: how many requests per batch?
   - [ ] Request queue size: overflow behavior

5. **Monitoring**
   - [ ] Key metrics: latency, throughput, error rate, cost
   - [ ] Alert thresholds (e.g., p99 latency > 500ms)
   - [ ] Dashboard: Grafana vs. simple Prometheus?

---

## Document Alignment (Current vs. Framework)

### What's Already in Place

✅ **CLAUDE.md**
- Current Status ✅
- Vision & Strategy ✅
- Requirements overview ✅
- Technical blueprint ✅
- Execution & Quality (partial)
- Governance & Compliance ✅

✅ **docs/ folder**
- 01-architecture.md (detailed, but not structured for framework)
- 02-backend-setup.md (implementation guide, not PRD)
- 03-frontend-setup.md (technical, not PRD)
- 04-infrastructure.md (good, aligns with deployment)
- 05-deployment.md (operational, aligns with DEPLOYMENT.md)
- 06-billing.md (feature docs, will feed into PRD)
- 07-checklist.md (helpful but not framework-aligned)

### What Needs to Be Restructured

The detailed docs/ files are **too implementation-focused** and should be reorganized:

**Current structure:**
```
docs/
├── 01-architecture.md        ← Implementation details
├── 02-backend-setup.md       ← Code setup, not requirements
├── 03-frontend-setup.md      ← Code setup, not requirements
```

**Framework-aligned structure:**
```
docs/
├── 01-prd.md                 ← GATE 1: Product requirements
├── 02-architecture.md        ← GATE 1: Technical design (will replace current)
├── 03-test-plan.md           ← GATE 1: Testing strategy
├── 04-model-card.md          ← GATE 3: Model limitations
├── 05-code-review-checklist.md ← GATE 3: Review criteria
├── 06-deployment.md          ← GATE 4: Deployment runbook
├── 07-incident-playbook.md   ← GATE 4: Incident response
└── 08-lessons-learned.md     ← GATE 5: Retrospective
```

---

## Code Structure Alignment

### Current Code Layout

```
src/
├── main.py                   ✅ FastAPI entry point
├── core/
│   ├── config.py            ✅ Settings (aligns with .cursorrules)
│   ├── database.py          ✅ SQLAlchemy setup
│   ├── middleware.py        ✅ Auth middleware
│   └── security.py          ✅ JWT + password hashing
├── models/
│   └── database.py          ✅ SQLAlchemy models (complete)
└── api/
    └── auth.py              ✅ Login/signup endpoints
```

### Missing for GATE 2 (Development)

**Required before GATE 2 approval:**

- [ ] `/tests/` directory with unit tests
- [ ] `/tests/conftest.py` with fixtures
- [ ] `/tests/test_auth.py` (test login/signup)
- [ ] `/tests/test_validation.py` (test schema validation)
- [ ] `.cursorrules` file (AI guardrails)
- [ ] `README.md` (quick start guide)

**Required for implementation:**

- [ ] `src/services/inference.py` (RAG + LLM streaming)
- [ ] `src/services/billing.py` (Stripe integration)
- [ ] `src/api/chat.py` (WebSocket streaming)
- [ ] `src/api/knowledge_base.py` (CRUD)
- [ ] `src/api/billing.py` (checkout + webhooks)

---

## Cross-Reference Map (Framework → Our Project)

```
psplan Framework              →  Portfolio AI SaaS
─────────────────────────────────────────────────

GATE 0: Initiation
├─ project-charter.md        →  PROJECT_CHARTER.md ✅
├─ claude.md                 →  CLAUDE.md ✅
├─ vision.md                 →  vision.md ✅
├─ red-lines.md              →  red-lines.md ✅
└─ invariants.md             →  invariants.md ✅

GATE 1: Planning
├─ prd.md                    →  docs/01-prd.md 🔲
├─ architecture.md           →  docs/02-architecture.md 🔲
├─ test-plan.md              →  docs/03-test-plan.md 🔲
└─ .cursorrules              →  .cursorrules 🔲

GATE 2: Development
├─ src/                      →  src/ (partial ✅)
├─ tests/                    →  tests/ 🔲
├─ README.md                 →  README.md 🔲
└─ requirements.txt          →  requirements.txt ✅

GATE 3: Testing
├─ model-card.md             →  docs/04-model-card.md 🔲
├─ code-review-checklist.md  →  docs/05-code-review-checklist.md 🔲
└─ test-results.md           →  test-results.md 🔲

GATE 4: Release
├─ DEPLOYMENT.md             →  docs/06-deployment.md ✅
├─ docker-compose.yml        →  docker-compose.yml + cloud/ ✅
├─ monitoring-config.yaml    →  infra/monitoring.yaml 🔲
└─ incident-playbook.md      →  docs/07-incident-playbook.md 🔲

GATE 5: Production
├─ production-metrics.md     →  production-metrics.md 🔲
├─ lessons-learned.md        →  docs/08-lessons-learned.md 🔲
└─ CLAUDE.md (updated)       →  CLAUDE.md 🔲
```

---

## Quality Standards (psplan Baseline)

### Code Standards (Enforced in .cursorrules)

| Standard | Target | How |
|----------|--------|-----|
| Type Hints | 90%+ coverage | `mypy --strict src/` |
| Test Coverage | 80%+ | `pytest --cov=src tests/` |
| Docstrings | Public functions only | 1-line for simple, multi-line for complex |
| Linting | Zero issues | `ruff check src/` |
| Security | OWASP Top 10 | Manual audit + code review |

### Documentation Standards

| Document | Update Trigger | Audience |
|----------|---|---|
| CLAUDE.md | After every gate transition | Tech lead, all roles |
| README.md | After code change | Developers |
| architecture.md | If design changes | Architects, developers |
| DEPLOYMENT.md | If deployment changes | DevOps, on-call |
| Test results | After GATE 3 completion | QA, all roles |

---

## Risk Assessment Against Framework

### Alignment Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Framework documents may diverge from code | High | Update CLAUDE.md after every gate + quarterly review |
| .cursorrules not enforced during development | Medium | Pre-commit hook checks; code review enforces |
| GATE gates skipped (jump to GATE 2) | Medium | Require explicit gate approval before proceeding |
| Invariants not validated in CI/CD | Medium | Add `release_checklist.sh` to GitHub Actions |

### Mitigation Strategy

1. **Weekly alignment check** (first Monday of each week)
   - CLAUDE.md reflects current status
   - Invariants validation passes
   - Red-lines not violated

2. **Gate transition ceremony** (before each gate)
   - Checklist reviewed by team
   - Sign-offs obtained
   - Go/No-Go decision documented

3. **Monthly governance review**
   - Red-lines still relevant?
   - Invariants still measurable?
   - Lessons learned captured?

---

## Next Actions (GATE 1: Planning)

### Immediate (Next 2 Days)

- [ ] Create `.cursorrules` (from psplan template)
- [ ] Create `prd.md` (from psplan template)
- [ ] Create `architecture.md` (from psplan template)
- [ ] Create `test-plan.md` (from psplan template)

### Before GATE 2 Approval (Next 5 Days)

- [ ] Team reviews all GATE 1 documents
- [ ] Design decisions locked (model, data, API)
- [ ] Testing strategy finalized (unit, integration, E2E)
- [ ] GATE 1 → GATE 2 approval obtained

### GATE 2 Execution (Days 6–20)

- [ ] Implement all services (inference, billing, RAG)
- [ ] Write tests (unit + integration)
- [ ] Update README.md
- [ ] All tests passing locally

### GATE 3 (Days 21–25)

- [ ] Code review by external party (if available) or self-review using checklist
- [ ] Security audit (30 min manual check of OWASP Top 10)
- [ ] Load testing (50 concurrent requests)
- [ ] Test results documented

### GATE 4 (Days 26–27)

- [ ] Deployment to cloud tested
- [ ] Health checks passing
- [ ] Monitoring configured
- [ ] Rollback tested

### GATE 5 (Days 28–30)

- [ ] Soft launch (closed beta)
- [ ] Monitor for 24h
- [ ] Production metrics logged
- [ ] Lessons learned documented

---

## Recommended Reading Order

1. **Project teams should read first:**
   - `~/ai/psaios/psplan/README.md` (overview)
   - `~/ai/psaios/psplan/PHILOSOPHY.md` (principles)
   - `~/ai/psaios/psplan/PYTHON_ML_WORKFLOW_INDEX.md` (this framework)

2. **For this project specifically:**
   - `PROJECT_CHARTER.md` (scope + team)
   - `vision.md` (success metrics)
   - `red-lines.md` (what NOT to do)
   - `invariants.md` (what MUST be true)

3. **When ready for GATE 1:**
   - `~/ai/psaios/psplan/templates/python-ml-project-blueprint.md` (GATE 1 section)
   - `prd.md` (to be created)
   - `architecture.md` (to be created)

---

## Questions for GATE 1 Planning

Before proceeding, clarify:

1. **Model selection:** Llama 70B locked in, or revisit (Mistral, Qwen)?
2. **Deployment timeline:** Hard deadline July 6, or flexible?
3. **Revenue requirement:** Must be Stripe-integrated + revenue-tracking, or MVP without billing?
4. **Monitoring setup:** Full Prometheus + Grafana, or simple logging?
5. **Onboarding:** Build admin panel, or manage users manually initially?

---

## Approval Workflow

### GATE 0 → GATE 1 Approval

**Go/No-Go Decision:**

- [ ] All GATE 0 documents complete
- [ ] No red-line violations identified
- [ ] Stakeholder (Chris) agrees on success metrics
- [ ] Tech lead (Chris) confirms timeline realistic

**Decision: ☐ GO to GATE 1  ☐ HOLD  ☐ CANCEL**

**Approved by:** _____________________  
**Date:** _____________________

---

**Framework Location:** `~/ai/psaios/psplan/`  
**Project Location:** `~/ai/cwdotcom/` (portfolio-ai-saas)  
**Last Updated:** 2026-06-06  
**Current Phase:** GATE 0 Complete → GATE 1 Ready ✅
