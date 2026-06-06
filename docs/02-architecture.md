# Architecture Document (Day 30 MVP)

**Project:** Portfolio AI SaaS  
**Scope:** Website + AI Chat Demo (No SaaS features)  
**Date:** 2026-06-06  
**Version:** GATE 1 Design

---

## System Overview

**Architecture Philosophy:** Minimal display layer (cwetzel.com) + powerhouse compute core (T5810)

```
┌─────────────────────────────────────────────────────┐
│         User Browser                                │
└──────────────────────────┬──────────────────────────┘
                          │ HTTPS
                          ↓
     ┌──────────────────────────────────────────┐
     │  DISPLAY LAYER: cwetzel.com              │
     │  (1 core, 1GB RAM, 25GB SSD)             │
     │                                           │
     │  ┌──────────────────────────────────────┤
     │  │ Nginx (port 80/443)                  │
     │  │ - Reverse proxy                      │
     │  │ - SSL termination                    │
     │  │ - Static file serving                │
     │  └────────────┬─────────────────────────┤
     │               │                          │
     │  ┌────────────↓──────────────────────────┤
     │  │ FastAPI (port 8000)                  │
     │  │ - Landing page (GET /)               │
     │  │ - Chat UI (GET /chat)                │
     │  │ - WebSocket proxy (WS /ws/chat)      │
     │  │ - Health check (GET /health)         │
     │  │ - JUST a bridge to T5810             │
     │  └────────────┬─────────────────────────┤
     │               │                          │
     └───────────────┼──────────────────────────┘
                     │ WireGuard Tunnel
                     │ 10.0.0.2 → 10.0.0.1
                     │ Encrypted, <50ms latency
                     ↓
     ┌──────────────────────────────────────────┐
     │  COMPUTE CORE: T5810 / 98.110.86.95      │
     │  (2x Xeon, 2x A4500, 64GB+ RAM)          │
     │  ← WHERE ALL THE POWER IS ←              │
     │                                           │
     │  ┌──────────────────────────────────────┤
     │  │ vLLM (port 8001)                     │
     │  │ - Model: Llama 2 70B (bfloat16)      │
     │  │ - Tensor Parallel: 2 GPUs (NVLink)   │
     │  │ - Throughput: 50+ tok/sec            │
     │  │ - Inference work → GPU does it       │
     │  └─────────────────────────────────────┤
     │                                          │
     │  ┌──────────────────────────────────────┤
     │  │ Qdrant (port 6333)                   │
     │  │ - Vector search for Chris's KB       │
     │  │ - ~200 documents (resume, cases)     │
     │  │ - Embedding: BAAI/bge-small          │
     │  │ - Top-5 retrieval per query          │
     │  └──────────────────────────────────────┤
     │                                          │
     │  ┌──────────────────────────────────────┤
     │  │ Knowledge Base (on disk)             │
     │  │ - Resume, case studies, experience   │
     │  │ - Indexed at startup                 │
     │  └──────────────────────────────────────┤
     └──────────────────────────────────────────┘
```

**Resource allocation:**
- **cwetzel.com:** HTML serving, request routing, WebSocket proxying (lightweight)
- **T5810:** All inference, vector search, knowledge base (GPU-accelerated)

---

## Technology Stack

| Layer | Technology | Purpose | Decision |
|-------|-----------|---------|----------|
| **Frontend** | React 18 + TypeScript | Chat UI, responsive design | Simple, no complex state |
| **Server** | FastAPI + Uvicorn | Async HTTP server, WebSocket | Python, good async support |
| **Streaming** | WebSocket or SSE | Real-time token streaming | WebSocket chosen (bidirectional) |
| **Reverse Proxy** | Nginx | SSL termination, static files | Standard, battle-tested |
| **Inference** | vLLM | LLM serving, batching, streaming | Fast, production-ready, supports tensor parallel |
| **Model** | Llama 2 70B (bfloat16) | LLM inference | Open license, 70B quality, fits on 2x A4500 |
| **Vector DB** | Qdrant (in-memory) | Semantic search for RAG | Simple, fast, no external deps |
| **Embedding** | BAAI/bge-small-en-v1.5 | Doc→vector conversion | Lightweight, good quality |
| **Session Storage** | Browser localStorage | Chat history per session | Cleared on refresh (minimal MVP) |
| **Networking** | WireGuard | Encrypted tunnel (cwetzel.com↔T5810) | Lightweight, high-performance VPN |
| **Container** | Docker | Reproducible deployment | Standard for cloud deployment |
| **Orchestration** | Docker Compose | Local dev + cloud | Simple, sufficient for MVP |

