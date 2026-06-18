# Deployment Guide: Portfolio AI MVP

**Status:** GATE 2 Infrastructure Complete  
**Date:** 2026-06-06  
**Model:** Qwen 2.5 14B (existing pscode cache, 28GB, bfloat16)  
**Frontend:** dev.cwetzel.com (staging) → cwetzel.com (production cutover later)

---

## Architecture

```
┌────────────────────────────────────────────────────────┐
│ Browser → https://dev.cwetzel.com                      │
│ Apache (HTTPS, SSL cert via Let's Encrypt)             │
├────────────────────────────────────────────────────────┤
│ React Frontend (static files)                          │
│ /api/* → Apache ProxyPass → localhost:8000             │
│ /ws/* → Apache ProxyPass (WebSocket)                   │
└──────────────────────┬─────────────────────────────────┘
                       │
         cwetzel.com:8000 (FastAPI)
         • /health → {status, timestamp}
         • /api/chat → pscode vLLM
         • /api/search → Qdrant
         • /ws/chat → WebSocket streaming
                       │
        ┌──────────────┴──────────────┐
        │                             │
   ai.cwetzel.com:8004          ai.cwetzel.com:6333
   (via /etc/hosts)             (via /etc/hosts)
   └─→ localhost:8004           └─→ localhost:6333
       (SSH tunnel)                 (SSH tunnel)
        │                             │
        └──────────────┬──────────────┘
                       │ SSH Tunnel (encrypted)
                       │ cwetzel.com:localhost → T5810
                       │ • 8001 → 8001 (unused, reserved)
                       │ • 8004 → 8004 (pscode vLLM)
                       │ • 8005 → 8005 (embedding service)
                       │ • 8006 → 8006 (reranker service)
                       │ • 6333 → 6333 (Qdrant)
                       │
┌──────────────────────┴──────────────────────────────────┐
│ T5810 Home Server (Gentoo)                             │
├──────────────────────────────────────────────────────────┤
│ pscode (existing)                                       │
│ └─ vLLM:8004 (Qwen 2.5 14B, BF16, 16K context)         │
│    GPU: 18GB per card (proven working)                  │
│                                                         │
│ Portfolio AI                                            │
│ ├─ Qdrant:6333 (Vector DB, indexed)                    │
│ ├─ embed-service:8005 (all-MiniLM-L6-v2, CPU)          │
│ └─ rerank-service:8006 (bge-reranker-base, CPU)        │
└─────────────────────────────────────────────────────────┘
```

---

## ✅ Step 1: SSH Tunnel (cwetzel.com → T5810)

**Status:** ✅ Active  
**Service:** `/etc/systemd/system/portfolio-ai-tunnel.service`

**Ports forwarded:**
- `localhost:8001` → T5810:8001 (reserved, unused)
- `localhost:8004` → T5810:8004 (pscode vLLM, active)
- `localhost:8005` → T5810:8005 (embedding service, active)
- `localhost:8006` → T5810:8006 (reranker service, active)
- `localhost:6333` → T5810:6333 (Qdrant, active)

**Verify:**
```bash
ssh root@cwetzel.com "systemctl status portfolio-ai-tunnel && ss -tlnp | grep -E ':(8001|8004|6333)'"
```

---

## ✅ Step 2: vLLM (Using Existing pscode Instance)

**Status:** ✅ Active (no new setup needed)

pscode's vLLM:8004 is already running with Qwen 2.5 14B cached and proven working. Using the existing instance eliminates:
- Redundant model download (saves ~15 min)
- GPU memory conflict (pscode: 18GB + new would exceed 40GB)
- Infrastructure duplication

**vLLM Details:**
- Model: Qwen 2.5 14B (cached since May 21, running)
- Memory: 18GB per GPU (95% of 20GB each)
- Port: T5810:8004 (tunneled to cwetzel.com:8004)
- Hostname: ai.cwetzel.com:8004 (resolved via /etc/hosts)

**Verify:**
```bash
ssh root@cwetzel.com "curl -s http://ai.cwetzel.com:8004/v1/models | head -c 100"
```

---

## ⏳ Step 3: Qdrant (Vector Database)

**On T5810, install & start Qdrant:**

```bash
ssh root@t5810.local 'bash -c "
  apt-get update && apt-get install -y qdrant
  systemctl enable qdrant && systemctl restart qdrant
  sleep 3
  curl http://localhost:6333/health
"'
```

**Verify from cwetzel.com:**
```bash
curl http://ai.cwetzel.com:6333/health
```

---

## ✅ Step 4: cwetzel.com Proxy Setup

**Status:** ✅ Complete

