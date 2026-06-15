# AI Portfolio Chat System — Architecture & Design

## What This Is

The AI chat at dev.cwetzel.com is a full-stack AI inference system built on personal hardware. It's not a wrapper around OpenAI or a cloud GPU service — it runs on a Dell Precision T5810 in my home office on two RTX A4500 GPUs with a custom vLLM deployment.

The system demonstrates that high-quality AI inference can run on owned infrastructure at low cost, and that portfolio showcasing can be done with real engineering rather than polished demos.

**The code is open source:** https://github.com/cdnwetzel/portfolio-saas

If you're talking to this AI right now, you're using this system. The repo contains everything: the FastAPI proxy, the React frontend, the RAG pipeline, the Qdrant indexing scripts, and the vLLM service configuration.

---

## Full Stack

| Layer | Technology | Where It Runs |
|---|---|---|
| Frontend | React + Vite + Tailwind CSS | Browser |
| Edge | Nginx + FastAPI (api-proxy.py) | cwetzel.com VPS |
| LLM | vLLM + Qwen2.5-Coder 14B Instruct | T5810 home server |
| Vector DB | Qdrant | T5810 home server |
| Embeddings | all-MiniLM-L6-v2 | T5810 home server (CPU) |
| Tunnel | SSH reverse forward | VPS ↔ T5810 |

---

## RAG Pipeline

Every chat message goes through a Retrieval-Augmented Generation pipeline:

1. **Embed query:** The user's message is embedded using `all-MiniLM-L6-v2` (384 dims, CPU)
2. **Vector search:** Qdrant searches the `documents` collection using cosine similarity, returns top-3 matching knowledge base chunks
3. **Inject context:** The retrieved docs are injected into the LLM system prompt
4. **Stream response:** vLLM streams the response token-by-token over WebSocket to the browser
5. **Extract follow-ups:** The model appends `FOLLOWUPS:[...]` at the end; the frontend parses and strips it, showing suggestion chips

This means the LLM is grounded in actual documented facts (my real projects, case studies, posts) rather than hallucinating biographical details.

---

## Knowledge Base

The knowledge base (indexed into Qdrant) includes:
- LinkedIn posts (top 10 by impressions, ~114K total impressions in 6 months)
- Case studies: SAP B1 global deployment, AVD 200-user migration, SOC2 Type II, disaster recovery
- Resume and professional context
- Infrastructure write-ups: T5810 homelab, this AI system
- Project docs: psaios (Python AI project)

Documents are chunked at 400 words with 50-word overlap, embedded, and stored as vectors.

---

## Why Qwen2.5-Coder 14B?

The model was chosen for:
- **14B parameters:** Fits both A4500s with tensor parallelism, leaves headroom for Qdrant + embeddings
- **Instruction-tuned:** Follows the system prompt grounding rules reliably
- **Code understanding:** Strong structured output (JSON for FOLLOWUPS), markdown formatting, technical accuracy
- **Speed:** Faster streaming than 32B models, perceptibly more responsive for portfolio demos

The `pscode` naming in the service reflects a past experiment with a LoRA adapter trained on Python code (psaios project). The LoRA is NOT loaded in production — the base instruct model is used with RAG context instead of fine-tuning.

---

## WebSocket Architecture

The chat uses a WebSocket connection (not polling):

```
Browser → wss://dev.cwetzel.com/ws/chat
  FastAPI WebSocket handler
    → Qdrant search (3 docs)
    → vLLM streaming (token by token)
    → Browser renders chunks as they arrive
```

This enables real-time streaming: tokens appear as fast as the model generates them. The frontend shows "Searching knowledge base…" during RAG, then transitions to streaming text.

---

## Total Monthly Cost

- Cloud VPS (cwetzel.com): ~$20/month
- T5810 home server: owned hardware + electricity (~$30-40/month estimated)
- GPU compute: $0 cloud cost (owned A4500s)

Comparable cloud GPU inference (2× A4500 equivalent) would cost $3-5/hour. At moderate usage, owning the hardware pays off quickly and demonstrates the infrastructure competency directly.

---

## Engineering Decisions Worth Noting

**Persistent httpx client:** The FastAPI proxy uses a single `AsyncClient` via lifespan context rather than creating a new connection per request. This eliminates TCP handshake overhead on every RAG query.

**Grounding system prompt:** Low temperature + strict rules force the model to say "I don't have that documented" rather than hallucinate, and to always cite sources from the KB. RAG context does the factual grounding; temperature handles response naturalness.

**FOLLOWUPS pattern:** Instead of a separate API call to generate follow-up questions, the model appends them in a structured block at the end of its response. The frontend regex-parses and strips them, showing chips without an extra round-trip.

**OpenRC not systemd:** The T5810 runs Gentoo with OpenRC. Service management uses `rc-service` and `rc-update` with environment files in `/etc/conf.d/`. This is by design — Gentoo's init flexibility lets me tune startup dependencies precisely.

**Why RAG over fine-tuning:** A LoRA adapter (`20260429T133650Z-fc3ecc58`) was trained on the psaios Python project codebase. It's a code-completion adapter, not biographical. For factual Q&A about my experience, RAG with structured KB documents gives more accurate, citable answers than fine-tuning on narrative text. The LoRA exists but is not loaded in production.

**Why owned hardware over cloud GPU:** At moderate usage, an A4500 NVLink pair pays for itself in months vs. cloud GPU rental. More importantly, it's a portfolio signal in itself — the infrastructure is the demonstration.
