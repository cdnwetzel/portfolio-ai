# Current Work — 2026

**What Chris is working on in 2026, beyond the day job (IT Manager, Portnoy Schneck LLC).**

## The Portfolio AI Chat (this system)

The main 2026 side project: a production RAG chat over his own professional knowledge base,
running entirely on owned hardware. Live at dev.cwetzel.com. What it went through in mid-2026:

- **Credibility pass (July 2026):** full doc-vs-code audit — rate limiting on the public
  WebSocket (1 concurrent connection per IP, HTTP 429 on duplicates), honest deployment docs,
  live system-info values, browser-localStorage chat persistence, an explicit PII policy
  (public contact email OK, phone/SSN never), and a dead-reference sweep.
- **Verifier upgrade (July–Aug 2026):** the out-of-band faithfulness judge moved from
  Qwen2.5-7B (RTX 3060 Ti) to **Qwen2.5-14B-Instruct on a new RTX 5060 Ti 16 GB**, with a
  16K context window. Gated by a 9/9 fixture run and a 35-question golden-set eval
  (mean grounding 4.48/5) before deploy.
- **GPU reranker (Aug 2026):** the bge-reranker-base cross-encoder moved from T5810 CPU
  (~4.1s per query) to the 5060 Ti GPU (**~0.26s, ~16x faster**), cutting time-to-first-token
  from ~9s to ~5.6s. Verified: identical scores CPU vs GPU.
- **Voice + UX (Aug 2026):** first-person persona, query routing (meta/off-topic questions
  skip retrieval), multi-turn context, adaptive answer length, stop button, chat history
  persistence in the browser.

## Hardware changes

- The verifier box (asrock B550, Ryzen 9 5950X) got an **RTX 5060 Ti 16 GB** (was 3060 Ti 8 GB),
  which now hosts both the 14B judge and the GPU reranker.
- The T5810 (2× RTX A4500, NVLink) serves the answerer via vLLM at 93% VRAM. As of 2026-08-26
  that is **Qwen3.8-27B-FP8**, which replaced the previous 14B on measured grounding and citation.

## Engineering practices this project runs on

- **Gated deploys:** fixture gates (9/9) and a graded golden-set eval before any judge change;
  a live self-test battery gates every code deploy.
- **Fail-open verification:** if the judge box dies, chat is unaffected.
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
