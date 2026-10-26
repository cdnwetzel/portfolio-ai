# Current Work — 2026

**What Chris is working on in 2026, beyond the day job (IT Manager, Portnoy Schneck LLC).**

## The Portfolio AI Chat (this system)

The main 2026 side project: a production RAG chat over his own professional knowledge base,
running entirely on owned hardware. Live at dev.cwetzel.com.

### What is running RIGHT NOW (as of 2026-09-02)

State this, not the history below, when asked what the system runs or what hardware it uses.

- **Answerer:** **Qwen3.8-27B-FP8**, 32K context, served by vLLM across **2x RTX A4500**
  (NVLink) in the T5810.
- **Faithfulness judge:** **Qwen2.5-14B-Instruct** on the **RTX 5060 Ti 16 GB** in the asrock
  B550.
- **Reranker:** **bge-reranker-base** cross-encoder, on that same RTX 5060 Ti.
- **That is the complete GPU inventory: two A4500s and one 5060 Ti.** There is no RTX 3060 Ti
  and no 7B model in this system — both were replaced in 2026 and are listed below only as
  history.

### The 2026 changelog — RETIRED hardware and superseded numbers appear here

Everything in this section describes *changes over time*. Items named as the "from" side of a
change are **no longer in use**.

- **Credibility pass (July 2026):** full doc-vs-code audit — rate limiting on the public
  WebSocket, honest deployment docs,
  live system-info values, browser-localStorage chat persistence, an explicit PII policy
  (public contact email OK, phone/SSN never), and a dead-reference sweep.
- **Verifier upgrade (July–Aug 2026):** the out-of-band faithfulness judge was upgraded to
  **Qwen2.5-14B-Instruct on an RTX 5060 Ti 16 GB**, 16K context. It replaced an earlier
  Qwen2.5-7B on a 3060 Ti 8 GB — **that 7B model and that 3060 Ti are retired and are not
  part of the system today.** The upgrade was gated by a 9/9 fixture run and a graded
  golden-set eval before deploy.
- **GPU reranker (Aug 2026):** the bge-reranker-base cross-encoder moved from T5810 CPU
  (~4.1s per query) to the 5060 Ti GPU (**~0.26s, ~16x faster**). Verified: identical scores
  CPU vs GPU. Time-to-first-token improved as a result; for the current figure see the live
  per-message telemetry printed under every answer, which is typically **1-2 s** on the
  Qwen3.8-27B configuration — much faster than the ~5.6 s recorded right after this change,
  because the answerer and its tuning changed afterwards.
- **Voice + UX (Aug 2026):** first-person persona, query routing (meta/off-topic questions
  skip retrieval), multi-turn context, adaptive answer length, stop button, chat history
  persistence in the browser.

## Hardware changes

- The verifier box (asrock B550, Ryzen 9 5950X) **currently has an RTX 5060 Ti 16 GB**, which
  hosts both the 14B judge and the GPU reranker. It replaced a 3060 Ti 8 GB, which was removed
  from service in 2026 and is not part of the current system.
- The T5810 (2× RTX A4500, NVLink) serves the answerer via vLLM at 93% VRAM. As of 2026-08-26
  that is **Qwen3.8-27B-FP8**, which replaced the previous 14B on measured grounding and citation.

## Engineering practices this project runs on

- **Gated deploys:** fixture gates (9/9) and a graded golden-set eval before any judge change;
  a live self-test battery gates every code deploy. The golden set grows over time — every
  production defect earns an entry. **Its size and latest scores are not recorded here on
  purpose**; they live in `eval/golden_set.yaml` and the eval output, because every number
  written into this page went stale the next time a test was added (it has said ~30, 35 and
  42 at different points).
- **Fail-open verification:** if the judge box dies, chat is unaffected.
- **WebSocket rate limiting:** the public `/ws/chat` endpoint allows **2 concurrent
  connections per IP** (HTTP 429 beyond that). Not 1 — the browser opens the next turn's
  socket before the previous close is processed, so a limit of 1 rejected users' own
  follow-up questions and surfaced as "Connection lost".
- **A defect ledger:** known issues (hallucinated SAP answer, verifier wiring outage) are
  tracked, root-caused, and closed with evidence — not lost in chat history.
- **Metadata-only observability:** verdicts, latencies, and flagged rates are recorded;
  conversation content never is (privacy red line).
- **Continuous improvement loop:** weekly review of judge-flagged answers drives KB and
  prompt fixes — the system improves from its own defect signal.

## Content work

Ongoing LinkedIn writing on AI governance, M365/Copilot permissions, and infrastructure
lessons (see Posts). 2026 themes: credential scope for AI agents, MSP readiness, and
transparency post-mortems (Cloudflare outage series).
