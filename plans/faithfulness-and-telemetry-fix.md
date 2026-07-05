# Plan: Faithfulness + Telemetry Fix

> Triggered by a live failure. Asked "Tell me about the GPU home lab setup," the
> system grounded correctly on `homelab_t5810.md` (top source 0.835) and still
> emitted two fabricated claims: "40 GB of storage" per A4500 (aggregate VRAM
> mislabeled as per-card storage) and "both the NVIDIA and AMD GPUs" (the asrock's
> Ryzen 9 5950X is a CPU; there is no AMD GPU). This is the exact failure the
> faithfulness layer exists to catch, so the question is whether it caught it, and
> whether we could even find out.

## Findings (recon)

1. **The source doc is not wrong.** `homelab_t5810.md:10` says "20 GB GDDR6 each,
   40 GB total"; `:30-54` is a section titled "Two Distinct GPU Machines — Do Not
   Conflate" that explicitly says never attribute one machine's CPU/GPU to the
   other. The model read the disambiguation and compressed it wrong. This is a
   generation + retrieval-packaging failure, not a data gap.

2. **The verifier is advisory and fail-open.** `api-proxy.py:509-511` fires it via
   `asyncio.create_task` AFTER the `done` event. It can record a verdict; it can
   never block or edit an answer. Best case it scored this and no one looked.

3. **The verifier may not even be enabled.** The committed `api-proxy.service` sets
   no `Environment` lines, and `_fire_verify` is a no-op unless `VERIFIER_URL` is
   set (`api-proxy.py:41,309`). If the running unit doesn't set it out-of-band, the
   answer was never scored.

4. **The "not stored or logged" UI claim is not literally true when the verifier is
   on.** `verifier.py:63-73` persists full `query` and `answer` text (plus
   `claims_json`, which is answer-derived) for 90 days in `~/verifier/verdicts.db`.
   The proxy honors the red-line (metadata only); the verifier DB does not.

## The passes (ordered; each is independently shippable)

### Pass 1 — Diagnose (read-only, time-sensitive, runs on the live boxes)
Do this BEFORE Pass 2, because the stored content we're about to purge is the only
thing that makes the score recoverable right now.

- On the cloud proxy box: `systemctl show api-proxy --property=Environment`
  → is `VERIFIER_URL` set? (enabled vs off)
- If enabled, on the asrock judge box (`10.0.1.115`):
  `sqlite3 ~/verifier/verdicts.db "SELECT ts, faithfulness, flagged, n_contradicted,
  verdict_type FROM verdicts WHERE answer LIKE '%40 GB of storage%' OR answer LIKE
  '%AMD GPU%' ORDER BY ts DESC LIMIT 5;"`
- Outcome settles "missed it" (flagged, no one looked) vs "wasn't listening" (off).

### Pass 2 — Telemetry: score + id only, no conversation text  [code: verifier.py]
Make the public claim honest and the score a durable, queryable metric.

- Lean schema: `request_id, ts, verdict_type, n_claims, n_supported, n_unsupported,
  n_contradicted, faithfulness, flagged, judge_model, latency_s`. Drop `query`,
  `answer`, `claims_json` from the persisted row.
- In-place migration on startup: detect legacy text columns, copy score columns to a
  fresh lean table, drop the old table. This also PURGES the 90 days of stored
  content, which is the privacy win.
- Opt-in debug capture (`VERIFIER_DEBUG_CAPTURE=1`, default off): only when explicitly
  enabled does it retain query/answer/claims in a separate `debug_captures` table for
  reproducing a specific hallucination. Off in production.
- `/review` degrades to scores + `request_id` (no content) unless debug capture is on.

### Pass 3 — Faithfulness (the careful, eval-backed core)  [code: KB doc, eval, prompt]
Do NOT hand-tune one prompt and declare victory. Gate it with the eval.

- **Regression gate first:** add `forbid_substrings` support to `eval_graded.py`
  (currently only `expect_substrings` exists) and add golden items for this exact
  failure ("40 gb of storage", "amd gpu", "both the nvidia and amd"). Now the bug
  is a permanent CI-style gate.
- **Source hardening:** disambiguate `homelab_t5810.md:10` so "40 GB total" cannot be
  read as per-card storage, and state plainly that GPU memory is VRAM, not storage.
- **Prompt hardening (general, not overfit):** SYSTEM_PREFIX gains a grounding line —
  do not invent spec categories absent from the sources (never call GPU memory
  "storage"); never attribute one machine's CPU/GPU to another.
- **Structural (Pass 3b, validate live):** the reranker caps at 1 chunk/doc
  (`_cap_per_doc`), so the "Do Not Conflate" guardrail may not travel in-context with
  the spec numbers. Evaluate allowing >1 chunk from the dominant doc. Retrieval-wide
  change → measure with the eval before adopting.

### Pass 4 — Voice (cut recitation)  [code: prompt; later: iChris LoRA]
The reply was verbose recitation ("high-performance computing tasks" x4), the
anti-voice. iChris owns a dedicated voice LoRA and lists cwdotcom as its persona
source, so this is a shared spine.

- Near-term: concise-answer style clause in SYSTEM_PREFIX (lead with the answer, no
  padding/repetition), validated against the eval so grounding doesn't regress.
- Later: route persona through the iChris voice layer.

### Pass 5 — The post
Write the build-in-public post once Pass 1 and Pass 3 are real: "I built grounded
infrastructure to avoid confident wrong answers. It invented a GPU spec against its
own source doc, and the verifier either missed it or whispered. Here's the fix."
Honest, not triumphant. Supersedes or sequels `post_queue_personal_ai_permissions.md`.

## Definition of Done
- [ ] Pass 1 outcome recorded (enabled? score?).
- [ ] Verifier persists no conversation text; migration purges history; claim is honest.
- [ ] `forbid_substrings` gate live; the two fabrications fail the eval before the fix
      and pass after.
- [ ] Source + prompt hardening in; graded eval mean grounding not regressed.
- [ ] Voice clause in; answers shorter, grounding held.
- [ ] Post drafted from the real verdict.

## Guardrails
- No deploy, commit, or push without Chris's go. Pass 1 runs first (it needs the
  running boxes and gates Pass 2's deploy).
- Changes here are local/working-copy only until Chris deploys them.