---

## API Design

### Endpoints (Day 30 MVP)

#### 1. **GET /**
Landing page with intro and link to chat.
```
Request:  GET / HTTP/1.1
Response: 200 OK
  Content-Type: text/html
  Body: HTML landing page
```

#### 2. **GET /chat**
Chat UI (React app).
```
Request:  GET /chat HTTP/1.1
Response: 200 OK
  Content-Type: text/html
  Body: React chat interface
```

#### 3. **WebSocket /ws/chat**
Streaming chat endpoint.
```
Connect: WS ws://cwetzel.com/ws/chat

Message (user→server):
  {
    "query": "Tell me about your Azure experience",
    "session_id": "abc123" (optional, for history)
  }

Response (server→user, streaming):
  {"token": "Chris"}
  {"token": " has"}
  {"token": " 9+"}
  {"token": " years"}
  ...
  {"token": "<END>", "total_tokens": 42}
```

#### 4. **GET /health**
Health check for monitoring.
```
Request:  GET /health HTTP/1.1
Response: 200 OK
  Content-Type: application/json
  Body: {
    "status": "ok",
    "uptime_seconds": 3600,
    "gpu_utilization": 45.2,
    "inference_queue_length": 2,
    "last_error": null
  }
```

---

## Data Flow (User Query → Response)

### Happy Path

```
1. User enters query in browser
   "What's your experience with SOC2?"

2. Browser sends via WebSocket
   POST /ws/chat
   {"query": "What's your experience with SOC2?"}

3. FastAPI handler receives query
   - Validate input (length, format)
   - Log query (optional, for monitoring)

4. RAG Pipeline
   a) Convert query to embedding (BAAI/bge-small)
   b) Search Qdrant for top-5 similar documents
      - Context: Resume (SOC2 experience)
      - Context: Case study (SOC2 audit process)
      - Context: Experience (compliance background)
   c) Build context prompt with retrieved docs

5. LLM Inference (vLLM)
   System: "You are Chris Wetzel, an IT Manager..."
   Context: [retrieved documents above]
   User Query: "What's your experience with SOC2?"
   
6. Stream response tokens back to browser
   {"token": "I"}
   {"token": "'ve"}
   {"token": " conducted"}
   ...
   {"token": "<END>"}

7. Browser displays response in real-time
   "I've conducted SOC2 Type II audits and..."
```

### Error Path

```
If query fails:
- Inference timeout (>30s) → Return error message
- vLLM unavailable → Return error message
- Qdrant unavailable → Return error message
- Invalid input → Return 400 Bad Request

All errors logged with timestamp + details for troubleshooting.
```

---

## RAG (Retrieval-Augmented Generation)

### Day 30 Knowledge Base

**Content sources:**

1. **Resume** (1 document, ~5KB)
   - All jobs, dates, responsibilities, skills
   - Metrics: 75% DB performance improvement, 200-user AVD scaling

2. **cwetzel.com pages** (5 documents)
   - About: 26 years enterprise IT background
   - Experience: Detailed job descriptions
   - Projects: Major implementations (SOC2, AVD, SAP, DR, VMware)
   - Education: College, certifications
   - Skills: Tools, platforms, methodologies

3. **LinkedIn profile** (1 document)
   - Summary and endorsements
   - Recommendations from colleagues
   - Current role at law firm

4. **Case studies** (5 detailed documents)
   - SOC2 Type II Compliance: Audit process, gaps, remediation steps
   - Azure VDI Migration: 120→200 users, regional distribution, backup strategy
   - SAP Business One: MSSQL backend, WMS integration, global rollout
   - Disaster Recovery: BDR approach, off-site backups, failover testing
   - VMware: P2V migration strategy, infrastructure design

