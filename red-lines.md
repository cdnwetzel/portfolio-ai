# Red Lines — Absolute Prohibitions

**Project:** Portfolio AI SaaS  
**Purpose:** Define non-negotiable constraints. Violating any of these stops the project.  
**Owner:** Tech Architect  
**Last Updated:** 2026-06-06

---

## Core Security & Privacy

### 1. NEVER store plaintext passwords in database
**Consequence:** Customer account compromise, OWASP A02:2021  
**Enforcement:** Code review checks for `password=` in queries (except hashed columns)

### 2. NEVER log customer data (prompts, queries, or LLM responses)
**Consequence:** GDPR violation, privacy lawsuit, reputational damage  
**Enforcement:** Every log statement reviewed; use hashing for audit trails instead

### 3. NEVER commit secrets (API keys, DB passwords, JWT secrets) to git
**Consequence:** Leaked credentials, account takeover, compliance violation  
**Enforcement:** Pre-commit hook blocks commits with `.pem`, `.key`, `api_key=`, `secret=`

### 4. NEVER train the LLM on customer data without explicit written consent
**Consequence:** Legal liability, GDPR violation, customer lawsuits  
**Enforcement:** Model is inference-only; no fine-tuning on production data

### 5. NEVER expose model weights or internal system details in API responses
**Consequence:** Model theft, competitive disadvantage, security vulnerability  
**Enforcement:** API responses contain only sanitized text, no metadata

---

## Data Integrity & Quality

### 6. NEVER skip data validation on user input
**Consequence:** SQL injection, prompt injection, malformed inference  
**Enforcement:** Pydantic schema validation on all POST/PUT endpoints

### 7. NEVER allow train/validation/test data to overlap (if fine-tuning)
**Consequence:** Inflated metrics, model fails in production, wasted weeks  
**Enforcement:** Data split logic validated with hash-based deduplication

### 8. NEVER deploy a model version without ≥ 10 passing unit tests
**Consequence:** Silent failures, degraded UX, customer churn  
**Enforcement:** CI/CD blocks deployment if test coverage < 80% or any test fails

### 9. NEVER rely on a single accuracy metric (F1, BLEU, ROUGE, etc.)
**Consequence:** Optimization gaming, poor real-world performance  
**Enforcement:** Test suite includes multiple metrics + qualitative review of 10 samples

---

## Infrastructure & Reliability

### 10. NEVER run inference without request timeouts
**Consequence:** Zombie requests, resource exhaustion, service hangs  
**Enforcement:** FastAPI timeout=60s on all inference endpoints

### 11. NEVER expose database connection strings in logs or error messages
**Consequence:** Credential leak, unauthorized database access  
**Enforcement:** Exception handlers sanitize database errors before returning to client

### 12. NEVER rely on a single GPU without failover mechanism
**Consequence:** Single point of failure, complete service outage  
**Enforcement:** Health checks detect GPU memory errors; fallback to cloud inference mode

### 13. NEVER allow unbounded query lengths (prompt size) on inference
**Consequence:** OOM errors, denial-of-service, service crash  
**Enforcement:** Input validation enforces max_tokens=8192 on requests

### 14. NEVER skip SSL/TLS on production endpoints
**Consequence:** Man-in-the-middle attacks, credential interception  
**Enforcement:** HSTS headers enforced; Nginx redirects HTTP → HTTPS

### 15. NEVER commit model weights, large datasets, or checkpoints to git
**Consequence:** Repository bloat, slow clones, storage exhaustion  
**Enforcement:** `.gitignore` enforces; pre-commit hook blocks `.pth`, `.safetensors`, `.bin` files

---

## Operational & Business

### 16. NEVER deploy without monitoring and alerting configured
**Consequence:** Silent failures, undetected degradation, lost revenue  
**Enforcement:** Health checks + Prometheus metrics required before production push

### 17. NEVER charge a customer without validated payment confirmation from Stripe
**Consequence:** Revenue tracking broken, customer disputes, accounting errors  
**Enforcement:** Webhook signature validation on all Stripe events

### 18. NEVER use production customer data for benchmarking or debugging
**Consequence:** Privacy violation, data exposure, compliance breach  
**Enforcement:** Use anonymized test fixtures; audit logs track all data access

### 19. NEVER release a version without updating CHANGELOG or version tag
**Consequence:** Lost deployment history, difficult debugging, compliance audit failure  
**Enforcement:** Release script requires version bump + git tag before push

