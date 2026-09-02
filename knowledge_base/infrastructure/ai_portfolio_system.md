# AI Portfolio Chat System — Architecture & Design

## At a Glance

Portfolio AI (dev.cwetzel.com) is a self-hosted, full-stack Retrieval-Augmented Generation platform serving a personalized digital twin of my work. It runs on a secure, low-latency hybrid-cloud topology: **Apache** on an edge VPS terminates SSL/WSS and proxies traffic through an encrypted **SSH reverse tunnel** to a bare-metal **Gentoo Linux** home server — zero cloud compute cost. Inference is served by **vLLM** running **Qwen3.8-27B-FP8** with **tensor parallelism across an NVLink-bridged dual RTX A4500** GPU array. A custom **FastAPI** backend manages a 24K-character sliding-window context history, streams tokens over **WebSocket**, and grounds every response in a **Qdrant** vector database — **bge-base-en-v1.5 (768-d) cosine retrieval, reranked by a bge-reranker-base cross-encoder on a second GPU** — with an out-of-band faithfulness verifier independently scoring each answer's grounding.

---

## What This Is

The AI chat at dev.cwetzel.com is a full-stack AI inference system built on personal hardware. It's not a wrapper around OpenAI or a cloud GPU service — it runs on a Dell Precision T5810 in my home office on two RTX A4500 GPUs with a custom vLLM deployment.

The system demonstrates that high-quality AI inference can run on owned infrastructure at low cost, and that portfolio showcasing can be done with real engineering rather than polished demos.

**The code is open source:** https://github.com/cdnwetzel/portfolio-ai

If you're talking to this AI right now, you're using this system. The repo contains everything: the FastAPI proxy, the React frontend, the RAG pipeline, the Qdrant indexing scripts, and the vLLM service configuration.

---

## Where is the source code? Is this open source?

Yes. The full source is public at **https://github.com/cdnwetzel/portfolio-ai** — the FastAPI
proxy, the React frontend, the RAG pipeline, the Qdrant indexing scripts, the evaluation harness
and the vLLM service configuration. If you are talking to this AI right now, you are using the
code in that repository.

---

## Full Stack

| Layer | Technology | Where It Runs |
|---|---|---|
| Frontend | React + Vite + Tailwind CSS | Browser |
| Edge | Apache (SSL/WSS) + FastAPI (api-proxy.py) | cwetzel.com VPS |
| LLM | vLLM 0.27.1 + Qwen3.8-27B-FP8 | T5810 home server (2× A4500) |
| Vector DB | Qdrant (dense cosine, 768-d) | T5810 home server |
| Embeddings | BAAI/bge-base-en-v1.5 (768-d) | T5810 home server (CPU) |
| Reranker | bge-reranker-base (cross-encoder) | asrock B550 (RTX 5060 Ti, GPU) |
| Faithfulness verifier | Qwen2.5-14B-Instruct (Ollama, RTX 5060 Ti) | asrock B550 home server |
| Tunnel | SSH reverse forward (VPS → T5810 → asrock) | VPS ↔ home LAN |

### Why this system uses two home machines (and which does what)

Two GPU boxes, split by **what competes for VRAM**, not by "inference vs retrieval":

- **T5810** — the answerer, plus everything that does *not* need a GPU. It runs vLLM
  (Qwen3.8-27B-FP8) across its two A4500s, and alongside it **Qdrant** and the
  **bge-base embedder**. Those two are safe to co-locate because the embedder runs on
  **CPU** and Qdrant is memory/disk-bound — neither touches the A4500s, and the box has
  256 GB of RAM and 22 cores to spare. So retrieval costs the answerer nothing.
- **asrock B550** — the two jobs that *would* have competed for A4500 VRAM: the
  **bge-reranker-base** cross-encoder and the **Qwen2.5-14B-Instruct** faithfulness judge.
  Together they hold about 13 GB, which is 13 GB the answerer would have lost. Putting the
  judge on separate hardware also keeps it genuinely independent of the model it grades.