**Total:** ~12 documents, ~200KB of text

### Embedding & Retrieval

```
1. During startup:
   a) Load all documents from files (src/data/knowledge_base/)
   b) Split into chunks: 512 tokens, 256 token overlap
   c) Convert chunks to embeddings (BAAI/bge-small)
   d) Index in Qdrant (in-memory)

2. At query time:
   a) Convert query to embedding
   b) Search Qdrant for top-5 most similar chunks
   c) Build prompt with top-5 chunks as context

3. LLM sees:
   System prompt (fixed)
   + Top-5 retrieved documents
   + User query
   = Full prompt
```

### Quality Metrics

- **Retrieval Relevance:** Top-5 results include answer 90%+ of time
- **Hallucination Rate:** AI makes up facts <1% of time
- **Response Accuracy:** >90% of responses are accurate/relevant

### Day 60+ Enhancements (Out of Scope)

- [ ] Dynamic document loading (users upload own content)
- [ ] Document chunking optimization (adaptive chunk size)
- [ ] Re-ranking (BM25 second-stage ranking)
- [ ] Semantic caching (cache embeddings, skip re-computation)
- [ ] Feedback loops (user can correct AI, improve retrieval)

---

## Inference Pipeline (vLLM)

### Model Configuration

```
Model: meta-llama/Llama-2-70b-chat-hf
Quantization: bfloat16 (no quality loss, fits on 2x A4500s)
Max tokens: 2048 (request context window)
Response max: 2000 tokens (user sees up to 1500 words)
Temperature: 0.7 (balanced creativity/consistency)
Top-p: 0.9 (nucleus sampling)
```

### Tensor Parallelism (2 GPUs)

```
GPU 0: Model layers 0-39
GPU 1: Model layers 40-79
Communication: NVLink (~900 GB/s)

Benefits:
- Fit 70B model on 2x 40GB GPUs
- Throughput: 50+ tokens/sec
- Latency: p50 <100ms, p90 <500ms
```

### Batching & Queuing

```
Request arrives:
  1. Add to queue (max 10 pending)
  2. When batch reaches 4–8 requests OR 100ms elapsed
  3. Run inference
  4. Stream tokens back to all clients

Prevents single slow request blocking others.
```

### Streaming

```
vLLM outputs tokens one at a time.
FastAPI WebSocket sends each token immediately.
Browser receives & displays in real-time.

User sees: "I've..." (pause) "...conducted..." (pause) "...SOC2..."
Latency feels fast even if total time is 5 seconds.
```

---

## Deployment Topology

### cwetzel.com (Minimal Display Server)

```
┌──────────────────────────────────────┐
│ Ubuntu 22.04 LTS (minimal specs)     │
│ 1 core, 1GB RAM, 25GB SSD            │
├──────────────────────────────────────┤
│ Nginx (port 80, 443)                 │
│  - HTTPS termination (Certbot SSL)   │
│  - Static file serving (landing page)│
│  - Reverse proxy to FastAPI:8000     │
├──────────────────────────────────────┤
│ FastAPI (port 8000, async)           │
│  - Landing page endpoint             │
│  - Chat UI endpoint                  │
│  - WebSocket proxy (WS /ws/chat)     │
│  - Health check endpoint             │
│  - Lightweight request forwarding    │
├──────────────────────────────────────┤
│ WireGuard (port 51820 inbound)       │
│  - Encrypted tunnel to T5810         │
│  - Persistent connection             │
│  - <50ms latency to home server      │
└──────────────────────────────────────┘
```

### T5810 (Powerhouse Compute)

