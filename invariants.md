# Invariants — Architectural Constants

**Project:** Portfolio AI SaaS  
**Purpose:** Define properties that MUST always be true in production.  
**Owner:** Tech Architect  
**Verification:** Every release checklist validates all invariants.  
**Last Updated:** 2026-06-06

---

## Invariant #1: Model Versioning is Immutable

**Statement:** Every inference artifact is tagged with commit hash + model version + inference timestamp.

**Why:** Reproducing a bug requires knowing exactly what code and model ran.

**How to Verify:**
```bash
# Check that every inference log contains model version
psql -c "SELECT DISTINCT model_version FROM inference_logs WHERE timestamp > NOW() - 1h;"

# Should return exactly 1 version (the currently deployed version)
# If >1 version, rollout is incomplete
# If 0 versions, model versioning is broken
```

**Enforcement:**
- [ ] vLLM startup logs the model version
- [ ] Every inference request logs: `model_version`, `inference_timestamp`, `commit_hash`
- [ ] Database schema enforces non-null on `model_version` column

---

## Invariant #2: Data is Reproducible

**Statement:** Training/indexing inputs are version-controlled (or hash-documented) so we can rebuild the exact system.

**Why:** If a user asks "why did the model give this answer?" we need to re-index with the same data.

**How to Verify:**
```bash
# Check that training data is documented in git
git log --all --grep="training_data" --oneline

# Or check that data hash is in commit message
git show HEAD | grep -i "data_hash\|dataset_hash"

# Should return a valid hash and timestamp
```

**Enforcement:**
- [ ] Every commit touching data includes hash in message: `Data hash: abc123def456`
- [ ] Data is either:
  - Small enough to be in git (< 100MB), OR
  - Stored in S3 with hash in git commit, OR
  - Documented in data/README.md with source + version
- [ ] Qdrant vector DB is re-indexable from source documents

---

## Invariant #3: Input/Output Schemas are Always Validated

**Statement:** Every API request is validated against Pydantic schema before processing. Every response conforms to documented schema.

**Why:** Prevents silent data corruption, prompt injection, malformed LLM input.

**How to Verify:**
```bash
# Check that validation errors are caught in unit tests
pytest tests/test_validation.py -v

# In production: zero schema mismatch errors in logs
curl https://api.yourdomain.com/health/schema-errors

# Should return 0 errors in last 24h
```

**Enforcement:**
- [ ] Every endpoint declares request body with Pydantic model
- [ ] Every endpoint declares response body with Pydantic model
- [ ] Type hints cover all parameters (mypy --strict)
- [ ] Validation tests include: null, empty, oversized, malformed JSON

---

## Invariant #4: Every Inference is Logged

**Statement:** Every inference request logs: input_hash, model_version, tokens_used, latency_ms, confidence_score.

**Why:** We need telemetry to detect accuracy degradation, track costs, debug user issues.

**How to Verify:**
```bash
# Check inference log completeness
psql -c "SELECT COUNT(*) FROM inference_logs WHERE model_version IS NULL OR latency_ms IS NULL LIMIT 1;"

# Should return 0 (no missing data)
# If > 0, logging is broken
```

**Enforcement:**
- [ ] Every `/ws/chat` connection logs start + end event
- [ ] Every token generated includes: session_id, model_version, timestamp
- [ ] Logs are queryable by user, session, date range
- [ ] Log retention: 90 days minimum

---

## Invariant #5: Accuracy/Latency Metrics are Monitored Hourly

**Statement:** System emits and alerts on: inference latency (p50/p99), throughput (tokens/sec), error rate.

**Why:** Silent degradation (model drift, GPU memory leak) is undetectable without metrics.

**How to Verify:**
```bash
# Check Prometheus scrape targets
curl http://localhost:9090/api/v1/targets

# Check latest metric values
curl 'http://localhost:9090/api/v1/query?query=inference_latency_p99_ms'

# Should return metric with timestamp < 5 minutes old
```

**Enforcement:**
- [ ] vLLM exports Prometheus metrics
- [ ] FastAPI middleware logs request latency
- [ ] Grafana dashboard shows last 7 days of latency + errors
- [ ] Alerting: if p99 latency > 500ms OR error_rate > 1%, page on-call

---

## Invariant #6: Rollback is Possible in < 5 Minutes

**Statement:** Previous model/code version can be restored within 5 minutes without manual intervention.

**Why:** If production inference is broken, we need a fast escape hatch.

