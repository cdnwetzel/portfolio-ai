# Portfolio AI - Operations & Monitoring

**Status:** All 5 tiers live (Tier 5 deployed 2026-08-03)  
**Endpoint:** https://dev.cwetzel.com  
**Stack:** React (Tier 5 UX) → Apache (proxy) → FastAPI (backend) → pscode vLLM (T5810) + 14B judge (asrock) + GPU reranker (asrock)  
**Operators:** Claude (monitoring/code), Kimi (hardware/deployment)

---


## Power / UPS constraint (measured 2026-09-01)

**The T5810 exceeds its UPS during generation bursts.** Measured, not estimated:

| | GPU total | Whole box (AC) | vs 330 W UPS |
|---|---|---|---|
| True idle, model resident | 28 W | **~152 W** | 46 % — fine |
| Generation burst (~8 s) | 330 W | **~520 W** | **158 % — overload** |

This workload is **bursty**: ~193-367 generations/day at ~8 s each is a **~2-3 % duty
cycle**, so the box is idle 97 % of the time. On line power the overload is just an alarm.
The real exposure is the compound event — an outage that lands *during* a burst, when the
UPS is over its rating and drops the load instead of transferring. That risks corrupting a
29 GB model load, the Qdrant collection and `verdicts.db`.

**Until a larger UPS is fitted, avoid deliberately sustained GPU load** (graded eval runs,
benchmark sweeps, soak tests) — those push the duty cycle from ~2 % to ~100 % and turn an
unlikely coincidence into a near-certainty. Normal visitor traffic is fine.

### TEMPORARY measures while the UPS is undersized (2026-09-01, revert after fitting)

| Change | From | To | Effect |
|---|---|---|---|
| `SMOKE_INTERVAL_SEC` | 1800 (30 min) | **86400** | E2E parked to ~1/day (pre-2026-08-31 cadence); removes ~25 min/day of self-inflicted burst load |
| GPU power cap | — | **left at 165 W** | see below — the cap is not the lever |

**The power cap is NOT the lever, and was deliberately restored to 165 W.** Both settings
overload the UPS during a burst — 165 W → ~520 W (158 %), 130 W → ~440 W (133 %) — and a UPS on
battery trips at either. Lowering it changes the depth of an overload that trips regardless.

Worse, it is marginally *counterproductive*: a generation takes ~8.4 s at 165 W versus ~8.9 s at
130 W, so the higher cap finishes sooner and leaves a **shorter window** in which an outage
would hurt. Same energy, less time exposed. Fitting under 330 W would need ~79 W/card, which is
not a usable configuration.

**Duty cycle is the lever.** Exposure is "fraction of the day spent in a burst", and the only
thing that moved it materially was self-inflicted load: the E2E probe at 30-min intervals added
~25 min/day against organic traffic of ~26-49 min/day, roughly *doubling* it. Parking that is
worth far more than any cap change.

**Until the 1500VA/1000W lands:** no evals, benchmark sweeps, soak tests or reindex-plus-eval
cycles. Organic traffic is fine. **Revert `SMOKE_INTERVAL_SEC` to 1800 after fitting.**

