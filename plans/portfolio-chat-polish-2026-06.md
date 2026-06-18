# Portfolio Chat Polish Plan — June 2026

## Goal
Make the portfolio AI assistant grounded, citable, trustworthy, and professionally presentable while keeping all inference local (Qwen 14B on vLLM / T5810).

## Scope & execution order

### 1. System prompt hardening (`cloud/context_manager.py`)
- Add identity line: built by Chris Wetzel, base model Qwen2.5-Coder 14B Instruct from Alibaba Cloud.
- Enforce first person.
- Add RAG-only rule: only answer from retrieved KB context; fallback to "I don't have that documented."
- Add citation rule: every factual claim must include `[source: filename]`.
- Add anti-jailbreak / instruction-hierarchy clause.
- Add anti-speculation clause: ban "likely", "probably", "may be" unless supported by retrieved text.

### 2. Source citations UI
- Update `cloud/api-proxy.py` to return top-N retrieved sources (`filename`, `score`, `snippet`) in the response payload.
- Update frontend message shape and render a collapsible "Sources" block under each assistant message.

### 3. KB fact-sheet updates (local-only)
- Update `knowledge_base/infrastructure/ai_portfolio_system.md` with:
  - Model card (Qwen2.5-Coder 14B Instruct, vLLM)
  - Exact hardware spec & ports/services table
  - Reranker fallback behavior (cosine top-5)
  - Known weaknesses / self-critique section
  - Cost table / cloud-cost comparison
- Add one failure/iteration case study to KB.

### 4. Retrieval guardrails
- Add score threshold in proxy: if no chunk passes threshold, return fallback refusal instead of generating.
- Add out-of-scope refusal for prompts like Python help or jokes unless covered by KB.

### 5. Frontend + repo polish
- Add social meta tags, OG/Twitter card, favicon, theme-color to `frontend/index.html`.
- Create `frontend/public/` with favicon and 1200×630 OG image.
- Remove dead deps `axios` and `zustand` from `frontend/package.json`.
- Lazy-load `react-syntax-highlighter` in `ChatWindow.jsx` and add `manualChunks` in `vite.config.js`.
- Remove stale `psaios_project.md` reference from `README.md:63`.

## Verification
- Re-run the test corpus after changes and confirm:
  - No impersonation.
  - No "GPT" hallucination.
  - Source citations appear.
  - Jailbreak refused.
  - Cost/weakness questions cite KB content.