### 20. NEVER skip database backups
**Consequence:** Data loss, complete service downtime, unrecoverable customer data  
**Enforcement:** Automated daily backups to S3; restore test monthly

---

## Code Quality & Collaboration

### 21. NEVER merge code without at least 1 code review
**Consequence:** Silent bugs, security vulnerabilities, technical debt  
**Enforcement:** GitHub branch protection requires review approval

### 22. NEVER commit code with `# TODO`, `# FIXME`, or `# HACK` without a ticket
**Consequence:** Deferred bugs, lost context, technical debt accumulation  
**Enforcement:** Linter warns; code review enforces ticket linkage

### 23. NEVER change database schema without an Alembic migration
**Consequence:** Rollback failures, data loss, downtime  
**Enforcement:** Migration script is required for any schema change; `alembic upgrade head` must succeed

### 24. NEVER use hardcoded environment variables or magic numbers
**Consequence:** Configuration errors, difficult debugging, non-portable code  
**Enforcement:** All config via .env or pydantic Settings; no string literals > 3 chars in code

### 25. NEVER skip testing for edge cases (empty input, max size, concurrent requests)
**Consequence:** Production bugs, customer-facing failures  
**Enforcement:** Test checklist includes: null, empty string, max_tokens, 100 concurrent reqs

---

## Documentation & Knowledge

### 26. NEVER deploy without updating README.md
**Consequence:** Onboarding delays, operational knowledge lost, hard to reproduce  
**Enforcement:** Code review checklist requires README update for new features

### 27. NEVER ship a new API endpoint without OpenAPI/Swagger documentation
**Consequence:** Clients can't use the API, support burden, API abuse  
**Enforcement:** Endpoint must be accessible at `/docs`; docstring required

### 28. NEVER change critical logic without documenting the "why"
**Consequence:** Future engineers misunderstand decision; tech debt  
**Enforcement:** ADR (Architecture Decision Record) for all major changes

### 29. NEVER suppress warnings in type checking (mypy, pyright)
**Consequence:** Type safety compromised, runtime errors missed  
**Enforcement:** Linter configured with `strict: true`; `# type: ignore` requires comment

### 30. NEVER delete a red-line without consensus from the tech team
**Consequence:** Gradual standard degradation, loss of safety rails  
**Enforcement:** Red-lines reviewed quarterly; any removal requires written justification

---

## Verification Checklist (Before Every Deployment)

```
Pre-Deployment Security Checklist
==================================

Code
☐ No plaintext passwords in code (grep -r "password =" src/)
☐ No API keys in code (grep -r "sk_" src/ | grep -v test)
☐ No `# TODO` without ticket (grep -r "TODO" src/ | grep -v "GitHub#")
☐ All type hints passing (mypy --strict src/)
☐ All tests passing locally (pytest tests/ -v)

Database
☐ No uncommitted schema changes (alembic current = alembic heads)
☐ Backup successful (ls -la /backup/ | head -5)

Configuration
☐ No hardcoded URLs (grep -r "http://" src/ | grep -v test)
☐ All secrets in .env (grep -r "os.getenv" src/ returns only expected vars)

Security
☐ SSL certificate valid (certbot certificates | grep "Valid")
☐ HSTS header enabled (curl -I https://app.yourdomain.com | grep HSTS)
☐ No test credentials in production (grep -r "test_key" .env)

Monitoring
☐ Health check endpoint responds (curl /health returns 200)
☐ Logging configured (tail logs/ shows recent entries)
☐ Alerts configured (check Prometheus targets)

Documentation
☐ README updated (git diff README.md)
☐ API docs generated (curl /docs returns 200)
☐ Deployment notes added (DEPLOYMENT.md updated)
```

---

## Escalation Process

**If you're about to violate a red-line:**

1. **STOP** — Do not commit or deploy
2. **Document** — Write down which red-line, why it seems necessary, what the consequence is
3. **Discuss** — Message the tech lead + team (or add to standup)
4. **Decide** — Either:
   - Fix the code to comply with the red-line (preferred)
   - Update the red-line with team consensus (rare)
   - Accept the risk consciously (very rare, documented)
5. **Log** — Add entry to LESSONS_LEARNED.md with context

---

**Current Status:** GATE 0 (Red-lines defined)  
**Last Updated:** 2026-06-06  
**Review Cadence:** Monthly (quarterly major review)