**How to Verify:**
```bash
# Test rollback procedure
git tag                                    # List all releases
git log --oneline -10                      # View recent releases
docker pull portfolio-saas:v1.2.3          # Verify previous image exists in registry
docker-compose down && docker-compose up   # Re-deploy with previous version

# Time this process: should be < 5 minutes
```

**Enforcement:**
- [ ] Every release creates git tag + Docker image tag
- [ ] Docker images are pushed to registry (or stored locally with `.tar`)
- [ ] Rollback procedure is documented in DEPLOYMENT.md
- [ ] Rollback is tested monthly

---

## Invariant #7: Database Backups are Validated

**Statement:** Daily automated backups exist. Restore test runs monthly. Restore time is logged.

**Why:** Data loss is recoverable only with validated backups.

**How to Verify:**
```bash
# Check backup directory
ls -la /backup/ | wc -l

# Should have ≥ 30 backups (one per day, last 30 days)

# Check restore test log
cat /var/log/backup-restore-test.log | tail -20

# Should show successful restore with timestamp < 30 days old
```

**Enforcement:**
- [ ] Cron job runs daily: `pg_dump | gzip > /backup/saas_$(date +%Y%m%d).sql.gz`
- [ ] Retention: Keep 30 days of backups
- [ ] Monthly restore test: `psql < /backup/latest.sql` on test database
- [ ] Restore time logged; alert if > 30 minutes

---

## Invariant #8: WireGuard Tunnel is Monitored

**Statement:** WireGuard status is checked every 60 seconds. Ping latency is logged. Connection drops trigger alerts.

**Why:** Home ↔ cloud inference depends on this tunnel; failures are silent without monitoring.

**How to Verify:**
```bash
# Check tunnel status
sudo wg show

# Should show:
# - interface: wg0
# - peers: 1 (cloud)
# - latest handshake: < 2 minutes ago

# Check latency
ping -c 1 10.0.0.2

# Should be < 50ms. If > 100ms, investigate.

# Check logs
tail -20 /var/log/wireguard-monitor.log

# Should show pings every 60s with latency values
```

**Enforcement:**
- [ ] Systemd timer runs every 60s: `wg-monitor.sh`
- [ ] Logs include: timestamp, latency, peer handshake age
- [ ] Alert if: handshake > 5 minutes OR latency > 100ms for 3 checks
- [ ] Runbook: How to restart WireGuard if disconnected

---

## Invariant #9: Multi-Tenancy is Enforced at Database Level

**Statement:** PostgreSQL Row-Level Security (RLS) prevents Tenant A from seeing Tenant B's data, even with a compromised JWT.

**Why:** Application bugs can leak data; database-level isolation catches them.

**How to Verify:**
```bash
# Connect as tenant_a user
psql -U tenant_a_user -d saas_prod

# Try to query another tenant's data
SELECT * FROM chat_sessions WHERE tenant_id = 'tenant_b_id';

# Should return empty result (RLS blocks it)

# Check RLS policies are enabled
psql -c "SELECT schemaname, tablename, rowsecurity FROM pg_tables WHERE rowsecurity = true;"

# Should list: chat_sessions, invoices, usage_metrics, etc.
```

**Enforcement:**
- [ ] All tenant-scoped tables have RLS enabled
- [ ] RLS policy: `USING (tenant_id = current_setting('app.tenant_id'))`
- [ ] FastAPI sets `SET app.tenant_id = 'xxx'` on every request
- [ ] Unit tests verify: wrong tenant cannot access data

---

## Invariant #10: API Rate Limiting is Applied

**Statement:** Per-tenant rate limits are enforced: Free tier = 100 req/min, Pro tier = 1000 req/min.

**Why:** Prevents abuse, protects GPU from overload, ensures fair resource allocation.

**How to Verify:**
```bash
# Send 101 requests as free user
for i in {1..101}; do curl -H "Authorization: Bearer $TOKEN" https://api.yourdomain.com/api/chat; done

# Request 101 should return 429 (Too Many Requests)

# Check Redis rate limit key
redis-cli --raw
GET rate_limit:tenant_xyz:minute

# Should show remaining quota
```

**Enforcement:**
- [ ] Redis stores: `rate_limit:{tenant_id}:{period} = remaining_requests`
- [ ] Middleware checks before accepting request
- [ ] Returns 429 with `Retry-After` header
- [ ] Logs all rate limit violations
- [ ] Alert if free tier user hits limit 5+ times/hour

---