```
┌──────────────────────────────────────┐
│ Gentoo Linux (precision-t5810)       │
│ 2x Xeon, 2x NVIDIA A4500, 64GB+ RAM  │
├──────────────────────────────────────┤
│ vLLM (port 8001)                     │
│  - Model: Llama 2 70B (bfloat16)     │
│  - 2x A4500 (tensor parallel)        │
│  - GPU throughput: 50+ tok/sec       │
│  - Accessible via WireGuard tunnel   │
├──────────────────────────────────────┤
│ Qdrant (port 6333)                   │
│  - Vector DB (in-memory)             │
│  - Chris's knowledge base (~200 docs)│
│  - Fast semantic search              │
│  - Accessible via WireGuard tunnel   │
├──────────────────────────────────────┤
│ Knowledge Base (disk storage)        │
│  - Resume, case studies, experience │
│  - Loaded & indexed at startup       │
│  - Served by Qdrant                  │
└──────────────────────────────────────┘
```

### WireGuard Tunnel

```
Cloud IP:           10.0.0.2/24
Home IP:            10.0.0.1/24
UDP Port:           51820
Key exchange:       Pre-shared keys (generated)
Throughput:         300 Mbps available
Latency:            <50ms (home network)
Stability:          Monitored (alert if down)

Benefits:
- Encrypted (no MITM attacks)
- Lightweight (low overhead)
- No dynamic DNS needed
- Simple key rotation
```

---

## Data Storage (Day 30 MVP)

**No server-side database needed for MVP.**

**Chat history:** Stored in browser (localStorage)
- Chat clears on page refresh
- No server persistence
- Minimal infrastructure required
- Perfect for demo/showcase

**Knowledge base:** Pre-indexed at T5810 startup
- Loaded from disk files
- Indexed into Qdrant
- Served by Qdrant (no database needed)

**Day 60+ Addition:** PostgreSQL for persistence
- Chat history storage
- User authentication
- API key management
- Usage tracking
- Billing records
- Multi-tenant row-level security

---

## Security (Day 30)

### HTTPS/TLS
- ✅ Certbot SSL cert (auto-renew)
- ✅ Force HTTPS (redirect HTTP→HTTPS)
- ✅ Modern TLS 1.3

### Rate Limiting
- ✅ 100 requests/min per IP (Redis-backed)
- ✅ Simple IP-based (no user accounts day 30)
- ✅ Return 429 Too Many Requests if exceeded

### Input Validation
- ✅ Query length: max 1000 characters
- ✅ Reject null/empty queries
- ✅ Reject special characters that could break prompts
- ✅ Validate request format (JSON, expected fields)

### No Sensitive Data
- 🚫 No user accounts (day 30)
- 🚫 No private data storage
- 🚫 No authentication tokens
- ✅ Chat history clears on browser refresh (or cleared daily server-side)

### Monitoring
- ✅ /health endpoint (uptime, errors, GPU util)
- ✅ Error logs (query failures, inference timeouts)
- ✅ No sensitive data in logs

### Day 60+ Security Additions
- [ ] User authentication (JWT tokens)
- [ ] API key management
- [ ] Row-level security (multi-tenant isolation)
- [ ] Audit logging (who queried what, when)
- [ ] Data encryption at rest (PostgreSQL pgcrypto)

---

## Performance Targets

### Latency (User Experience)
```
First token: p50 <100ms, p90 <500ms
- User sees response starting within 100-500ms
- Feels instant/responsive

Full response (2000 tokens at 50 tok/sec):
- Streaming allows response to be viewed as it arrives
- Total time: 40 seconds worst-case
- But user sees partial response in <1s
```

### Throughput
```
Single A4500: ~40 tok/sec
Dual A4500 (tensor parallel): ~50 tok/sec
Batching (4-8 requests): Amortized cost
- Multiple users experience near-linear throughput (no batching overhead)
```

### Resource Usage
```
GPU Memory: 38GB / 40GB available
  - Llama 70B bfloat16: ~140GB (2 cards = 80GB total)
  - vLLM overhead: 2GB per card
  - Total: 38–40GB ✓

CPU (on cloud VPS): <20% during inference
RAM (on cloud VPS): <2GB

Qdrant (in-memory): ~500MB for 12 docs + embeddings
Redis: <1GB for rate limit counters + session cache
```

---

## Deployment & Operations

### Docker Compose (Local Dev + Cloud)

