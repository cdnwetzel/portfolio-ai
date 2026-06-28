# Plan: RAG & Chatbot Improvements (learnings from iChris + firm review)

**Status:** Design / backlog. Not yet built.
**Date:** 2026-06-27
**Source:** review of `../iChris/` codebase + docs, and the firm's monday.com trackers
(iChris — Project Tracker, PS AI OS — Project Tracker). Findings attributed inline so they're
traceable: `iChris:<path>` = built code; `mon:<id>` = monday item (roadmap/spec, may not be shipped).

## Context
cwdotcom is the reusable "speaks-as-Chris" RAG spine other projects build on (monday: `PRJ — cwdotcom`,
`bl009`). This plan captures the genuinely transferable improvements found in iChris and the firm's
AI roadmap, mapped to concrete cwdotcom changes. The strongest signals are where the **iChris codebase
and the monday roadmap independently agree**.

Current cwdotcom stack (baseline): embed (bge-base-en-v1.5, 768-d; 400-word/50-overlap chunks) →
Qdrant cosine top-15 → bge-reranker-base top-5 (1 chunk/doc) → vLLM Qwen2.5-Coder-14B → WS stream;
grounding system prompt + source citations; `scripts/selftest.py` (grounded/faithfulness gate) + hourly canary.

## Principles
- **Measure before/after.** Every change is gated by the self-test (and the graded eval once it lands).
  No quality change ships without a before/after on a fixed question set.
- **No regression, fail-open.** RAG sub-steps degrade rather than crash a turn.
- **One change at a time** through the harness, so a regression is attributable.

---

## TIER 1 — highest impact (both sources converge); do first

### 1.1 Graded, multi-signal eval with an INDEPENDENT judge
- **What:** replace selftest's boolean grounded-vs-fallback with graded axes (grounding / faithfulness /
  citation-correctness, 1–5), emitted to JSONL for *trend* tracking, judged by a model **different from
  the 14B** (echo bias), plus a small human golden set as backstop and explicit ship thresholds.
- **Source:** `iChris:ichris/eval/judge.py,harness.py,schemas.py,soak.py` (separate stronger judge, strict
  JSON, temp 0, JSONL) + `mon:bl89` ("single-signal judge has echo bias and penalizes assertive answers;
  v4.1 scored worse than v3 despite fixing hallucinations — the eval measured the wrong thing"; 5 signals;
  ship only if ≥3 of 5 incl. ≥1 programmatic + ≥1 human) + `mon:bl278` (5-dim rubric; promote at mean ≥3.5,
  no dim <2.5, over ≥15 evals; "multi-LLM convergence is NOT sufficient for sign-off — keep a human golden set").
- **cwdotcom change:** `scripts/selftest.py` (+ new `eval/` JSONL records, a ~30-Q golden set as YAML).
  **This is the same engine as the verifier** — see `plans/verifier-faithfulness-layer.md`; the independent
  judge requirement is satisfied by the spare-box 7-8B judge (≠ the 14B). Build once, use for both
  offline eval and live verification.
- **Effort:** medium. **Why first:** it makes every other change measurable; without it the rest is guesswork.

### 1.2 Query alias / expansion before Qdrant (cheapest recall win)
- **What:** a curated domain synonym/alias map; expand the query across aliases before the vector search.
- **Source:** `iChris:ichris/broker/mailhistory.py` (`DEFAULT_ALIAS_GROUPS`; distinctive-token search +
  re-rank against full query; measured confidence 0.70→0.85) + `mon:b017/bl019` (aliases auto-derived from
  co-occurrence).
- **cwdotcom change:** `cloud/api-proxy.py` `search_knowledge_base()` — alias-expand the query (project
  codenames, tech abbreviations, "RAG"↔"retrieval-augmented generation", tool/product names) before embed+search.
- **Effort:** low. Closes the "recruiter says 'your LLM project', KB says 'Qwen inference platform'" gap.

