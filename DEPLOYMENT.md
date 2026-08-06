# Deployment Guide: Portfolio AI Chat

**Status:** Deployed, production  
**Current as of:** 2026-07-24  
**Endpoint:** https://dev.cwetzel.com

---

## Overview

Single-tenant portfolio RAG chat on owned hardware: an Ubuntu VPS (cwetzel.com) serving a
React build and a FastAPI proxy, connected by one SSH tunnel to home GPU boxes (T5810 Xeon,
asrock B550 Ryzen) that run inference, retrieval and verification. No auth, no accounts, no
database — the chat is public and anonymous, and nothing is persisted server-side.

---

## Hardware Topology

```
User Browser
    ↓ HTTPS / WSS
cwetzel.com VPS (Ubuntu, systemd)
├─ apache2                  SSL termination, static React, WSS proxy → 127.0.0.1:8000
├─ api-proxy.service        FastAPI/Uvicorn on 127.0.0.1:8000 (/opt/api-proxy/main.py)
└─ portfolio-ai-tunnel.service  SSH forward tunnel to the T5810
    ↓ SSH tunnel (initiated by the VPS; home services stay LAN-only)
T5810 (Gentoo/OpenRC) — Xeon E5-2699v4, 256 GB ECC, 2x RTX A4500 20 GB (NVLink)
├─ pscode-vllm (OpenRC)     vLLM :8004 — Qwen2.5-Coder-14B-Pscode, BF16, 16K ctx, TP=2
├─ qdrant (OpenRC)          Qdrant :6333 — dense 768-d cosine, collection `documents`
├─ embed-service            bge-base-en-v1.5, CPU, :8005
└─ rerank-service           bge-reranker-base, CPU, :8006
    ↓ the same tunnel forwards :8007 over the home LAN
asrock B550 (Gentoo/OpenRC) — Ryzen 9 5950X, 64 GB, RTX 5060 Ti 16 GB
├─ ollama (OpenRC)          Ollama daemon (judge model host)
└─ verifier-service (OpenRC) faithfulness judge :8007 — Qwen2.5-14B-Instruct via Ollama
```

The asrock GPU was upgraded from a 3060 Ti to the RTX 5060 Ti 16 GB and the judge from
Qwen2.5-7B to Qwen2.5-14B-Instruct (Tier 2, deployed 2026-07-28).

**RAG pipeline:** query → alias-expand → embed (8005) → Qdrant cosine top-15 (6333) →
rerank top-15→5 (8006, ≤2 chunks/doc) → token-budget fit → vLLM stream (8004) →
fire-and-forget faithfulness verify (8007, out-of-band, never blocks the answer).

---

## The SSH Tunnel

`portfolio-ai-tunnel.service` (systemd, on the VPS) holds one `ssh -N` connection from the
VPS to the T5810 and forwards, all bound to `127.0.0.1` on the VPS:

| VPS port | Target | Service |
|----------|--------|---------|
| 8001 | T5810:8001 | reserved, unused |
| 8004 | T5810:8004 | vLLM |
| 8005 | T5810:8005 | embed-service |
| 8006 | T5810:8006 | rerank-service |
| 6333 | T5810:6333 | Qdrant |
| 8788 | T5810:8788 | headroom-lib compressor (optional; `COMPRESS_URL` unset = disabled) |
| 8007 | asrock:8007 | verifier — note: routed **via the T5810** over the home LAN |

Per-machine config lives in `/etc/default/portfolio-ai-tunnel` on the VPS (**not** in the
repo — the repo carries no internal addressing):

```bash
T5810_USER=chris
T5810_HOST=ai.cwetzel.com     # DNS, survives Verizon dynamic-IP rotation
VERIFIER_HOST=<asrock-lan-ip> # asrock's LAN address as resolved FROM the T5810
```

⚠️ Adopting the repo version of the unit requires `VERIFIER_HOST` to be set **first** — an
empty value produces `-L 127.0.0.1:8007::8007` and ssh refuses to start the tunnel.

The proxy reaches every backend at `127.0.0.1` (`VLLM_URL`, `QDRANT_URL`, `EMBED_URL`,
`RERANK_URL`, `VERIFIER_URL` — see `cloud/systemd/api-proxy.service` and its drop-ins).

---

## Deploying

Everything deploys from the repo root. **Production actions need explicit authorization** —
CI deliberately does not deploy (`.github/workflows/ci.yml` runs offline tests only).

```bash
# Code deploy: frontend build → rsync → scp proxy modules → restart → health check →
# live self-test gate (scripts/selftest.py against wss://dev.cwetzel.com/ws/chat).
./cloud/deploy.sh

# Rebuild the Qdrant index from the committed KB (runs the indexer on the T5810 so
# index vectors match query vectors). Wipes and recreates the `documents` collection.
./scripts/reindex_kb.sh

# One-time VPS infra: Apache vhost, SSL, health-monitor timers.
./cloud/setup-proxy-apache.sh
./cloud/setup-health-monitor.sh
```

