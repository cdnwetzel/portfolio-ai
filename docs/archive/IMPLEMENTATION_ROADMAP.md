# Implementation Roadmap — From Framework to Launch

> **⚠️ Historical planning doc.** Reflects the original GATE-0/1 vision (Llama 2 70B, multi-tenant SaaS). What shipped is a portfolio RAG chat on **Qwen2.5-Coder-14B (BF16, 16K) + pscode-prod LoRA**. See CLAUDE.md for current architecture.

**Status:** GATE 0 Complete, Professional Context Captured, Ready to Begin GATE 1  
**Date:** 2026-06-06  
**Repository:** github.com/cdnwetzel/portfolio-ai-saas (Private)

---

## What You Have Today

### ✅ Complete GATE 0 Governance
- PROJECT_CHARTER.md (team, scope, 30-day timeline, success metrics)
- vision.md (problem statement, measurable criteria, boundaries)
- red-lines.md (30 prohibitions: security, data, operations, quality)
- invariants.md (12 architectural constants: versioning, logging, monitoring, RLS)
- CLAUDE.md (master AI context, framework-aligned, current status)
- PROFESSIONAL_CONTEXT.md (your background, personas, RAG content strategy)

### ✅ Framework Alignment
- FRAMEWORK_ALIGNMENT.md (detailed assessment vs psplan)
- READY_TO_EXECUTE.md (exactly what's missing for GATE 1)
- PROJECT_STATUS.md (comprehensive overview + sign-offs)

### ✅ Code Scaffolding (60%)
- src/core/ (config, database, security, auth middleware) — 100% ready
- src/models/ (12 SQLAlchemy models) — 100% ready
- src/api/ (auth endpoints) — 100% ready
- alembic/ (migrations) — 100% ready
- Docker (compose, Dockerfile) — 100% ready
- CI/CD (.github/workflows/) — 100% ready
- Infrastructure (nginx, deploy scripts, WireGuard) — 100% ready
- Tests, React frontend, RAG services — 0% (GATE 2 work)

### ✅ Professional Identity
- Website analyzed (cwetzel.com)
- GitHub repo reviewed (gentoo-machines)
- LinkedIn profile captured
- Personas identified (IT Manager, Consultant, Lawyer)
- Use cases documented (compliance, contracts, infrastructure)
- RAG knowledge base strategy defined

---

## What You Need to Create (GATE 1 — 16 Hours)

### Critical (Must Have Before GATE 2)

| Document | Time | Purpose | Template Source |
|----------|------|---------|-----------------|
| **.cursorrules** | 2h | Code style guardrails, AI rules | `~/ai/psaios/psplan/templates/rules/cursorrules.md` |
| **prd.md** | 4h | Product requirements, use cases, acceptance criteria | `~/ai/psaios/psplan/templates/requirements/prd.md` |
| **architecture.md** | 6h | Technical design, data models, deployment | `~/ai/psaios/psplan/templates/technical/architecture.md` |
| **test-plan.md** | 4h | Testing strategy, coverage targets | `~/ai/psaios/psplan/templates/execution/test-plan.md` |

**Total Time:** 16 hours (2–3 days focused work)  
**ROI:** Saves 40+ hours of rework during GATE 2 implementation  
**Next Gate:** GATE 1 Approval → Ready for GATE 2

---

## Your Content for RAG Knowledge Base

### Primary Sources (To Include)
1. **Resume** (detailed, multi-format)
   - Current role: IT Manager @ Law Firm
   - 26 years enterprise infrastructure experience
   - All past roles, accomplishments, metrics

2. **Website** (cwetzel.com pages)
   - Summary: IT background, current responsibilities
   - Experience: Detailed job descriptions, accomplishments
   - Projects: Case studies (SOC2, AVD migrations, SAP integration)
   - Education: Certifications, training
   - Volunteer: Community contributions

3. **GitHub** (public repos)
   - gentoo-machines (kernel configs, system administration)
   - Any other public repositories

4. **LinkedIn** (profile summary, experience section, recommendations)

5. **Case Studies** (create 3–5 one-pagers)
   - **SOC2 Type II Compliance:** Audit process, hardening steps, documentation
   - **Azure VDI Migration:** 120→200 user scaling, regional settings, backup strategy
   - **SAP Business One Integration:** MSSQL backend, WMS integration, global deployment
   - **Disaster Recovery Planning:** BDR approach, off-site backups, failover testing
   - **VMware Virtualization:** P2V migration strategy, infrastructure design

### RAG Index Structure
```
Knowledge Base: Chris Wetzel (IT Professional)
├── About (profile, 26 years experience, current role)
├── Expertise (infrastructure, security, compliance, databases)
├── Projects
│   ├── SOC2 Type II Compliance
│   ├── Azure Virtual Desktop Migrations
│   ├── SAP Business One Integration
│   ├── Disaster Recovery Planning
│   └── VMware Virtualization & P2V
├── Skills (PowerShell, MSSQL, VMware, Azure, AWS, Linux, Windows Server)
├── Technology Stack (Windows Server, Ubuntu, Azure, AWS, VMware, SAN/NAS)
└── Industry Expertise (Enterprise IT, Law Firms, Compliance, Security)
```

---

## Recommended GATE 1 Document Customizations

### 1. .cursorrules (AI Guardrails)
**Key additions for your context:**
```
# Code Style
- All imports alphabetized, grouped (stdlib, third-party, local)
- Type hints on all public functions
- Docstrings: 1-line for simple, multi-line for complex

# Security (Enterprise Context)
- NEVER log customer data or sensitive queries
- NEVER commit secrets (API keys, DB passwords, JWT secrets)
- ALWAYS validate input (SQL injection, prompt injection prevention)
- ALWAYS encrypt sensitive data in transit + at rest

# Compliance (Law Firm Context)
- ALWAYS document data retention policies
- ALWAYS implement audit logging (who accessed what, when)
- ALWAYS enforce row-level security (tenant isolation)
- Document every security-relevant decision in COMPLIANCE.md

# Testing
- Unit tests: auth, validation, core services (80%+ coverage)
- Integration tests: API endpoints, database operations
- Security tests: RLS enforcement, data isolation, auth bypass attempts
- Edge cases: null, empty, max-size, concurrent requests
```

### 2. prd.md (Product Requirements)
**Key additions for your personas:**

```markdown
## Personas (Based on Chris's Background)

### Persona 1: IT Manager
- Currently: Manages enterprise infrastructure, compliance, vendors
- Pain: Document review at scale (SOC2 audits, vendor contracts, IT policies)
- Budget: $500–$2,000/month for AI tooling
- Success: "Reviewed 100 contracts in 10 hours instead of 40 hours"

### Persona 2: Consultant
- Currently: Advises clients on infrastructure, compliance, security
- Pain: Rapid analysis of client documents (contracts, RFPs, compliance docs)
- Budget: $29–$99/month for AI tools
- Success: "Extracted risk factors from 50-page SaaS contract in 5 minutes"

### Persona 3: Law Firm Associate
- Currently: Contract review, due diligence
- Pain: Tedious document analysis, highlight key clauses
- Budget: $49–$199/month for specialized tools
- Success: "Identified red flags in contract before partner review"

## Use Cases (Real Examples from Your Experience)

### Use Case 1: Compliance Document Analysis
"Chat with SOC2 audit guide — what remediation steps apply to our environment?"
Expected Response: Lists SOC2 requirements, gaps in current setup, remediation steps

### Use Case 2: Contract Risk Assessment
"Does this SaaS contract include IP ownership of our data?"
Expected Response: Extracts relevant clauses, identifies risks, suggests redlines

### Use Case 3: Infrastructure Knowledge Base
"What's the process for migrating to Azure Virtual Desktop at scale?"
Expected Response: Describes AVD migration strategy, 200-user example, lessons learned

### Use Case 4: Regulatory Policy Lookup
"What are our backup and retention requirements per compliance policy?"
Expected Response: Cites specific policy sections, retention timeline, implementation
```

### 3. architecture.md (Technical Design)
**Key additions for your infrastructure:**

```markdown
## Stack Decisions (Enterprise-Grade)

### Model & Inference
- **Model:** Llama 2 70B (open license, HIPAA/compliance-friendly)
- **Quantization:** bfloat16 (no quality loss, 40GB fits on 2x A4500s)
- **Inference Engine:** vLLM (100+ tok/sec throughput, batching)
- **Context Window:** 4096 tokens (documents up to ~3000 words)

### Security & Compliance (Law Firm Context)
- **Row-Level Security:** PostgreSQL RLS (Tenant A cannot see Tenant B's data)
- **Audit Logging:** Every inference logged (user, query, response, timestamp)
- **Encryption:** TLS in transit, encrypted at rest (PostgreSQL pgcrypto)
- **Data Retention:** Configurable per tenant (GDPR/SOC2 compliance)
- **Self-Hosted:** No external APIs, no vendor data training

### Infrastructure Topology
- **Cloud (Edge):** $5/mo Ubuntu VPS
  - React frontend (static assets)
  - Nginx reverse proxy + SSL
  - FastAPI middleware + auth
  - Redis caching layer
  
- **Home (Compute Core):** Your Gentoo + 2x A4500s
  - vLLM inference engine
  - PostgreSQL database
  - Qdrant vector DB
  - GitHub webhook receiver
  
- **Connection:** WireGuard encrypted tunnel (203.0.113.0/24)
  - Latency: <50ms
  - Throughput: 300 Mbps available
  - Reliability: Monitored, alerts on disconnection

## Data Models (From Your Expertise)

### Core Tables (Compliance-Aligned)
- tenants (multi-tenant isolation)
- users (fine-grained access control)
- api_keys (programmatic access, audit trail)
- chat_sessions (conversation isolation)
- chat_messages (audit log: who said what, when)
- usage_metrics (token counting for billing)
- invoices (audit trail for payment processing)

### Security Model
- Row-Level Security at DB level (defense in depth)
- JWT auth at API level (prevent token theft)
- API key hashing (irreversible, like passwords)
- Audit logging (every inference, every data access)

## Deployment & Operations (Enterprise-Ready)

### Monitoring (Compliance Requirement)
- Latency (p50, p99) — alert if > 500ms
- Error rate — alert if > 1%
- GPU utilization — alert if > 90% (queue buildup)
- Data integrity — hourly audit checks

### Disaster Recovery
- Backup: Daily automated PostgreSQL backups (off-site to S3)
- Restore test: Monthly validation (test database)
- Rollback: Previous model version always available (< 5 minutes)
- Failover: Cloud-only mode if WireGuard tunnel fails (degraded service)

### Compliance Reporting
- Audit logs queryable by date, user, action
- Retention: Configurable per tenant (3mo–7yr)
- Export: CSV/JSON for compliance audits
```

### 4. test-plan.md (Testing Strategy)
**Key additions for enterprise context:**

```markdown
## Security Tests (Compliance Critical)

### RLS Enforcement
- Tenant A user cannot query Tenant B's data (test via direct SQL)
- JWT token for wrong tenant rejected (test via API)
- API key hashing (verify plaintext key != stored hash)

### Compliance & Audit
- Every inference logged with: user_id, tenant_id, timestamp, tokens, response_length
- Audit logs immutable (no UPDATE/DELETE, only INSERT)
- Data retention enforced (old logs auto-purged per policy)

### Data Isolation
- Tenant A's knowledge base not visible to Tenant B (vector search isolated)
- Chat history only accessible to creating user + admins
- Deleted data is irrecoverable (no soft deletes)

## Performance Tests (Enterprise SLAs)

### Latency
- p50 latency < 100ms (first token)
- p99 latency < 500ms (first token)
- Full response < 10 seconds (for 1000-token response)

### Throughput
- Single GPU inference: 50+ tok/sec
- Dual GPU (tensor parallel): 100+ tok/sec
- Concurrent users: 32–64 without queuing

### Resource Usage
- GPU memory: 38GB / 40GB available
- PostgreSQL connections: < 20 active
- Redis memory: < 5GB for session cache

## Accuracy Tests (Document-Centric)

### RAG Relevance
- Document retrieval: Top-5 results include answer 90% of the time
- Hallucination rate: < 1% (model makes up facts)
- Prompt injection: Cannot bypass prompt with user input

### Compliance-Specific
- Extract requirements from policy doc: 95%+ accuracy
- Identify risks in contract: Recall > 0.9 (don't miss red flags)
- Summarize compliance audit: Accuracy validated by human review
```

---

## Timeline: Next 30 Days

### Days 1–3: GATE 1 Planning (16 hours)
- [ ] Create `.cursorrules` (2h) — Code style, security, compliance, testing rules
- [ ] Create `prd.md` (4h) — Personas, use cases, acceptance criteria, based on your background
- [ ] Create `architecture.md` (6h) — Stack, models, deployment, security/compliance details
- [ ] Create `test-plan.md` (4h) — Testing strategy, performance targets, compliance tests
- [ ] Review all documents (1h) — Verify alignment, sign off on GATE 1 approval

### Days 4–20: GATE 2 Development (120 hours)
**Week 1 (40h):**
- [ ] Chat streaming endpoint (`/ws/chat`)
- [ ] RAG pipeline (Qdrant retrieval + context building)
- [ ] Knowledge base CRUD (upload, index, delete documents)
- [ ] GitHub webhook integration (auto-reindex)

**Week 2 (40h):**
- [ ] React frontend (dashboard, signup, login, chat UI)
- [ ] Database migrations (all tables)
- [ ] Auth system (complete implementation)
- [ ] Tests (unit + integration, 80%+ coverage)

**Week 3 (40h):**
- [ ] Stripe integration (checkout, webhook handler, usage tracking)
- [ ] Monitoring + logging (Prometheus metrics, Grafana dashboard)
- [ ] Documentation updates (README, architecture, runbooks)
- [ ] Load testing (50 concurrent users)

### Days 21–25: GATE 3 Testing & Review (20 hours)
- [ ] Code review (functional + security audit)
- [ ] Performance testing (latency, throughput, concurrent users)
- [ ] Security testing (RLS, auth, data isolation)
- [ ] Compliance validation (audit logs, data retention)

### Days 26–27: GATE 4 Deployment (8 hours)
- [ ] Cloud server setup (Ubuntu, Docker, Nginx)
- [ ] WireGuard tunnel (home ↔ cloud)
- [ ] Production deployment (first deploy)
- [ ] Health checks (monitoring active)

### Days 28–30: GATE 5 Soft Launch (16 hours)
- [ ] Closed beta (friends + early customers)
- [ ] Monitor for 24h (latency, errors, usage)
- [ ] Fix issues found
- [ ] Lessons learned (document for next iteration)

---

## Success Criteria (MVP Definition)

### Launch Blockers (All Must Pass)
- [ ] First token latency < 200ms
- [ ] Throughput > 100 tok/sec
- [ ] Stripe integration works (test + live modes)
- [ ] JWT auth functional (signup/login/refresh)
- [ ] Database migrations apply cleanly
- [ ] Health check returns 200 OK
- [ ] Docker build succeeds
- [ ] GitHub Actions CI/CD passes
- [ ] WireGuard tunnel stable for 24h

### Quality Targets (Should Have)
- [ ] Test coverage ≥ 80%
- [ ] Type hints ≥ 90%
- [ ] RAG relevance ≥ 0.75
- [ ] Zero OWASP Top 10 findings
- [ ] API docs available at `/docs`

### Polish (Nice to Have)
- [ ] React dashboard fully styled
- [ ] Admin panel for user management
- [ ] Advanced monitoring dashboard

---

## What Makes This Different

This SaaS isn't just "another AI chatbot." It's positioned as:

**"Self-hosted AI for compliance and contract analysis,  
built by an IT Manager with 26 years enterprise experience.  
No external APIs. No data training. Enterprise-grade security."**

Your background + this framework = **credibility at scale.**

---

**Current Status:** Framework Complete, Professional Context Captured, Ready to Execute  
**Next Step:** Create GATE 1 documents (16 hours) → GATE 1 Approval → Begin GATE 2 Development  
**Repository:** github.com/cdnwetzel/portfolio-ai-saas

---

**Questions before you start GATE 1 planning?**

1. Any adjustments to the personas or use cases based on your actual contacts?
2. Specific compliance frameworks to emphasize (SOC2, GDPR, HIPAA, etc.)?
3. Any additional content sources to include in the RAG (published articles, blog posts)?
4. Timeline flexibility (30 days aggressive, or more realistic 6–8 weeks)?
5. Revenue priority (launch without billing, or must have Stripe working)?

---

**Last Updated:** 2026-06-06  
**Status:** Ready for Your Input