Power/utilisation metrics are sampled every minute to `/var/log/power-metrics.csv`
(metadata only — watts, temps, utilisation; never request content, per red-lines #2).
Report with `/usr/local/bin/power-report.py`.

Sizing, integration requirements and the resume procedure for the paused context-window
experiment: [`plans/ups-sizing-2026-09-01.md`](plans/ups-sizing-2026-09-01.md).

## System Status

### Services (cwetzel.com)

| Service | Port | Status | Auto-start | Restart |
|---------|------|--------|-----------|---------|
| api-proxy | 8000 | ✅ Running | ✅ Enabled | Always |
| apache2 | 80/443 | ✅ Running | ✅ Enabled | On-failure |
| portfolio-ai-tunnel | 8001/8004/8005/8006/6333/8007 | ✅ Running | ✅ Enabled | Always |
| portfolio-health.timer | — | ✅ Running | ✅ Enabled | Timer (5 min) |

### Services (T5810)

| Service | Port | Status | Usage |
|---------|------|--------|-------|
| labrouter | 8004 | ✅ Running | contract port; fronts the vLLM slots. supervise-daemon, respawn_max=0 (2026-08-31) |
| vllm-qwen38 | 8007 | ✅ Running | Qwen3.8-27B-FP8, 32K ctx, TP=2, CUDA graphs (~29 tok/s) |
| Qdrant | 6333 | ✅ Running | Vector DB — `home/qdrant/qdrant.openrc` (IaC) |
| embed-service | 8005 | ✅ Running | BAAI/bge-base-en-v1.5, 768-d (CPU) |
| rerank-service | 8006 | ✅ Running | bge-reranker-base (CPU) |

### Services (asrock B550 — verifier node)

| Service | Port | Status | Usage |
|---------|------|--------|-------|
| verifier-service | 8007 | ✅ Running | Out-of-band faithfulness judge (fail-open). Binds `VERIFIER_BIND` (LAN IP, not 0.0.0.0); reached via the tunnel's `-L 8007`. |

---

## Monitoring Commands

### Check all services running

```bash
# Quick status
ssh root@cwetzel.com "systemctl status api-proxy apache2 portfolio-ai-tunnel"

# Port status
ssh root@cwetzel.com "ss -tlnp | grep -E ':(8000|80|443)'"
```

### Check vLLM connectivity

```bash
# From cwetzel.com
ssh root@cwetzel.com "curl -s http://ai.cwetzel.com:8004/v1/models | head -c 100"

# From T5810 (for debugging)
ssh root@t5810.local "curl -s http://localhost:8004/v1/models | head -c 100"
```

### Check tunnel status

```bash
# Tunnel process
ssh root@cwetzel.com "ps aux | grep ssh | grep -v grep | grep tunnel"

# Tunnel logs (last 20 lines)
ssh root@cwetzel.com "journalctl -u portfolio-ai-tunnel -n 20 --no-pager"
```

### Check proxy logs

```bash
# Real-time FastAPI logs
ssh root@cwetzel.com "journalctl -u api-proxy -f"

# Real-time Apache logs
ssh root@cwetzel.com "tail -f /var/log/apache2/access.log"
```

---

## Automated Health Monitoring & Alerting

**Motivation:** the 2026-06-14 outage — Qdrant crash-looped and latched off, so every query
answered *"I don't have that documented in my knowledge base"* — went undetected because nothing
paged a human and the per-service `/health` endpoints all return a trivial `{"status":"ok"}` that
can't see a Qdrant serving 0 points. This layer fixes that.

**Design:** monitor + **alert only** (no auto-restart of stateful services — a blind respawn loop
is what hid the outage). One deep VPS-side aggregator covers every failure mode reachable through
the tunnel; an external dead-man's switch covers the VPS itself dying; a home-side canary is the
second, public-path vantage.

### Components

| Component | Where | Schedule | What it catches |
|-----------|-------|----------|-----------------|
| `scripts/health_aggregate.py` (`portfolio-health.timer`) | VPS | every 5 min | cheap probes: proxy, vLLM (`/v1/models`), **Qdrant points_count**, embed, rerank, verifier (`--no-smoke` — no LLM load) |
| `portfolio-health-heartbeat.timer` | VPS | daily 12:00 UTC | full run **incl. E2E WS query**; sends one "all green" ntfy/day so silence never means "monitor dead"; feeds healthchecks.io |
| `portfolio-health-alert.service` | VPS | `OnFailure=` | monitor-of-monitor: pages if the probe process itself crashes |
| healthchecks.io ping | external | on every green run | dead-man's switch — alerts if the VPS/monitor stops pinging |
| ~~`scripts/selftest-canary.sh` (cron)~~ | T5810 | **NOT INSTALLED** | verified 2026-08-31: not in any runlevel, no cron entry. Do not count as coverage. |
| E2E smoke inside `health_aggregate.py` | VPS | every 30 min (`SMOKE_INTERVAL_SEC`) | real WS query; this is what actually caught the 2026-08-26 outage |

**Alert channel:** ntfy.sh push to a private topic. Config (not in the repo):
`/etc/default/portfolio-health` on the VPS (`NTFY_URL`, `HEALTHCHECKS_URL`) and
`/etc/portfolio-canary.env` on the T5810 (`NTFY_URL`). Alerts fire **only on state transitions**
(healthy→down pages; down→healthy sends "recovered") — a sustained outage is not re-paged every cycle.

### Severity map (what pages vs. what doesn't)

| Signal | Severity | Pages? |
|--------|----------|--------|
| tunnel down / proxy / vLLM / embed down | CRITICAL | yes |
| **Qdrant up but points_count == 0** (the outage signature) | CRITICAL | yes |
| E2E smoke: a grounded question returns the fallback | CRITICAL | yes |
| rerank down (fails open to cosine order) | DEGRADED | heartbeat only |
| verifier / Ollama down (fail-open, chat unaffected) | INFO | no |

### Provisioning / commands

```bash
# Install/refresh the VPS monitor (deploys scripts + systemd units, seeds config):
./cloud/setup-health-monitor.sh

# One-off manual probe (prints per-service status; exit 1 if any CRITICAL):
ssh root@cwetzel.com "cd /opt/portfolio-health && python3 health_aggregate.py"

# Monitor logs:
ssh root@cwetzel.com "journalctl -u portfolio-health.service -n 30 --no-pager"

# Install the durable Qdrant unit on the T5810 (see runbook below):
./home/setup-qdrant.sh
```

---

## Restart Procedures

### Restart specific service

```bash
# FastAPI proxy
ssh root@cwetzel.com "systemctl restart api-proxy"

# Apache
ssh root@cwetzel.com "systemctl restart apache2"

# SSH tunnel
ssh root@cwetzel.com "systemctl restart portfolio-ai-tunnel"
```

### Full stack restart (if needed)

```bash
ssh root@cwetzel.com "systemctl restart portfolio-ai-tunnel api-proxy apache2"
sleep 5
# Verify
ssh root@cwetzel.com "systemctl status api-proxy apache2 portfolio-ai-tunnel"
```

---

## Performance Metrics

### Response latency (from user browser)

- Frontend load: <1s (static HTML + Tailwind CDN)
- API response: <2s (vLLM p50 latency <100ms + network overhead)
- WebSocket streaming: Real-time token generation

### System load

```bash
# cwetzel.com (1 core, 1GB RAM)
ssh root@cwetzel.com "uptime && free -h"

# T5810 (44 cores, lots of RAM)
ssh root@t5810.local "uptime && nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv"
```

### Tunnel health

```bash
ssh root@cwetzel.com "journalctl -u portfolio-ai-tunnel --since='1 hour ago' | grep -i 'error\|fail' || echo 'No errors in last hour'"
```

---

## Troubleshooting

### Frontend not loading

```bash
# Check Apache vhost
ssh root@cwetzel.com "apache2ctl configtest"
ssh root@cwetzel.com "ls -la /var/www/dev.cwetzel.com/"

# Check SSL cert
ssh root@cwetzel.com "openssl s_client -connect dev.cwetzel.com:443 -brief"
```

### Chat not responding

```bash
# Check FastAPI health
ssh root@cwetzel.com "curl -s http://127.0.0.1:8000/health"

# Check vLLM via tunnel
ssh root@cwetzel.com "curl -s -m 5 http://ai.cwetzel.com:8004/v1/models | head -c 50"

# Check tunnel connectivity
ssh root@cwetzel.com "journalctl -u portfolio-ai-tunnel -n 5 --no-pager"
```

### Every query answers "I don't have that documented" (Qdrant latched off — 2026-06-14 outage class)

Signature: the site loads and streams, but **every** answer is the fallback refusal. Root cause is
almost always retrieval returning empty — usually Qdrant down or serving 0 points.

```bash
# 1. Confirm which stage is broken (from the VPS, through the tunnel):
ssh root@cwetzel.com "cd /opt/portfolio-health && python3 health_aggregate.py"
#    Look for: [CRITICAL] Qdrant unreachable  OR  points_count=0

# 2. On the T5810, inspect + recover Qdrant:
ssh root@ai.cwetzel.com "tail -n 30 /var/log/qdrant.log"     # look for PermissionDenied on ./snapshots
ssh root@ai.cwetzel.com "rc-service qdrant status"
ssh root@ai.cwetzel.com "rc-service qdrant zap && rc-service qdrant start"   # zap clears a crashed/latched state

# 3. Verify it came back green with points:
ssh root@ai.cwetzel.com "curl -s http://127.0.0.1:6333/collections/documents | head -c 300"
#    Expect: status:green, points_count > 0

# 4. If it crash-loops on a PermissionDenied for ./snapshots/tmp, the OLD init bug is present.
#    Install the durable unit (correct CWD + logging, clears the stale root-owned /snapshots):
./home/setup-qdrant.sh

# 5. If Qdrant is green but points_count is 0, the collection is empty — rebuild the index:
./scripts/reindex_kb.sh
```

The durable fix (`home/qdrant/qdrant.openrc`) sets the daemon's CWD to `/home/chris/qdrant-data`
so its relative `./snapshots` cleanup can never again hit the root-owned `/snapshots`, and uses
`output_log`/`error_log` instead of a shell redirect passed as bogus argv.

### High latency or timeouts

```bash
# Check T5810 GPU memory
ssh root@t5810.local "nvidia-smi"

# Check T5810 load
ssh root@t5810.local "uptime"

# Check network between cwetzel.com and T5810
ssh root@cwetzel.com "ping -c 1 98.110.86.95"
```

---

## Deployment Checklist

### Initial Setup ✅

- [x] SSH tunnel (cwetzel.com ↔ T5810)
- [x] FastAPI proxy running
- [x] Apache vhost configured
- [x] SSL certificate issued
- [x] Frontend deployed

### Manual QA ⏳

- [ ] Load https://dev.cwetzel.com in browser
- [ ] Click "Start Chat"
- [ ] Type a question (e.g., "What is RAG?")
- [ ] Confirm response streams in real-time
- [ ] Check no JavaScript errors (DevTools console)
- [ ] Test mobile responsiveness

### Performance Validation ⏳

- [ ] Measure first-token latency (should be <100ms)
- [ ] Measure sustained throughput (should be >50 tokens/sec)
- [ ] Monitor for any connection drops over 5 min conversation
- [ ] Check system load on T5810 during sustained usage

### Production Checklist (Later)

- [x] Set up monitoring/alerting (deep health aggregator + ntfy + healthchecks.io dead-man's switch; see "Automated Health Monitoring & Alerting")
- [ ] Configure log rotation
- [ ] Set up automated backups
- [ ] Prepare runbooks for common incidents
- [ ] Plan capacity scaling
- [ ] DNS cutover to cwetzel.com

---

## Uptime Target

**MVP:** 99%+ uptime (auto-restart on failure)  
**Goal:** All services remain running across reboots

---

## Health Verification (The Truth Test)

This section defines what "green across the board" actually means, and how to test it. Operators (Claude, Kimi) use this to avoid relearning the system state.

### Three Layers of Truth

#### Layer 1: VPS Health Aggregator (Automated)
Runs every 5 minutes on VPS. **Limitation:** Can't always reach verifier via tunnel, but that doesn't mean it's broken.

```bash
ssh root@cwetzel.com "journalctl -u portfolio-health.service -n 1 --no-pager | grep -E 'OK|INFO|CRITICAL'"
```

**What GREEN looks like:**
- Proxy: OK ✓
- vLLM: OK ✓
- Qdrant: OK (62 points) ✓
- Embed: OK ✓
- Rerank: OK ✓
- Verifier: OK or INFO (both acceptable) ✓

**Known false positive:** Verifier shows INFO="unreachable" even when working. Reason: service only listens on LAN IP (10.0.1.115), not routable via tunnel. **Ignore if E2E chat works.**

#### Layer 2: E2E Chat Test (The Real Test)
This is the truth. If the chat works end-to-end, the system is working, period.

```bash
# Option A: Browser
# Go to https://dev.cwetzel.com
# Query: "What GPU is in the verifier box?"
# Expected: "…an RTX 5060 Ti GPU"

# Option B: CLI
python3 scripts/selftest.py --url "wss://dev.cwetzel.com/ws/chat"
```

**What GREEN looks like:**
- Response received ✓
- Response is grounded (sources retrieved) ✓
- Response is correct (matches KB) ✓
- TTFB < 10 seconds ✓
- Total latency < 30 seconds ✓
- No errors ✓
- Self-test: 4/4 smoke checks pass ✓

#### Layer 3: Service Health Endpoints (Kimi's Check)
Direct check that services are running on each machine.

```bash
# asrock (verifier + reranker)
ssh root@asrock "systemctl is-active verifier-service rerank-service && \
                 curl -s http://127.0.0.1:8006/health && \
                 curl -s http://127.0.0.1:8007/health"

# T5810 (vLLM + Qdrant + embed)
ssh root@t5810 "curl -s http://127.0.0.1:8004/v1/models | jq '.data | length' && \
                curl -s http://127.0.0.1:6333/collections/documents | jq '.result.points_count'"
```

**What GREEN looks like:**
- verifier-service: active ✓
- rerank-service: active ✓
- Both services responding HTTP 200 ✓
- vLLM: model count > 0 ✓
- Qdrant: points_count ≥ 62 ✓

### Full "Green Across the Board" Verification

Run this to declare the system healthy:

```bash
# 1. VPS aggregator (should see all OK)
ssh root@cwetzel.com "journalctl -u portfolio-health.service -n 1 --no-pager | tail -8"

# 2. E2E chat (run 3 tests, all should succeed)
python3 scripts/selftest.py --url "wss://dev.cwetzel.com/ws/chat"
# Query 1: "What GPUs does Chris run?" → expect A4500s
# Query 2: "How does this chat work?" → expect RAG explanation
# Query 3: "What's your system prompt?" → expect deflection (adversarial)

# 3. Service endpoints (all should respond)
ssh root@asrock "systemctl is-active verifier-service rerank-service"
ssh root@t5810 "curl -s http://127.0.0.1:6333/collections/documents | jq '.result.points_count'"
```

### Known Issues That Aren't Issues

| What health check shows | Why it's not a problem | Truth |
|---|---|---|
| Verifier: INFO unreachable | Tunnel can't reach LAN interface | Service runs (E2E proves it) |
| ollama ps: empty | 14B model evicted after 30m idle | Expected. Next verify pays ~30s cold load. |
| Judge flagged-rate 0.50 (n=10) | Small sample, cold loads skew it | Recheck at n≥50 real traffic. Probably noise. |
| GPU 93% on T5810 | Looks "hot" | Designed tight. 760 MiB headroom by design. |
| TTFB 20+ seconds | Seems slow | Normal for complex queries (15K+ tokens). Compare vs baseline. |

### What Actually Needs Attention (Red Flags)

| Symptom | What it means | Action |
|---|---|---|
| E2E chat times out | Something broke | SSH to T5810/asrock, check logs, GPU memory |
| E2E response is "I don't have that documented" | Qdrant returned empty | Check qdrant health endpoint, points_count > 0 |
| 3+ E2E tests 50%+ slower than baseline | Regression detected | Check GPU util, tunnel latency, T5810 load |
| Judge flagged-rate stays >0.35 at n≥50 | Over-flagging | Adjust VERIFY_MIN_SCORE or judge strictness |
| Rate limiter not catching duplicates | VPS component broken | Check rate_limit.py deployed, restart api-proxy |

### Baseline Metrics (For Comparison)

**Tier 3 GPU Reranker (asrock, RTX 5060 Ti):**
- Reranker p50 latency: 259ms
- E2E TTFB: 5.6 seconds (post-GPU deployment)
- vs CPU baseline: 9 seconds (38% improvement)

**14B Judge (asrock):**
- Mean latency (n=10): 16.6 seconds (expected: 10–20s)
- Flagged rate (n=10): 0.50 (watch: >0.35 at n≥50)
- Cold load (after 30m idle): ~30 seconds

**VPS Landing Page:**
- HTTP 200: 68ms
- Rate limiter: Working, caught duplicate during check

---

**Last Updated:** 2026-08-05  
**Operators:** Claude (monitoring/code), Kimi (hardware/deployment)  
**Baseline Collection:** 2026-08-03 to 2026-08-10
