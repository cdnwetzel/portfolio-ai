# Plan: Verifier Judge Hardening (Task 6)

> The 2026-07 diagnostic proved the faithfulness judge rated a fabricated "40 GB of
> storage" claim as `supported` (row ts 2026-07-04T23:56:06, faithfulness 0.857, not
> flagged). Reading the stored `claims_json` showed this was not one bug but three,
> failing at three different stages. This spec is one coherent diff addressing the two
> that counterbalance each other, and it defers the third deliberately.

## The three breaks (from the live claims_json)

1. **Rubric blessed a paraphrase it shouldn't have.** `JUDGE_SYSTEM` said "A paraphrase of
   a chunk's fact is still supported." The judge treated "20 GB memory and 40 GB of storage"
   as a paraphrase of "40 GB total VRAM" and passed it. A category/unit/role swap is not a
   faithful paraphrase.
2. **Evidence coupling made omissions invisible.** `_fire_verify` was handed the generator's
   own `context_docs`: the reranked set capped at `RAG_MAX_PER_DOC=1`, then token-trimmed.
   For a single-doc-dominant question that means ONE chunk of the very doc that is the
   answer. The judge marked a TRUE asrock fact `unsupported` because the disambiguating
   chunk was never in view. A verifier fed the generator's context shares the generator's
   blind spot: it can catch a claim the shared chunks *contradict*, never one they *omit*.
3. **Extraction missed the worst claim.** "both the NVIDIA and AMD GPUs" was never
   decomposed into a checkable claim, so it was never judged at all. Upstream of entailment.

## Why the fix order is forced

Tightening the rubric on the same thin evidence does not just underperform, it **inverts**
the failure mode: today you get false-supported (the storage pass); a stricter rubric on
one chunk gives false-unsupported at scale, flagging every true claim whose chunk got
capped out. That is worse, because it trains you to ignore flags. So evidence-widening and
rubric-tightening MUST ship together; the stricter rubric needs the wider evidence to score
correctly in both directions. Extraction-widening is the noisy one (more claims, some
false) and goes LAST, against a measured baseline on the tighter rubric.

The asymmetry that makes this safe: widening the *verifier's* evidence is nearly free (the
judge writes no prose, so more chunks only reduce false-unsupported and add contradiction
surface). Widening the *generator's* context is the risky one and stays behind the eval
(that is generator `_cap_per_doc`, tracked separately in the faithfulness plan, NOT here).

## The coherent diff (implemented, uncommitted)

