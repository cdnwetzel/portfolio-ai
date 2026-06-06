# Deployment Checklist

**Date:** 2026-06-06

## Infrastructure Setup (GATE 2 Prep)

### ✅ SSH Tunnel Service (cwetzel.com)

Created persistent SSH tunnel from cwetzel.com to T5810:
- **Service:** `/etc/systemd/system/portfolio-ai-tunnel.service`
- **Status:** Active and running
- **Tunnels:**
  - `127.0.0.1:8001` → `98.110.86.95:8001` (vLLM)
  - `127.0.0.1:6333` → `98.110.86.95:6333` (Qdrant)
- **Auto-restart:** Yes (systemd)
- **Logs:** `journalctl -u portfolio-ai-tunnel.service`

### Testing Tunnel Status

```bash
# From cwetzel.com:
systemctl status portfolio-ai-tunnel
ss -tlnp | grep -E '8001|6333'

# View logs:
journalctl -u portfolio-ai-tunnel.service -n 20 --no-pager
```

## GATE 2 Setup (To Be Done)

On **T5810** (98.110.86.95):

- [ ] vLLM:8001 (Llama 70B inference)
  - Separate from pscode's 8004
  - Tensor parallel on 2x A4500s
  - GPU memory allocation TBD (pscode uses 95%)

- [ ] Qdrant:6333 (vector database)
  - Load Chris's knowledge base
  - Pre-index ~200 documents

On **cwetzel.com**:

- [ ] FastAPI app
  - Landing page endpoint (GET /)
  - Chat UI endpoint (GET /chat)
  - WebSocket proxy (WS /ws/chat)
  - Forward to T5810 via tunnel

- [ ] React frontend
  - Landing page
  - Chat interface
  - Browser localStorage for session

- [ ] Docker build & test

## GATE 3-5 (Later)

- [ ] Performance testing
- [ ] Manual QA
- [ ] Soft launch (24h monitoring)
- [ ] Go/No-Go decision

---

**Next Steps:** GATE 2 development
