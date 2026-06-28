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
| Edge | Apache (SSL/WSS) + FastAPI (api-proxy.py) | cwetzel.com VPS |
| LLM | vLLM + Qwen2.5-Coder 14B Instruct | T5810 home server (2× A4500) |
| Vector DB | Qdrant (hybrid: dense + BM25 sparse) | T5810 home server |
| Embeddings | BAAI/bge-base-en-v1.5 (768-d) | T5810 home server (CPU) |
| Reranker | bge-reranker-base (cross-encoder) | T5810 home server (CPU) |
| Faithfulness verifier | Qwen2.5-7B-Instruct (Ollama, CPU) | asrock B550 home server |
| Tunnel | SSH reverse forward (VPS → T5810 → asrock) | VPS ↔ home LAN |

---

## RAG Pipeline

Every chat message goes through a Retrieval-Augmented Generation pipeline:

1. **Alias-expand query:** The user's message is widened with a curated synonym/alias map (e.g. "LLM" ↔ "large language model", project codenames) so retrieval recall doesn't depend on exact wording.
2. **Embed query:** The expanded query is embedded using `BAAI/bge-base-en-v1.5` (768 dims, CPU).
3. **Hybrid search:** Qdrant runs a hybrid query against the `documents` collection — a dense (cosine) vector search **and** a BM25 sparse-term search — fused with Reciprocal Rank Fusion, returning the top-15 candidate chunks. Dense catches semantic matches; BM25 catches exact/rare terms (names, codenames, error strings) that dense embeddings miss.
4. **Rerank:** A `bge-reranker-base` cross-encoder (CPU, T5810) re-scores all 15 candidates against the original query and keeps the top 5 (capped at one chunk per source document for diversity). Runs on the T5810's idle CPU/RAM, no GPU contention with vLLM.
5. **Inject context:** The reranked top-5 chunks are fit to a token budget and injected into the LLM system prompt.
6. **Stream response:** vLLM streams the response token-by-token over WebSocket to the browser.
7. **Extract follow-ups:** The model appends `FOLLOWUPS:[...]` at the end; the frontend parses and strips it, showing suggestion chips.
8. **Verify (out-of-band):** After the answer is delivered, the proxy fire-and-forgets the `(query, answer, chunks)` to a faithfulness verifier on a separate box (asrock B550), which scores whether each claim is supported by the retrieved chunks. This never blocks or alters the answer — it's continuous drift monitoring (see "Verification & Validation" below).

This means the LLM is grounded in actual documented facts (my real projects, case studies, posts) rather than hallucinating biographical details — and the grounding is continuously *measured*, not just hoped for.

---

## Knowledge Base

The knowledge base (indexed into Qdrant) includes:
- LinkedIn posts (top 10 by impressions, ~114K total impressions in 6 months)
- Case studies: SAP B1 global deployment, AVD 200-user migration, SOC2 Type II, disaster recovery
- Resume and professional context
- Infrastructure write-ups: T5810 homelab, this AI system
- Project docs: pxx (aider orchestrator), gentoo-machines (fleet config)

Documents are chunked structure-aware — split on markdown section boundaries (merging small sections, splitting long ones to ~400 words) so each chunk is a coherent semantic unit — then embedded (dense) and BM25-encoded (sparse) and stored as vectors.

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

**OpenRC not systemd:** The T5810 runs Gentoo with OpenRC. Service management uses `rc-service` and `rc-update` with environment files in `/etc/conf.d/`. For local testing, the FastAPI proxy is started manually with `uvicorn cloud.api-proxy:app --host 127.0.0.1 --port 8000`. A production OpenRC service for the proxy currently runs only on the Ubuntu VPS; the T5810 services (vLLM, Qdrant, embeddings, reranker) are managed under OpenRC.

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

### Speed (measured)

- **Generation throughput:** ~6 tokens/sec (BF16 14B, tensor-parallel on the A4500 pair). Measured ~48s for a 300-token answer.
- **Time to first token:** a few seconds — the RAG pre-step (embed → Qdrant search → CPU rerank) adds roughly 3–4s before the model starts, then prefill, then streaming begins.
- **End-to-end per query:** short answers/refusals land in ~7s; typical grounded answers run ~20–50s; long, detailed answers can reach ~100s. It's tuned for grounded quality on a single-user portfolio demo, not raw speed — the GPUs are the bottleneck and that's an accepted trade-off.

---

## Ports & Services

Home-server services bind to the LAN/localhost only. The public VPS reaches them through a single SSH reverse tunnel that terminates on the T5810; the T5810 in turn reaches the asrock box over the home LAN.

