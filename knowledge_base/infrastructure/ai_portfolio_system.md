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
| Reranker | bge-reranker-base (cross-encoder) | T5810 home server (CPU) |
| Tunnel | SSH reverse forward | VPS ↔ T5810 |

---

## RAG Pipeline

Every chat message goes through a Retrieval-Augmented Generation pipeline:

1. **Embed query:** The user's message is embedded using `all-MiniLM-L6-v2` (384 dims, CPU)
2. **Vector search:** Qdrant searches the `documents` collection using cosine similarity, returning the top-15 candidate chunks
3. **Rerank:** A `bge-reranker-base` cross-encoder (CPU, T5810) re-scores all 15 candidates against the query and keeps the top 5. Bi-encoder cosine is fast but imprecise — it surfaces candidates; the cross-encoder picks the genuinely most relevant. Runs on the T5810's idle CPU/RAM, no GPU contention with vLLM.
4. **Inject context:** The reranked top-5 docs are injected into the LLM system prompt
5. **Stream response:** vLLM streams the response token-by-token over WebSocket to the browser
6. **Extract follow-ups:** The model appends `FOLLOWUPS:[...]` at the end; the frontend parses and strips it, showing suggestion chips

This means the LLM is grounded in actual documented facts (my real projects, case studies, posts) rather than hallucinating biographical details.

---

## Knowledge Base

The knowledge base (indexed into Qdrant) includes:
- LinkedIn posts (top 10 by impressions, ~114K total impressions in 6 months)
- Case studies: SAP B1 global deployment, AVD 200-user migration, SOC2 Type II, disaster recovery
- Resume and professional context
- Infrastructure write-ups: T5810 homelab, this AI system
- Project docs: pxx (aider orchestrator), gentoo-machines (fleet config)

Documents are chunked at 400 words with 50-word overlap, embedded, and stored as vectors.

---

## Why Qwen2.5-Coder 14B?

The model was chosen for:
- **14B parameters:** Fits both A4500s with tensor parallelism, leaves headroom for Qdrant + embeddings
- **Instruction-tuned:** Follows the system prompt grounding rules reliably
- **Code understanding:** Strong structured output (JSON for FOLLOWUPS), markdown formatting, technical accuracy
- **Speed:** Faster streaming than 32B models, perceptibly more responsive for portfolio demos

The `pscode` naming in the service reflects a past experiment with a LoRA adapter trained on Python code. The LoRA is NOT loaded in production — the base instruct model is used with RAG context instead of fine-tuning.

---

## WebSocket Architecture

The chat uses a WebSocket connection (not polling):

```
Browser → wss://dev.cwetzel.com/ws/chat
  FastAPI WebSocket handler
    → Qdrant search (top-15) → bge-reranker (top-5)
    → vLLM streaming (token by token)
    → Browser renders chunks as they arrive
```

This enables real-time streaming: tokens appear as fast as the model generates them. The frontend shows "Searching knowledge base…" during RAG, then transitions to streaming text.

---

## Security & Privacy

The threat model is intentionally small — scoping decisions remove most classic web-app risks by construction:

- **No user data, no PII.** The knowledge base holds only public portfolio content — resume, case studies, LinkedIn posts, infrastructure write-ups. There are no visitor accounts, no customer records, no personal data collected.
- **No authentication needed.** The chat serves read-only public information about my career. Nothing a visitor does writes to a database, so there are no logins, passwords, or user records to protect.
- **Queries are not logged or stored.** The proxy logs only metadata — retrieval counts, timing, grounding status — never the content of a visitor's question or the model's response. Per-session chat history lives in the browser's localStorage only; nothing is persisted server-side.
- **Backend isolation.** vLLM (8004), Qdrant (6333), the embedding service (8005), and the reranker (8006) all bind to localhost on the T5810 and have no internet-facing ports. The public VPS reaches them only over an SSH tunnel with key-based auth.
- **Transport security.** All browser traffic is HTTPS/WSS with Let's Encrypt certificates, terminated at Apache on the VPS; the VPS↔home link is SSH-encrypted.
- **Bounded inputs.** Inference requests are capped at a maximum prompt length to prevent resource-exhaustion abuse.

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