**The common way to get this backwards is to say the asrock "handles retrieval".** It does
not: Qdrant and the embedder — the retrieval core — are on the T5810. The asrock runs the
reranker and the judge. The split is about VRAM contention, and both of the asrock's
services are **fail-open**, so if that box is down the site still answers.

This is separate from the `gentoo-machines` fleet project, which documents kernel and
build configuration for many machines. Cross-compilation, build hosts and low-power
targets belong to that project and have nothing to do with how this chat is served.

---

## RAG Pipeline

Every chat message goes through a Retrieval-Augmented Generation pipeline:

1. **Alias-expand query:** The user's message is widened with a curated synonym/alias map (e.g. "LLM" ↔ "large language model", project codenames) so retrieval recall doesn't depend on exact wording.
2. **Embed query:** The expanded query is embedded using `BAAI/bge-base-en-v1.5` (768 dims, CPU).
3. **Vector search:** Qdrant runs a dense cosine-similarity search against the `documents` collection, returning the top-15 candidate chunks. (A hybrid dense+BM25 path with Reciprocal Rank Fusion was built and A/B-tested, but it *regressed* on this small, well-curated KB versus pure dense — so it's disabled in production, `HYBRID_SEARCH=0`. Dense cosine won.)
4. **Rerank:** A `bge-reranker-base` cross-encoder (GPU, asrock B550) re-scores all 15 candidates against the original query and keeps the top 5 (capped at one chunk per source document for diversity). Runs on the T5810's idle CPU/RAM, no GPU contention with vLLM.
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

Documents are chunked structure-aware — split on markdown section boundaries (merging small sections, splitting long ones to ~400 words) so each chunk is a coherent semantic unit — then embedded (dense, 768-d) and stored as vectors.

---

## Why Qwen3.8-27B?

The model was selected on measurement, not preference. It replaced Qwen2.5-Coder-14B-Instruct
on 2026-08-26 after a head-to-head on the production contract:

- **Grounding:** 100% vs 96.4% for the incumbent
- **Citation:** ~100% vs 71.4%
- **FOLLOWUPS trailer:** ~100% vs **7.1%** — the incumbent omitted it on 26 of 28 answers, so the
  site's suggestion chips were absent from roughly 93% of responses
- **Against the other candidate:** 75.0% vs 64.3% for a 35B mixture-of-experts build

It is a **reasoning model**, and chain-of-thought is deliberately disabled. With thinking on it
spends the entire token budget reasoning and returns empty content on long answers. The RAG task
here does not need visible deliberation — the reasoning is "read the retrieved sources and quote
them accurately."

**FP8 quantization** is what makes a 27B model fit: ~29 GB of weights split across two 20 GB
A4500s with tensor parallelism, leaving room for the KV cache. The A4500s are Ampere and have no
FP8 tensor cores, so weights are dequantized on the fly — a compute cost the GPUs absorb.

An earlier `pscode` LoRA experiment is visible in some service names. That adapter was never used
in production; the base model is grounded with RAG context rather than fine-tuned.

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
- **Backend isolation.** labrouter (8004, fronting the vLLM backends), Qdrant (6333) and the embedding service (8005) bind to localhost on the T5810 and have no internet-facing ports. The public VPS reaches them only over an SSH tunnel with key-based auth.
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

**Grounding system prompt:** Low temperature + strict rules force the model to say "I don't have that documented" rather than hallucinate, and to ground every claim strictly in the retrieved KB documents (sources are shown to the visitor in a separate panel, so the prose stays clean). RAG context does the factual grounding; temperature handles response naturalness.

**FOLLOWUPS pattern:** Instead of a separate API call to generate follow-up questions, the model appends them in a structured block at the end of its response. The frontend regex-parses and strips them, showing chips without an extra round-trip.

**OpenRC not systemd:** The T5810 runs Gentoo with OpenRC. Service management uses `rc-service` and `rc-update` with environment files in `/etc/conf.d/`. For local testing, the FastAPI proxy is started manually with `uvicorn cloud.api-proxy:app --host 127.0.0.1 --port 8000`. A production OpenRC service for the proxy currently runs only on the Ubuntu VPS; the T5810 services (vLLM, Qdrant, embeddings, reranker) are managed under OpenRC.

**Why RAG over fine-tuning:** A LoRA adapter was previously trained on a Python code corpus as an experiment. It was a code-completion adapter, not biographical. For factual Q&A about my experience, RAG with structured KB documents gives more accurate, citable answers than fine-tuning on narrative text. The LoRA is not loaded in production.

**Why owned hardware over cloud GPU:** At moderate usage, an A4500 NVLink pair pays for itself in months vs. cloud GPU rental. More importantly, it's a portfolio signal in itself — the infrastructure is the demonstration.

---

## Model & Runtime Card

| Property | Value |
|---|---|
| Base model | Qwen3.8-27B-FP8 |
| Model creator | Alibaba Cloud |
| Inference engine | vLLM 0.27.1 |
| Serving host | Dell Precision T5810, Gentoo Linux |
| GPU layout | 2× NVIDIA RTX A4500 20 GB, NVLink (40 GB aggregate) |
| Tensor parallelism | 2-way across the A4500 pair |
| Quantization | FP8 weights (~29 GB across 40 GB aggregate VRAM) |
| Context window | 32,768 tokens served (proxy budgets 14,384 for the prompt) |
| Reserved response budget | 2,048 tokens |
| Temperature | 0.2 |
| Top-p | 0.7 |
| Presence penalty | 0.0 (penalties punish re-using retrieved wording, which causes paraphrase drift on a factual task) |

### Speed (measured 2026-08-31)

- **Generation throughput:** **33.2 tokens/sec**, sustained over a 10-minute continuous soak.
- **Time to first token:** **~900 ms** for a realistic retrieval prompt (~2,800 tokens). Prefill
  runs at roughly 330 ms per 1,000 tokens.
- **Retrieval pre-step:** ~1 second end to end — embedding ~24 ms, Qdrant search ~1 ms, GPU
  rerank ~14 ms, plus network hops.
- **End-to-end per query:** dominated by answer length rather than hardware. A 256-token answer
  completes in about 8 seconds; a detailed 800-token answer takes roughly 25.

These figures follow a hardware correction on 2026-08-31. The GPUs had been running under a
leftover power profile that capped them at 130 W of their 200 W rating and locked the SM clock to
1200 MHz of 2100 — under load they were dragged to 705–810 MHz while sitting at only 50 °C.
Removing it moved generation from 29.4 to 33.2 tok/s and cut time-to-first-token by 32%. An older
revision of this page quoted ~6 tokens/sec, which described the previous 14B model under that
same throttle.

---

## Ports & Services

Home-server services bind to the LAN/localhost only. The public VPS reaches them through a single SSH reverse tunnel that terminates on the T5810; the T5810 in turn reaches the asrock box over the home LAN.

| Service | Port | Host | Role | Fallback if unavailable |
|---|---|---|---|---|
| FastAPI proxy | 8000 | VPS | WebSocket/API entry, RAG orchestration | None — chat stops |
| vLLM | 8004 | T5810 | LLM inference | None — chat stops |
| Qdrant | 6333 | T5810 | Dense vector (cosine) search | None — chat stops |
| Embedding service | 8005 | T5810 | `bge-base-en-v1.5` query/document embeddings | None — chat stops |
| bge-reranker-base | 8006 | asrock B550 (GPU) | Cross-encoder reranking of the top-15 candidates | Cosine order, one chunk per source doc |
| Faithfulness verifier | 8007 | asrock B550 | Out-of-band claim-level faithfulness scoring | Chat unaffected — verdicts pause (fail-open) |
| SSH tunnel | 8004/6333/8005 to T5810; 8016→asrock:8006, 8007→asrock | VPS → T5810 (→ asrock) | Secure VPS↔home link | None — services unreachable from public internet |

---

## Reranker Fallback Behavior

The proxy always retrieves 15 candidate chunks from Qdrant (dense cosine). It then asks the GPU reranker on the asrock (port 8006) to re-score all 15 and return the best ones. If the reranker is unreachable, returns a non-200 status, or times out, the proxy fails open: it uses the original cosine order, applies the per-source-doc cap (max one chunk per document), and returns the top 5. Chat continues with slightly lower relevance precision.

---

## Verification & Validation

The system spans two home servers, reached over a single SSH tunnel. Here is how a question travels and how it gets checked:

```
Browser ──HTTPS/WSS──> cwetzel.com VPS (FastAPI proxy)
                          │  RAG: alias-expand → embed → Qdrant (dense) → rerank → vLLM stream
                          │  (all home services reached at 127.0.0.1 via the SSH tunnel)
                          ▼
                  ── SSH reverse tunnel ──> T5810 (ai.cwetzel.com)
                          ├─ labrouter 8004 (-> vLLM), Qdrant 6333, embed 8005  (on the T5810)
                          ├─ rerank 8006, judge 8007                        (on the asrock B550)
                          └─ tunnel also forwards :8007 ──LAN──> asrock B550 (verifier)
```

**How the VPS reaches two home boxes through one tunnel.** The tunnel is a single SSH connection from the VPS that terminates on the T5810. Each forwarded port resolves its target *from the T5810's side*: ports 8004/6333/8005/8006 point at `127.0.0.1` (services on the T5810 itself), while port 8007 points at the asrock box's LAN address. So the T5810 doubles as the jump host — the VPS never needs a separate link to asrock; it rides the same tunnel, and the T5810 routes the verifier traffic across the home LAN. Nothing on either home server is exposed to the public internet.

**What the verifier does.** After every answer is delivered, the proxy fire-and-forgets `(question, answer, retrieved chunks)` to the verifier on asrock. A separate judge model (Qwen2.5-14B-Instruct on the RTX 5060 Ti — deliberately a different model family and size from the Qwen3.8-27B-FP8 that writes the answers, to avoid self-grading bias) decides, per claim, whether it is **supported**, **unsupported**, or **contradicted** by the retrieved chunks, and records a faithfulness score. This is out-of-band: it never blocks, delays, or rewrites the answer, and if asrock is down the chat is completely unaffected (the verdict simply isn't recorded). It turns "the answer is grounded" from a hope into a continuously measured signal, and flags drift for review.

**Offline evaluation.** Separately from the live verifier, a graded eval harness (`scripts/eval_graded.py`) runs a human-authored golden set through the live pipeline and scores grounding/faithfulness, with ship thresholds — the regression gate used before changes go live. The set grows as coverage improves — every production defect gets an entry so the fix is gated rather than remembered. **The current count and scores live in `eval/golden_set.yaml` and the eval output, deliberately not here:** this page has carried three different sizes over time (~30, 35, 42), each stale the moment a test was added. Ask about the *approach*, not the tally. A lightweight self-test also runs as a deploy gate and an hourly canary.

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

1. **Answer-level, not claim-level, citations.** Every answer shows a collapsible "Sources" panel listing the exact KB chunks that grounded it (title, source, relevance score, snippet) — deterministic, from the actual retrieval. What it does not do is tie each individual sentence to a specific source; attribution is at the answer level.
2. **The chat's compute is a single point of failure.** The T5810 is one machine; a power, hardware, or ISP issue takes the chat offline until it recovers. (The asrock verifier is *not* a SPOF — it fails open, so the chat is unaffected if it's down.)
3. **No dynamic knowledge.** The KB is static Markdown. Recent work after the last index run isn't reflected until `scripts/index_with_embeddings.py` is re-run.
4. **Reranker and verifier run on CPU.** Each adds latency versus a GPU, but keeps GPU memory free for vLLM (and keeps the judge on a separate box entirely).
5. **Context window limits.** Long conversations are compacted by dropping oldest turns, so multi-turn threads can lose earlier context.
6. **The model can still hallucinate.** Grounding rules + dense retrieval reduce but don't eliminate it, especially with borderline-relevant chunks. The out-of-band verifier doesn't *prevent* a bad answer reaching the user once — it catches it afterward and flags it for the next iteration.

Addressed since earlier versions: upgraded embeddings (MiniLM-384 → bge-base-768), a graded eval pipeline + golden set, a deterministic prompt-extraction guardrail, a live faithfulness verifier, and a per-answer Sources panel in the UI. Still planned: claim-level (per-sentence) citation and automated re-indexing on KB changes.