**A. Rubric — `home/verifier-service/verifier_core.py` (`JUDGE_SYSTEM`).**
Removed the blanket "a paraphrase is still supported" clause. Now: `supported` requires the
SAME entities, roles, units, and categories; a changed category/unit/role/grouping is
`contradicted`, not supported, with explicit examples (VRAM called "storage"; CPU called a
GPU; per-item reported as aggregate; one machine's part attributed to another). Because
`compute_verdict` flags on `any(contradicted)` regardless of the 0.8 threshold, a category
swap now forces a flag even in an otherwise high-scoring answer.

**B. Evidence decoupling — `cloud/api-proxy.py`.**
- `rerank_documents(query, payloads)` now returns the FULL reranked list, uncapped. The
  per-doc cap moved out to the caller.
- `search_knowledge_base` returns `(context_docs, evidence_docs)`: `context_docs` =
  `_cap_per_doc(ranked, RAG_TOP_K)` for the generator (unchanged behavior); `evidence_docs`
  = `ranked[:VERIFIER_EVIDENCE_LIMIT]` (15) for the verifier, wide and uncapped.
- `_fire_verify(request_id, query, answer, evidence_docs)` — signature renamed; the judge is
  now fed the wide set, decoupled from the generator's budget in the signature, not sharing
  one object. New constant `VERIFIER_EVIDENCE_LIMIT = 15`.

**C. Fixtures — `home/verifier-service/fixtures.json` (+3, now 8).**
- `category_swap_vram_as_storage` → must flag (the exact live failure).
- `role_swap_cpu_as_gpu` → must flag ("both the NVIDIA and AMD GPUs").
- `true_crossmachine_fact_with_evidence` → must NOT flag: the true asrock fact, WITH its
  chunk present, proving the evidence-widening un-breaks the false-unsupported. The existing
  `paraphrase_still_supported` fixture is the guard that the rubric didn't over-tighten.

## Validation
- Offline: all modules compile; 14 verifier-core + 18 proxy unit tests pass; fixtures parse.
- Live (deploy-gated): `python3 home/verifier-service/run_fixtures.py --url http://<box>:8007`
  against the real Qwen2.5-7B judge. The 3 new fixtures are the ground truth for the rubric
  change; `paraphrase_still_supported` must stay green. This cannot be run offline (needs the
  7B judge); it runs on the asrock after deploy.

## Extraction widening — RESOLVED 2026-07-06: accept-the-gap (no judge change)
Isolating compound claims like "both the NVIDIA and AMD GPUs" so a false half can't hide
behind a true one. Investigated to a close; the shipped #6 judge is retained unchanged.

**What the data showed (four deterministic variants on the live 7B/CPU judge, temp 0):**
- v0 = shipped #6-only rubric: **9/9 fixtures**, including `compound_claim_split_one_false`
  flagged and `paraphrase_still_supported` clean.
- v1 strict decomposition instruction: paraphrase FLIPS to unsupported (0.0) — 8/9.
- v2 strict + broad leniency: paraphrase still fails AND `role_swap_cpu_as_gpu` leaks
  through — 7/9.
- v3 narrowed (conjunction-only) decomposition: paraphrase fails, role_swap AND compound
  both leak — 6/9.
The moment ANY decomposition text enters the prompt, this 7B judge stops honoring the
SSH-tunnel paraphrase (`cloud server reaches` ≈ `VPS talks to`, SSH tunnel ≈ "encrypted"
tunnel) and marks it unsupported. On a single-prompt 7B, compound-recall and
paraphrase-precision are in direct tension and cannot both be held. With #8 live, a
paraphrase false positive paints an amber "flagged" badge on a CORRECT answer → trains
flag-blindness. That trade is worse than the gap it closes.

**Why the gap is narrow anyway:** the compound class that MATTERS — a false half a chunk
*contradicts*, including the exact live failure "both the NVIDIA and AMD GPUs" — is already
caught by #6 (`role_swap_cpu_as_gpu` and `compound_claim_split_one_false` both flag on the
baseline; verified 9/9, twice, deterministic). The only genuinely-uncaught residual is a
compound whose false half is *chunk-silent* (unsupported, not contradicted) AND is diluted
below the 0.8 threshold by enough supported facts in the same answer. Narrow, and often a
plausibly-true add-on rather than a fabrication.

**Shipped:** `compound_claim_split_one_false` added to `fixtures.json` as a permanent
regression guard (passes on the baseline — locks in that a contradicted compound half gets
flagged). NO change to `verifier_core.py`; production judge unchanged; `flagged_rate`
unaffected (0.148 / 263 answers at close). If the narrow residual ever needs closing,
Approach #2 (two-pass: holistic pass A + conjunction-only pass B) or a stronger judge
(Approach #3) remain open — see `plans/` #7 close notes; both cost more than the gap is
worth today.

### Revisit trigger (reconfirmed 2026-07-06 — accept-the-gap holds)
Reopen on **evidence, not theory**. Triggers: a sustained `flagged_rate` drift, OR a real
chunk-silent false half riding below threshold in a *live* answer (seen via
`VERIFIER_DEBUG_CAPTURE`). Absent that, do not build — the gap is narrow, low-severity, and
out-of-band (monitoring, not gating).

When it does trigger, the order of attempts (cheapest first):
1. **Deterministic conjunction-splitter** in `verifier_core.py` — split obvious "X and Y"
   compounds into atoms *before* judging, no LLM call, no paraphrase risk, ~zero cost. Try this
   first; it likely captures most of the recall the residual needs.
2. **True two-CALL separation** (NOT the four single-prompt variants — those are refuted here):
   Pass A decomposer sees ONLY the answer (never the chunks, so it *structurally cannot* flip a
   paraphrase to unsupported); Pass B = the unchanged, proven 9/9 rubric. This is the one option
   the measured variants did not test, and the only reason accept-the-gap is a *judgment* call
   rather than settled. Cost: 2 judge calls; risk: 7B decomposer over-split → escalates to
   Tier 2 (distill + QLoRA). Only worth it if #1 is insufficient AND the gap is provably biting.
- **Enforcement wiring** — the proxy discards the verifier's return value; a flagged verdict
  is a log row nobody reads. Most urgent operationally and architecturally separate. Minimum
  viable: surface "this answer has a flagged claim" as a non-blocking UI footnote. Does not
  need to block; it needs to be *seen*.

## Guardrails
- No deploy/commit without Chris's go. Generator `_cap_per_doc` stays behind the eval; only
  the verifier's evidence was widened here.
