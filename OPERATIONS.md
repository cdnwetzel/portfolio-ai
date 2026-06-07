# Portfolio AI - Operations & Monitoring

**Status:** MVP Infrastructure Complete (GATE 2.5)  
**Endpoint:** https://dev.cwetzel.com  
**Stack:** React (frontend) → Apache (proxy) → FastAPI (backend) → pscode vLLM (inference)

---

## System Status

### Services (cwetzel.com)

| Service | Port | Status | Auto-start | Restart |
|---------|------|--------|-----------|---------|
| api-proxy | 8000 | ✅ Running | ✅ Enabled | Always |
| apache2 | 80/443 | ✅ Running | ✅ Enabled | On-failure |
| portfolio-ai-tunnel | 8001/8004/6333 | ✅ Running | ✅ Enabled | Always |

### Services (T5810)

| Service | Port | Status | Usage |
|---------|------|--------|-------|
| pscode vLLM | 8004 | ✅ Running (16 days) | 18GB/GPU (95%) |
| Qdrant | 6333 | ⏳ To be set up | Vector DB |

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

- [ ] Set up monitoring/alerting
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

## Contact

For infrastructure issues, check logs above. For model issues (vLLM), contact whoever manages pscode (T5810).

**Last Updated:** 2026-06-06