**Why RAG over fine-tuning:** A LoRA adapter was previously trained on a Python code corpus as an experiment. It was a code-completion adapter, not biographical. For factual Q&A about my experience, RAG with structured KB documents gives more accurate, citable answers than fine-tuning on narrative text. The LoRA is not loaded in production.

**Why owned hardware over cloud GPU:** At moderate usage, an A4500 NVLink pair pays for itself in months vs. cloud GPU rental. More importantly, it's a portfolio signal in itself — the infrastructure is the demonstration.

---

## Model & Runtime Card

| Property | Value |
|---|---|
| Base model | Qwen2.5-Coder 14B Instruct |
| Model creator | Alibaba Cloud |
| Inference engine | vLLM 0.14.0 |
| Serving host | Dell Precision T5810, Gentoo Linux |
| GPU layout | 2× NVIDIA RTX A4500 20 GB, NVLink (40 GB aggregate) |
| Tensor parallelism | 2-way across the A4500 pair |
| Context window | 16,384 tokens |
| Reserved response budget | 2,048 tokens |
| Temperature | 0.35 |
| Top-p | 0.7 |
| Presence penalty | 0.5 |

---

## Ports & Services

All services on the T5810 bind to localhost only. The public VPS reaches them through an SSH reverse tunnel.

| Service | Port | Role | Fallback if unavailable |
|---|---|---|---|
| FastAPI proxy | 8000 (VPS) | WebSocket/API entry, RAG orchestration | None — chat stops |
| vLLM | 8004 | LLM inference | None — chat stops |
| Qdrant | 6333 | Vector search | None — chat stops |
| Embedding service | 8005 | `all-MiniLM-L6-v2` query/document embeddings | None — chat stops |
| bge-reranker-base | 8006 | Cross-encoder reranking of top-15 cosine candidates | Cosine top-5, capped at one chunk per source doc |
| SSH tunnel | 8004, 6333, 8005 forwarded | Secure VPS↔T5810 link | None — services unreachable from public internet |

---

## Reranker Fallback Behavior

The proxy always retrieves 15 candidate chunks from Qdrant using cosine similarity. It then asks the CPU reranker (port 8006) to re-score all 15 and return the best ones. If the reranker is unreachable, returns a non-200 status, or times out, the proxy fails open: it uses the original cosine-similarity order, applies the per-source-doc cap (max one chunk per document), and returns the top 5. Chat continues with slightly lower relevance precision.

---

## Cost Comparison

| Cost item | Owned hardware | Equivalent cloud GPU |
|---|---|---|
| Cloud VPS (edge) | ~$20/month | ~$20/month |
| T5810 + 2× A4500 | Already owned; electricity ~$30–40/month | N/A |
| GPU inference | $0/hour | ~$3–5/hour for A4500-class GPU |
| 24/7 light usage | ~$50–60/month total | ~$2,200–3,600/month |
| One-time hardware | ~$2,500–3,500 (used/refurb) | $0 upfront |

At moderate usage, the owned hardware breaks even in roughly 1–2 months versus renting equivalent cloud GPU time. The main trade-off is operational responsibility: power, cooling, hardware failures, and tunnel maintenance.

---

## Known Limitations & Honest Weaknesses

1. **No source citations in the UI.** Retrieved documents ground the answer, but the visitor cannot see which chunks were used. This makes it harder to verify claims.
2. **No live eval pipeline.** There is no automated test set that runs after prompt or KB changes. Quality is checked manually by asking test questions.
3. **Single point of failure.** The T5810 is one machine. A power outage, hardware failure, or ISP issue takes the chat offline until it recovers.
4. **No dynamic knowledge.** The KB is static Markdown files. Recent work after the last index run is not reflected until `scripts/index_with_embeddings.py` is re-run.
5. **Reranker runs on CPU.** It adds ~2–3 seconds of latency per query compared to a GPU reranker, but keeps GPU memory free for vLLM.
6. **Small embedding model.** `all-MiniLM-L6-v2` is fast but imprecise; it needs the reranker to place the right chunks in the final top 5.
7. **Context window limits.** Long conversations are compacted by dropping oldest turns, so multi-turn threads can lose earlier context.
8. **Model can still hallucinate.** The grounding rules reduce but do not eliminate hallucination, especially if the retrieved chunks are borderline-relevant.

Planned fixes: source citations in the UI, an eval test suite, and automated re-indexing on KB changes.