`deploy.sh` scp's `api-proxy.py` (as `main.py`) plus its local module imports
(`context_manager.py`, `query_expansion.py`, `sparse_bm25.py`, `guardrails.py`,
`verify_gate.py`, `rate_limit.py`) to `/opt/api-proxy/`. `tests/test_deploy_manifest.py`
guards that list: adding an import to `api-proxy.py` without adding the file to
`deploy.sh` fails CI — that exact miss once shipped a crash-looping proxy.

**Out-of-repo config that deploys must preserve (learned 2026-08-06, see DEFECT_LEDGER #5):**
- `/etc/default/portfolio-ai-tunnel` — `T5810_USER`, `T5810_HOST`, `VERIFIER_HOST`,
  `RERANK_HOST`. A missing `*_HOST` value makes that tunnel forward listen-but-dead-end.
- `/etc/systemd/system/api-proxy.service.d/*.conf` — drop-ins carrying `VERIFIER_URL`,
  `VERIFY_MIN_SCORE`, `COMPRESS_*`. Without `VERIFIER_URL` the verifier silently no-ops:
  chat works, zero verdicts, nothing errors.
After any proxy/tunnel redeploy, verify: `curl -s http://127.0.0.1:8007/health` on the VPS
(answers with the judge model name) and a verdict row lands in verdicts.db after a chat.

---

## Startup Sequence

Dependency order — each step's verification must pass before the next matters:

**1. T5810 services (OpenRC):**
```bash
rc-service qdrant status && curl -s http://127.0.0.1:6333/collections
rc-service pscode-vllm status && curl -s http://127.0.0.1:8004/v1/models
rc-service embed-service status && curl -s http://127.0.0.1:8005/health
rc-service rerank-service status && curl -s http://127.0.0.1:8006/health
```
vLLM startup is slow (weights load onto 2 GPUs); `curl /v1/models` until it answers.
(embed/rerank setup: `home/setup-t5810-services.sh`; Qdrant: `home/setup-qdrant.sh`.)

**2. asrock verifier (OpenRC):**
```bash
rc-service ollama status
rc-service verifier-service status
curl -s http://<asrock-lan-ip>:8007/health
```
The verifier binds its LAN address (`VERIFIER_BIND`), not `0.0.0.0` — it is reachable
from the T5810, not from the internet. (Provisioning: `home/provision-verifier-asrock.sh`.)

**3. VPS tunnel + proxy + Apache (systemd):**
```bash
systemctl status portfolio-ai-tunnel
ss -tlnp | grep -E ':(8004|8005|8006|6333|8007)'   # all five LISTEN on 127.0.0.1
curl -s http://127.0.0.1:8004/v1/models            # vLLM through the tunnel
systemctl restart api-proxy && curl -s http://127.0.0.1:8000/health
curl -s https://dev.cwetzel.com/ | head -c 200     # Apache serves the React build
```

**4. End-to-end:** send one chat at https://dev.cwetzel.com, or run the same battery the
deploy gate runs:
```bash
python3 scripts/selftest.py --url wss://dev.cwetzel.com/ws/chat
```

---

## Monitoring

Three independent layers, all paging via ntfy (config: `/etc/default/portfolio-health`,
not in the repo). **Alert-only by design** — no auto-restart of stateful services (blind
respawn hid the 2026-06-14 Qdrant outage).

- **VPS deep aggregator** — `scripts/health_aggregate.py`, every 5 min via
  `portfolio-health.timer`. Probes the whole chain visible through the tunnel (proxy
  `/health`, vLLM, Qdrant **including `points_count`**, embed, rerank, verifier) plus an
  optional end-to-end WS smoke. Pages only on state transitions; pings a healthchecks.io
  URL on every all-green run. Units + installer: `cloud/systemd/portfolio-health*`,
  `cloud/setup-health-monitor.sh`.
- **External dead-man's switch** — healthchecks.io alerts when the VPS/monitor itself
  dies (the pings stop). Daily "all green" heartbeat at 12:00 via
  `portfolio-health-heartbeat.timer`; `portfolio-health-alert.service` fires if the probe
  itself crashes. Runbook: `docs/runbooks/dead-mans-switch-monitoring.md`.
- **T5810 canary** — `scripts/selftest-canary.sh`, cron every 30 min, runs the self-test
  against the **public** endpoint from the home network, exercising the visitor path
  (DNS, SSL, Apache, tunnel) that the VPS-internal aggregator can't see.

**Metrics worth watching:** verifier latency (7B baseline: median ~8 s; 14B: expect 10–20 s),
`flagged_rate` (7-day baseline 0.25, all-time 0.22 — watch for drift past ±0.05), T5810 GPU utilization
(93% — tight by design, see Known Limits).

---

## Known Limits

- **Reranker truncates at 512 tokens** per (query, chunk) pair — an XLM-RoBERTa
  architectural cap, not a tunable. 71% of the 62 chunks are longer, so they are scored on
  their head only. It affects **ranking only** — the generator always receives full chunks.
  A/B'd against a smaller-chunk collection and kept: fixing it is net-negative end-to-end.
  Do not reopen without a metric that beats 20/20 on the golden set (see CLAUDE.md).
- **Single-user only.** One box, in-memory state, no multi-instance replication. The
  public `/ws/chat` is rate-limited to 1 concurrent connection per IP
  (`cloud/rate_limit.py`); localhost is exempt for local testing.
- **T5810 VRAM is tight by design:** `GPU_MEMORY_UTILIZATION=0.93` leaves ~760 MiB free
  per A4500 (0.95 OOMs). No headroom for a spec-decoding draft model; decoupling
  embed/rerank off the box is the planned relief.
- **The verifier is fail-open.** If asrock is down, chat is unaffected — verdicts simply
  don't appear. The reranker also fails open (to cosine order) if it is down.
- **Hybrid dense+BM25 retrieval exists but is OFF** (`HYBRID_SEARCH=0`) — it lost its A/B
  on this small KB. Turning it on requires a coordinated reindex (`HYBRID=1
  ./scripts/reindex_kb.sh`) + proxy env change.

---

## Troubleshooting

**Chat connects but times out / errors on every message**
→ vLLM. Through the tunnel from the VPS: `curl http://127.0.0.1:8004/v1/models`. If that
fails, check the tunnel (`systemctl status portfolio-ai-tunnel`), then
`rc-service pscode-vllm status` on the T5810. A model reload after a crash takes minutes.

**Answers say "I don't have that documented" for everything, or no sources appear**
→ Retrieval chain. Check Qdrant first: `curl http://127.0.0.1:6333/collections/documents`
and confirm `points_count` is non-zero (the 2026-06-14 outage was Qdrant up but serving 0
points — the health aggregator now probes exactly this). Then rerank:
`curl -X POST http://127.0.0.1:8006/rerank ...` — if it is down the proxy falls back to
cosine order, so a silent rerank outage shows as *subtly worse* answers, not errors.

**Verdicts never appear / verifier takes >10 s**
→ Check the judge is on the GPU, not CPU: `nvidia-smi` on the asrock (the Ollama model
should be listed). Ollama evicts idle models after 5 min by default — `JUDGE_KEEP_ALIVE=30m`
is set for this reason — and defaults to a 4096-token context that silently truncates the
15-chunk evidence payload, hence `JUDGE_NUM_CTX=16384` (in lockstep with
`OLLAMA_CONTEXT_LENGTH=16384` on the Ollama side). Also verify the tunnel's 8007
forward: `curl http://127.0.0.1:8007/health` from the VPS.

**Everything behind the tunnel is unreachable at once**
→ The tunnel itself. `systemctl restart portfolio-ai-tunnel`, then confirm all five ports
LISTEN on `127.0.0.1`. If it crash-loops, check `/etc/default/portfolio-ai-tunnel` — an
empty `VERIFIER_HOST` makes ssh refuse to start.

**Deploy succeeded but the site misbehaves**
→ The deploy's self-test gate should have caught this; if it was skipped (no `websockets`
locally), run it manually: `python3 scripts/selftest.py --url wss://dev.cwetzel.com/ws/chat`.
Proxy logs: `journalctl -u api-proxy -f` on the VPS. Query/response *content* is never
logged (red-lines #2) — metadata only, by design.

---

## Latency Baseline (measured, single-user)

| Stage | Median | Notes |
|-------|--------|-------|
| Query embedding (bge-base, CPU) | ~45 ms | |
| Qdrant search (top-15) | ~120 ms | |
| Rerank (15 chunks, CPU cross-encoder) | ~2,800 ms | the pipeline bottleneck |
| LLM generation, TTFT | ~3,200 ms | context-length dependent |
| **End-to-end answer** | **~9 s** | unlimited latency budget by design (single-user) |
| Verifier judge (14B, RTX 5060 Ti), out-of-band | expect ~10,000–20,000 ms (7B baseline: ~8,000 ms) | never blocks the answer |

Expected after the Tier 2/3 GPU moves (reranker onto a GPU): rerank ~50 ms, end-to-end
~6 s. There is no "50+ tokens/sec" anywhere in this system — don't write it back in.

---

## Rollback

```bash
systemctl restart api-proxy                # proxy (VPS)
systemctl restart portfolio-ai-tunnel      # tunnel (VPS)
systemctl restart apache2                  # edge (VPS)
rc-service qdrant restart                  # vector DB (T5810)
rc-service pscode-vllm restart             # vLLM (T5810) — minutes to reload weights
rc-service verifier-service restart        # judge (asrock) — chat unaffected while down
```

Index rollback is `./scripts/reindex_kb.sh` — the collection is derived data, regenerated
from the committed KB. Never hand-patch the Qdrant index.