```yaml
version: "3.9"
services:
  nginx:
    image: nginx:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./cloud/nginx.conf:/etc/nginx/nginx.conf
      - ./certs:/etc/nginx/certs
    depends_on:
      - api

  api:
    build: .
    environment:
      - VLLM_HOST=10.0.0.1  # WireGuard IP of home server
      - VLLM_PORT=8001
      - QDRANT_HOST=10.0.0.1
      - QDRANT_PORT=6333
      - REDIS_URL=redis://redis:6379
      - LOG_LEVEL=INFO
    ports:
      - "8000:8000"
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

### Health Checks

```
Nginx: curl http://localhost/health
FastAPI: GET /health
vLLM: Connect via WireGuard, check /health
Qdrant: Connect via WireGuard, check /health
```

### Monitoring

```
/health endpoint returns:
  {
    "status": "ok",
    "uptime_seconds": 86400,
    "gpu_utilization": 45.2,
    "gpu_temperature": 62.0,
    "inference_queue_length": 2,
    "last_inference_latency_ms": 245,
    "qdrant_available": true,
    "redis_available": true,
    "errors_last_hour": 0
  }

Check every 5 minutes. Alert if:
  - status != "ok"
  - uptime < last check (crash/restart)
  - gpu_temperature > 80°C
  - inference_queue_length > 10
```

### Troubleshooting

**Inference slow (>500ms p90)?**
- Check GPU utilization: if >90%, queue is building
- Reduce batch size (more frequent, smaller batches)
- Reduce context window (fewer tokens per request)

**vLLM offline?**
- Check WireGuard tunnel: `wg show`
- Check vLLM logs: `docker logs vllm`
- Restart: `docker restart vllm`

**Qdrant returning no results?**
- Verify knowledge base loaded on startup
- Check Qdrant logs: `docker logs qdrant`
- Verify embeddings generated correctly

**High latency from cloud?**
- Check WireGuard latency: `ping 10.0.0.1`
- Check cloud VPS network: `mtr 10.0.0.1`
- Check home internet (300 Mbps available?)

---

## Future Enhancements (Day 60-90+)

### Database Schema
- [ ] Multi-tenant support (tenants table, RLS)
- [ ] User management (signup, login, API keys)
- [ ] Usage tracking (tokens, requests, cost per tenant)
- [ ] Billing (Stripe integration, invoices)

### Features
- [ ] Multiple knowledge bases (per tenant)
- [ ] Document upload/management
- [ ] Chat history persistence
- [ ] Feedback loops (user corrections)
- [ ] Admin dashboard

### Infrastructure
- [ ] Load balancer (multiple FastAPI instances)
- [ ] Caching layer (semantic cache, embedding cache)
- [ ] CDN (static assets, faster global delivery)
- [ ] Backup system (daily PostgreSQL backups)

### Observability
- [ ] Prometheus metrics (detailed)
- [ ] Grafana dashboard (visualize metrics)
- [ ] Structured logging (ELK stack or similar)
- [ ] Tracing (request spans across services)

---

## Decision Log

### Why Llama 70B (not Mistral, Qwen, etc.)?
- **Open license:** Can run locally without restrictions
- **Quality:** Comparable to GPT-3.5 on many benchmarks
- **Size:** 70B is sweet spot (not too large, good quality)
- **Community:** Largest open model community, lots of resources

### Why vLLM (not TensorRT, ONNX, etc.)?
- **Streaming:** Native support for token streaming
- **Batching:** Excellent batching throughput
- **Tensor Parallel:** Easy 2-GPU setup with NVLink
- **Simplicity:** One command line to start

### Why Qdrant (not Pinecone, Weaviate, etc.)?
- **Local:** No external service needed (privacy)
- **Fast:** In-memory vector DB, sub-millisecond search
- **Simple:** Minimal setup, good Python API
- **Self-hosted:** No vendor lock-in, no API key exposed

### Why WebSocket (not SSE, Polling)?
- **Bidirectional:** User can send new query while streaming
- **Lower latency:** No polling overhead
- **Standard:** Well-supported in browsers and frameworks
- **Streaming:** Native support for token streaming

---

**Status:** GATE 1 Design Complete  
**Next:** GATE 2 Implementation  
**Last Updated:** 2026-06-06
