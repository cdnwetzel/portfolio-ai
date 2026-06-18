# Portfolio AI — dev.cwetzel.com

A full-stack AI chat built on personal GPU hardware. Not a wrapper around OpenAI — Qwen 14B runs on two RTX A4500 GPUs in my home office via vLLM tensor parallelism. Every answer is grounded in a RAG knowledge base of documented work: case studies, infrastructure write-ups, LinkedIn posts, resume.

**Live:** https://dev.cwetzel.com

---

## Architecture

```
Browser
  ↓ HTTPS / WSS
cwetzel.com (Ubuntu VPS)
  ├─ Nginx  — SSL termination, static React build
  └─ FastAPI api-proxy (port 8000)
       ├─ RAG: embed query → Qdrant search (top-15) → rerank (top-5) → inject context
       └─ Stream: vLLM WebSocket → browser
            ↓ SSH reverse tunnel
T5810 Home Server (Gentoo Linux)
  ├─ vLLM  — Qwen2.5-Coder 14B, tensor parallel, port 8004
  ├─ Qdrant — vector DB, 384-dim cosine similarity, port 6333
  ├─ all-MiniLM-L6-v2 — CPU embeddings, port 8005
  └─ bge-reranker-base — CPU cross-encoder reranker, port 8006
```

**Key properties:**
- RAG-grounded responses — model cites sources, says "I don't have that documented" when KB doesn't cover a topic
- Streaming via WebSocket — tokens appear as generated, no polling
- Follow-up suggestion chips — model appends a `FOLLOWUPS:[...]` block; frontend parses and strips it, shows as clickable chips
- Context management — 4K char per-prompt cap, 24K char sliding window history
- Zero cloud GPU cost — owned A4500 NVLink pair handles inference

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite + Tailwind CSS |
| Edge proxy | FastAPI + Uvicorn (Python) |
| LLM serving | vLLM 0.14.0 |
| Model | Qwen2.5-Coder 14B Instruct |
| Vector DB | Qdrant |
| Embeddings | sentence-transformers / all-MiniLM-L6-v2 |
| Inference hardware | Dell Precision T5810, 2× NVIDIA RTX A4500 (NVLink) |
| OS | Gentoo Linux (custom kernel, OpenRC) |
| Networking | SSH reverse tunnel (home → VPS) |

---

## Project Layout

```
cloud/          FastAPI proxy (api-proxy.py) — deployed to VPS
frontend/       React + Vite app — built and rsync'd to /var/www/dev.cwetzel.com/
scripts/        KB indexer (index_with_embeddings.py), one-off tools
knowledge_base/
  RESUME.md
  case_studies/   9 project write-ups (AVD, SAP, SOC2, DR, VMware, AI iterations, ...)
  posts/          Top LinkedIn posts (by impressions)
  infrastructure/ T5810 homelab, this AI system
plans/          Design documents and implementation plans
```

---

## Running Locally

You need vLLM, Qdrant, an embedding service, and a reranker running. The proxy expects them on localhost ports 8004, 6333, 8005, and 8006 respectively (same as the SSH tunnel forwards in production). The reranker is optional — the proxy fails open to cosine top-5 if port 8006 is unreachable.

```bash
# Frontend dev server
cd frontend
npm install
npm run dev   # http://localhost:5173 — proxies /ws and /api to localhost:8000

# API proxy
pip install fastapi uvicorn httpx
uvicorn cloud.api-proxy:app --host 127.0.0.1 --port 8000

# Index KB into Qdrant (run on whatever machine hosts Qdrant)
python scripts/index_with_embeddings.py
```

---

## Deployment

```bash
# Build and deploy frontend
cd frontend && npm run build
rsync -avz --delete dist/ root@cwetzel.com:/var/www/dev.cwetzel.com/

# Deploy proxy
scp cloud/api-proxy.py root@cwetzel.com:/opt/api-proxy/main.py
ssh root@cwetzel.com "systemctl restart api-proxy"
```

---

## About

Built by Chris Wetzel — infrastructure engineer, 26 years enterprise IT, currently IT Manager at a law firm in NJ. The T5810 running inference in my home office is the same machine I use for Gentoo kernel experiments and the same one I write about on LinkedIn.

- **Website:** https://cwetzel.com
- **LinkedIn:** https://linkedin.com/in/chris-wetzel
- **Email:** chris@cwetzel.com