### 1.3 Prompt-version content-hash stamping
- **What:** `PROMPT_VERSION = sha1(system_prompt)[:8]`; stamp every eval/verdict record with it.
- **Source:** `iChris:ichris/llm/prompts.py:99` (hard-won: a constant stamp silently invalidated history when
  the prompt changed — couldn't tell prompt-regression from pipeline-regression).
- **cwdotcom change:** `cloud/api-proxy.py` (compute hash of the system prompt) + `scripts/selftest.py` (stamp records).
- **Effort:** trivial. High diagnostic value; pairs with 1.1.

---

## TIER 2 — real RAG quality / latency wins (medium effort)

### 2.1 Hybrid dense + sparse (BM25) retrieval in Qdrant
- **What:** add a sparse (BM25) vector alongside the dense vector; fuse results. Dense-only misses exact /
  rare-term matches (names, codenames, error strings).
- **Source:** `mon:bl75` (psretrieve: "dense + sparse BM25 in Qdrant", framed as replacing naive RAG).
- **cwdotcom change:** `scripts/index_with_embeddings.py` (add sparse vectors at index time) +
  `cloud/api-proxy.py` (hybrid query + fusion). Re-index required.
- **Effort:** medium. Gate on the graded eval (1.1).

### 2.2 Structure-aware chunking
- **What:** chunk on semantic boundaries (section headers, numbered lists) as atomic units instead of a
  naive 400-word/50 window; cleaner embeddings + citations.
- **Source:** `mon:bl75` (structure-aware / legal-aware chunking).
- **cwdotcom change:** `scripts/index_with_embeddings.py` `chunk_text()` → header/section-aware splitter. Re-index.
- **Effort:** medium. Gate on eval.

### 2.3 Speculative decoding (the latency lever previously written off)
- **What:** Qwen-1.5B draft model → 14B target in vLLM. Claimed 1.5–2× throughput / 30–40% lower TPOT for
  streaming — directly attacks cwdotcom's ~6 tok/s.
- **Source:** `mon:bl131`. **Caveat (from the item):** vLLM spec-dec is finicky with continuous batching —
  **benchmark vs baseline before committing**; revert if not a clear win.
- **cwdotcom change:** T5810 vLLM launch config (`/etc/pscode/pscode.conf` + `start-vllm.sh`):
  `--speculative-model` / draft config. No re-index. **Gate:** A/B tok/s + the graded eval (spec-dec must not
  change outputs, but verify).
- **Effort:** medium; **risk:** could destabilize the running 14B serving — test off-peak, easy rollback.

### 2.4 Token budget + minimal-retry fallback; audit enrichment fail-open
- **What:** explicit token-aware context budget; on overflow, retry with fewer chunks instead of erroring.
  Confirm an embed/rerank hiccup degrades (not crashes) a turn.
- **Source:** `iChris:ichris/llm/prompts.py` (`PromptBudget`), `endpoint.py:36-47` (minimal-retry),
  `broker/broker.py:118-133` (best-effort isolation) + `mon:b037` (map-reduce: summarize older, keep recent).
- **cwdotcom change:** `cloud/api-proxy.py` (we already cap chunks + fail-open the reranker; add the token
  budget + minimal-retry path and confirm embed-failure handling). Ties into the existing
  `context_manager.py` budget work.
- **Effort:** low-medium.

---

## TIER 3 — candidates / situational

- **BGE-M3 embeddings** (`mon:bl75`, 8192-ctx, multilingual, hybrid-native) — the *next* embedding ceiling
  above bge-base. We just moved to bge-base this session; treat M3 as a **later harness-gated A/B**, not an
  immediate re-index. Re-dim 768→1024 + re-index; pairs naturally with 2.1 (M3 does dense+sparse natively).
- **bge-reranker-v2-m3** (`mon:bl131`) — already in the reranker plan; 8K context, no chunk truncation.
- **Per-chunk citation granularity** (`mon:bl75`: source/section/page/scores, immutable) — we already ship
  source+score citations; section/page is the enhancement.
- **Voice exemplars** (`iChris:ichris/learning/exemplars.py`) — inject 1–2 relevance-ranked first-person KB
  samples as voice anchors. Marginal (already first-person + RAG); cheap if wanted.
- **Map-reduce long-history context** (`mon:b037`) — summarize older turns, keep recent verbatim. Marginal
  now (mostly single-turn); relevant if multi-turn grows.
- **Centralized text hygiene before chunking** (`iChris:ichris/textclean.py`) — strip HTML/entities/boilerplate
  once, before chunking, if any KB source carries boilerplate.
- **Robust JSON extraction + self-correcting retry** (`iChris:ichris/llm/prompts.py:185`, `endpoint.py:49`) —
  only if cwdotcom adds a structured-output sidecar; keep on the shelf (bot is currently prose streaming).
- **Matter-scoped collection isolation** (`mon:bl178`) — multi-tenant concern; N/A for single-tenant public
  cwdotcom, but the rule ("similarity search crosses logical boundaries by default; isolate by architecture")
  applies the day cwdotcom hosts a second corpus (e.g. an iChris mail collection beside the portfolio).

## Already covered / don't regress
- **Cross-encoder rerank + 1-chunk-per-doc cap** — more sophisticated than iChris's *shipped* retrieval, which
  is only TF-IDF cosine (`iChris:retrieval.py`; embeddings/Qdrant are future-work behind a Protocol). The
  monday BGE-M3/hybrid items are **roadmap/spec, not shipped code** — weight accordingly.
- Source citations + scores, fail-open reranker, grounding/refusal prompt — in place.
- PII scrub gate — iChris needs it for privileged mail; cwdotcom's KB is public portfolio content, N/A.

## Process to adopt
**Adversarial multi-model review** of the RAG pipeline (`iChris:reviews/`). Two rules worth stealing:
"a finding without a file:line citation is invalid" and "verify your own proposed fix is correct." Point a
periodic pass at RAG failure modes: empty-retrieval fail-open, reranker short-return, chunk-dedup off-by-one,
WS stream truncation.

## Recommended sequence
1. **1.3** (prompt-hash, trivial) → **1.2** (alias expansion, low) → **1.1** (graded eval + verifier, medium)
   — now everything is measurable.
2. Then the medium RAG wins gated by 1.1: **2.4** (robustness) → **2.1** (hybrid BM25) → **2.2** (structure-aware
   chunking) → **2.3** (speculative decoding, off-peak, easy revert).
3. Tier 3 as candidates, evaluated only when a Tier-1/2 item motivates them (e.g. BGE-M3 alongside hybrid).

See also `plans/verifier-faithfulness-layer.md` — item 1.1 here and the verifier are the same judge engine.