## Invariant #11: Security Headers are Always Present

**Statement:** All HTTPS responses include: HSTS, CSP, X-Frame-Options, X-Content-Type-Options.

**Why:** Prevents clickjacking, XSS, MIME-sniffing attacks.

**How to Verify:**
```bash
# Check headers
curl -I https://app.yourdomain.com

# Should include:
# Strict-Transport-Security: max-age=31536000
# Content-Security-Policy: default-src 'self'
# X-Frame-Options: DENY
# X-Content-Type-Options: nosniff

# Automated check
./scripts/check_security_headers.sh

# Should return: "All headers present ✓"
```

**Enforcement:**
- [ ] Nginx config includes security headers
- [ ] FastAPI middleware adds headers if missing
- [ ] Monitoring dashboard alerts if headers are stripped

---

## Invariant #12: Version Information is Always Available

**Statement:** API has `/version` endpoint showing: git commit, release tag, build time, model version.

**Why:** Debugging and support need to know exactly what version is running.

**How to Verify:**
```bash
curl https://api.yourdomain.com/version

# Should return:
# {
#   "commit": "abc123def456",
#   "tag": "v1.0.3",
#   "build_time": "2026-06-06T14:23:45Z",
#   "model": "llama-70b-v1.0"
# }
```

**Enforcement:**
- [ ] Version endpoint is public (no auth required)
- [ ] Version info is baked into Docker image at build time
- [ ] Every release updates VERSION file
- [ ] Health check verifies version endpoint responds

---

## Verification Workflow (Before Every Release)

```bash
#!/bin/bash
# release_checklist.sh

echo "🔍 Verifying Invariants..."

# Invariant 1: Model version in logs
psql -c "SELECT COUNT(DISTINCT model_version) FROM inference_logs WHERE timestamp > NOW() - 1h;" | grep -q "^[ ]*1$" && echo "✓ Inv #1: Model versioning" || echo "✗ FAIL: Inv #1"

# Invariant 2: Data reproducible
git log --oneline -10 | grep -q "data_hash\|dataset" && echo "✓ Inv #2: Data documented" || echo "✗ FAIL: Inv #2"

# Invariant 3: Schemas validated
pytest tests/test_validation.py -q && echo "✓ Inv #3: Schema validation" || echo "✗ FAIL: Inv #3"

# Invariant 4: Logging complete
psql -c "SELECT COUNT(*) FROM inference_logs WHERE model_version IS NULL;" | grep -q "^[ ]*0$" && echo "✓ Inv #4: Logging complete" || echo "✗ FAIL: Inv #4"

# Invariant 5: Metrics available
curl -s http://localhost:9090/api/v1/query?query=inference_latency_ms | grep -q "result" && echo "✓ Inv #5: Metrics available" || echo "✗ FAIL: Inv #5"

# Invariant 6: Rollback possible
git tag | tail -3 | grep -q "v" && echo "✓ Inv #6: Tags exist for rollback" || echo "✗ FAIL: Inv #6"

# Invariant 7: Backups valid
ls /backup/*.sql.gz | wc -l | grep -qE '[0-9]{2,}' && echo "✓ Inv #7: Backups exist" || echo "✗ FAIL: Inv #7"

# Invariant 8: WireGuard connected
ping -c 1 10.0.0.2 > /dev/null && echo "✓ Inv #8: Tunnel connected" || echo "✗ FAIL: Inv #8"

# Invariant 9: RLS enabled
psql -c "SELECT COUNT(*) FROM pg_tables WHERE rowsecurity = true;" | grep -qE '[5-9]|[0-9]{2}' && echo "✓ Inv #9: RLS enabled" || echo "✗ FAIL: Inv #9"

# Invariant 10: Rate limiting active
redis-cli PING | grep -q "PONG" && echo "✓ Inv #10: Rate limiting ready" || echo "✗ FAIL: Inv #10"

# Invariant 11: Security headers
curl -s -I https://api.yourdomain.com | grep -q "Strict-Transport-Security" && echo "✓ Inv #11: Headers present" || echo "✗ FAIL: Inv #11"

# Invariant 12: Version available
curl -s https://api.yourdomain.com/version | grep -q "commit" && echo "✓ Inv #12: Version endpoint" || echo "✗ FAIL: Inv #12"

echo "✅ All invariants verified!"
```

---

**Current Status:** GATE 0 (Invariants defined)  
**Last Updated:** 2026-06-06  
**Review Cadence:** Quarterly + after any production incident