**What was set up:**
1. `/var/www/dev.cwetzel.com` (frontend directory)
2. FastAPI proxy on localhost:8000
3. Apache vhost for dev.cwetzel.com (HTTPS)
4. SSL cert issued via Let's Encrypt
5. Apache ProxyPass for /api/* and /ws/*
6. ai.cwetzel.com added to /etc/hosts

**Services running:**
- FastAPI: ✅ localhost:8000
- Apache: ✅ dev.cwetzel.com (HTTPS)
- SSH Tunnel: ✅ to T5810

**Verify:**
```bash
ssh root@cwetzel.com "curl -s http://127.0.0.1:8000/health"
ssh root@cwetzel.com "systemctl status apache2 api-proxy portfolio-ai-tunnel"
```

**Logs:**
```bash
ssh root@cwetzel.com "journalctl -u api-proxy -f"
ssh root@cwetzel.com "tail -f /var/log/apache2/access.log"
```

---

## ⏳ Step 5: React Frontend (Days 4-7)

**Local development:**

```bash
cd frontend/
npm install
npm run dev
```

Opens http://localhost:5173 with proxy to localhost:8000

**Build and deploy to production:**

```bash
cd frontend/
npm run build
scp -r dist/* root@cwetzel.com:/var/www/dev.cwetzel.com/
```

**Test:**
```bash
curl https://dev.cwetzel.com/
```

**Frontend architecture:**
- Landing page: Intro + "Start Chat" button
- Chat interface: WebSocket streaming (real-time tokens)
- Message display: User/Assistant roles, auto-scroll
- Error handling: Graceful fallback on connection errors

---

## ⏳ Step 6: Qdrant Setup & Knowledge Base Indexing (Days 8-9)

**Install Qdrant on T5810:**
```bash
ssh root@t5810.local "apt-get install -y qdrant && systemctl enable qdrant && systemctl restart qdrant"
```

**Index documents:**
```bash
python scripts/index_knowledge_base.py \
  --qdrant-url http://ai.cwetzel.com:6333 \
  --kb-path knowledge_base/
```

**Knowledge base content:**
- 28 LinkedIn posts (114.6k impressions, ranked by engagement)
- 5 case studies (SOC2, AVD, SAP, DR, VMware)
- Resume (26-year IT career)

---

## ⏳ Step 7: Integration Testing (Days 10-15)

**Full stack test:**

1. **Check vLLM responds:**
   ```bash
   curl https://dev.cwetzel.com/api/chat \
     -H "Content-Type: application/json" \
     -d '{"messages": [{"role": "user", "content": "Hello, what is your name?"}], "model": "Qwen2.5-14B"}'
   ```

2. **WebSocket streaming:**
   ```bash
   wscat -c wss://dev.cwetzel.com/ws/chat
   # Send: {"type": "chat", "payload": {"messages": [{"role": "user", "content": "Hi"}], "model": "Qwen2.5-14B"}}
   ```

3. **Knowledge base search:**
   ```bash
   curl https://dev.cwetzel.com/api/search \
     -H "Content-Type: application/json" \
     -d '{"collection": "documents", "query": [0.1, 0.2, ...], "limit": 5}'
   ```

4. **Performance targets:**
   - vLLM latency (p50): <100ms
   - Qdrant search: <200ms
   - Proxy overhead: <50ms
   - Throughput: >50 tokens/sec

---

## Performance Targets (MVP)

| Metric | Target | Status |
|--------|--------|--------|
| vLLM latency (p50) | <100ms | pscode proven <100ms |
| Qdrant search latency | <200ms | Not yet tested |
| Proxy overhead | <50ms | Measured <50ms |
| Throughput | >50 tok/sec | pscode proven >50 |
| Uptime | 99%+ | pscode: 16 days uptime |

---

## DNS & Network Status

| Component | Status | Notes |
|-----------|--------|-------|
| dev.cwetzel.com | ✅ Active | A record, HTTPS ready |
| cwetzel.com | ✅ Active | Cloud instance, SSH tunnel |
| ai.cwetzel.com | ✅ Configured | /etc/hosts on both systems |
| SSH Tunnel | ✅ Running | Ports 8001, 8004, 6333 |
| FastAPI Proxy | ✅ Running | localhost:8000 |
| Apache vhost | ✅ Active | dev.cwetzel.com HTTPS |

---

## Future: Cutover to cwetzel.com (Later)

When ready for production:
1. Copy React to `/var/www/cwetzel.com/`
2. Create Apache vhost for cwetzel.com
3. Reissue SSL cert for cwetzel.com
4. Update DNS to point to production
5. Keep dev.cwetzel.com for staging/testing

---

## Rollback Procedures

**FastAPI proxy restart:**
```bash
ssh root@cwetzel.com "systemctl restart api-proxy"
```

**Qdrant restart:**
```bash
ssh root@t5810.local "systemctl restart qdrant"
```

**SSH tunnel restart:**
```bash
ssh root@cwetzel.com "systemctl restart portfolio-ai-tunnel"
```

**Apache restart:**
```bash
ssh root@cwetzel.com "systemctl restart apache2"
```

---

## GATE 2 Progress

- Days 1-3: ✅ Infrastructure complete
  - ✅ SSH tunnel (T5810 ↔ cwetzel.com)
  - ✅ FastAPI proxy (cwetzel.com:8000)
  - ✅ Apache vhost (dev.cwetzel.com HTTPS)
  - ✅ vLLM (pscode:8004, existing)
  
- Days 4-7: ⏳ React frontend + UI
  
- Days 8-9: ⏳ Qdrant + knowledge base indexing
  
- Days 10-15: ⏳ Integration & performance testing
  
- Days 16-20: ⏳ E2E testing + soft launch prep
  
- Days 21-30: ⏳ Soft launch (24h monitoring)