| Service | Port | Host | Role | Fallback if unavailable |
|---|---|---|---|---|
| FastAPI proxy | 8000 | VPS | WebSocket/API entry, RAG orchestration | None — chat stops |
| vLLM | 8004 | T5810 | LLM inference | None — chat stops |
| Qdrant | 6333 | T5810 | Hybrid vector + sparse search | None — chat stops |
| Embedding service | 8005 | T5810 | `bge-base-en-v1.5` query/document embeddings | None — chat stops |
| bge-reranker-base | 8006 | T5810 | Cross-encoder reranking of the top-15 candidates | Fused order, one chunk per source doc |
| Faithfulness verifier | 8007 | asrock B550 | Out-of-band claim-level faithfulness scoring | Chat unaffected — verdicts pause (fail-open) |
| SSH tunnel | 8004/6333/8005/8006/8007 forwarded | VPS → T5810 (→ asrock) | Secure VPS↔home link | None — services unreachable from public internet |

---

## Reranker Fallback Behavior

The proxy always retrieves 15 candidate chunks from Qdrant (hybrid dense + BM25). It then asks the CPU reranker (port 8006) to re-score all 15 and return the best ones. If the reranker is unreachable, returns a non-200 status, or times out, the proxy fails open: it uses the original fused order, applies the per-source-doc cap (max one chunk per document), and returns the top 5. Chat continues with slightly lower relevance precision.

---

## Verification & Validation

The system spans two home servers, reached over a single SSH tunnel. Here is how a question travels and how it gets checked:

```
Browser ──HTTPS/WSS──> cwetzel.com VPS (FastAPI proxy)
                          │  RAG: alias-expand → embed → Qdrant hybrid → rerank → vLLM stream
                          │  (all home services reached at 127.0.0.1 via the SSH tunnel)
                          ▼
                  ── SSH reverse tunnel ──> T5810 (ai.cwetzel.com)
                          ├─ vLLM 8004, Qdrant 6333, embed 8005, rerank 8006  (on the T5810)
                          └─ tunnel also forwards :8007 ──LAN──> asrock B550 (verifier)
```

**How the VPS reaches two home boxes through one tunnel.** The tunnel is a single SSH connection from the VPS that terminates on the T5810. Each forwarded port resolves its target *from the T5810's side*: ports 8004/6333/8005/8006 point at `127.0.0.1` (services on the T5810 itself), while port 8007 points at the asrock box's LAN address. So the T5810 doubles as the jump host — the VPS never needs a separate link to asrock; it rides the same tunnel, and the T5810 routes the verifier traffic across the home LAN. Nothing on either home server is exposed to the public internet.

**What the verifier does.** After every answer is delivered, the proxy fire-and-forgets `(question, answer, retrieved chunks)` to the verifier on asrock. A separate judge model (Qwen2.5-7B on CPU — deliberately a *different* model than the 14B that wrote the answer, to avoid self-grading bias) decides, per claim, whether it is **supported**, **unsupported**, or **contradicted** by the retrieved chunks, and records a faithfulness score. This is out-of-band: it never blocks, delays, or rewrites the answer, and if asrock is down the chat is completely unaffected (the verdict simply isn't recorded). It turns "the answer is grounded" from a hope into a continuously measured signal, and flags drift for review.

**Offline evaluation.** Separately from the live verifier, a graded eval harness (`scripts/eval_graded.py`) runs a ~30-question human-authored golden set through the live pipeline and scores grounding/faithfulness, with ship thresholds — the regression gate used before changes go live. A lightweight self-test also runs as a deploy gate and an hourly canary.

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

1. **Source citations not surfaced in the UI.** The backend tracks which chunks grounded each answer (and sends them over the WebSocket), but the visitor-facing UI doesn't yet render them prominently.
2. **The chat's compute is a single point of failure.** The T5810 is one machine; a power, hardware, or ISP issue takes the chat offline until it recovers. (The asrock verifier is *not* a SPOF — it fails open, so the chat is unaffected if it's down.)
3. **No dynamic knowledge.** The KB is static Markdown. Recent work after the last index run isn't reflected until `scripts/index_with_embeddings.py` is re-run.
4. **Reranker and verifier run on CPU.** Each adds latency versus a GPU, but keeps GPU memory free for vLLM (and keeps the judge on a separate box entirely).
5. **Context window limits.** Long conversations are compacted by dropping oldest turns, so multi-turn threads can lose earlier context.
6. **The model can still hallucinate.** Grounding rules + hybrid retrieval reduce but don't eliminate it, especially with borderline-relevant chunks. The out-of-band verifier doesn't *prevent* a bad answer reaching the user once — it catches it afterward and flags it for the next iteration.

Addressed since earlier versions: upgraded embeddings (MiniLM-384 → bge-base-768), added hybrid dense+BM25 retrieval, a graded eval pipeline + golden set, a deterministic prompt-extraction guardrail, and a live faithfulness verifier. Still planned: UI source citations and automated re-indexing on KB changes.
