# Eval: Model faithfulness A/B — pscode-14B vs qwen3-coder:30b

**Status:** MEASURED + VALIDATED (2026-08-10). Verdict: model choice GREEN, migration BLOCKED on GPU capacity (not quality).
**Date:** 2026-08-10 (isolated overnight run on the Mac M4)
**Method:** Held RAG context and system prompt constant; captured the live pscode answer plus its
retrieved sources from `wss://dev.cwetzel.com/ws/chat`, then generated a qwen3-coder:30b answer on
the **exact same sources** using the proxy's exact chunk formatting, and scored **both** answers with
the site's own faithfulness verifier (`:8007`, judge qwen2.5:14b on asrock, flag threshold 0.8).
**Harness:** `scratchpad/cwdotcom-ab/ab2.py` + `run_tonight.sh` (two-phase: generate all, then verify
all, to minimize GPU model swaps).

## Environment
- **Candidate:** `qwen3-coder:30b` (Q4, ~19 GB) running **GPU-resident on the Mac M4** (Metal /
  unified memory), fully isolated from the live fleet. No swapping; real substantive answers on every
  question. This host is a **measurement rig only** (offload is too slow for prod serving).
- **Incumbent:** `qwen2.5-coder-14b-pscode` via the live pipeline (t5810 vLLM).
- **Live site untouched throughout.** The 30B never ran on a fleet GPU (a prior attempt proved that
  starves the live rerank/embed path and degrades chat to "I don't have that documented").

## Result — grounded questions only (the honest comparison)

Only questions where **both** models received real KB grounding (5 sources) are comparable. Two of the
six questions retrieved **0 sources**; those are excluded from the model comparison (see caveat below).

| Question | pscode | flag | 30B | flag |
|---|---|---|---|---|
| What has Chris built? | 0.80 | | **1.00** | |
| Tell me about the GPU home lab setup | **1.00** | | 0.88 | |
| Consulting / MSP experience | 0.64 | FLAG | **1.00** | |
| Tell me about the pxx project | 0.42 | FLAG | **1.00** | |
| **mean** | **0.71** | **2/4 flagged** | **0.97** | **0/4 flagged** |

**Headline:** on grounded queries the 30B is materially more faithful (0.97 vs 0.71) with zero flags vs
two. It also **eliminates the incumbent's signature confabulation**: on the pxx question, pscode invented
a non-existent "Mac Studio T5810" model (0.42, flagged); the 30B did not (1.00). It wins by discipline,
not terseness — the 30B pxx answer is a complete, accurate feature list (~980 chars) making fewer claims
(3-8 vs pscode's 5-15), but real ones. This is direct evidence toward DEFECT_LEDGER #1 (grounding
hallucination, LIVE IN PRODUCTION).

## Caveat — the 0-source cases test a guardrail, not the models

Q5 ("How does this AI system work?") and Q6 ("Walk me through a major infrastructure project") retrieved
**0 sources**. This is decisive to read correctly:
- In **production**, the RAG guardrail refuses at 0-source **before the model is ever called**
  (`api-proxy.py`: `if not context_docs or context_docs[0].score < RAG_MIN_SCORE -> canned refusal`).
  This is **model-independent**.
- The harness deliberately bypassed that guardrail for the 30B (fed it 0 chunks; it answered anyway and
  hallucinated from the system-prompt text). pscode correctly refused. Q6's pscode was additionally a
  429 WebSocket error, not a real answer.
- Therefore Q5/Q6 tell us nothing about model quality; they confirm the **guardrail** is what protects
  faithfulness on ungrounded queries, for either model. The full-run means (pscode 0.71 / 30B 0.73) are
  muddied by these and should not be quoted; the grounded-only means (0.71 / 0.97) are the real result.
- **Implication for migration:** the guardrail must stay. It already does the job the incumbent's refusal
  behavior was doing, independent of which model sits behind it.

## Verdict
- **Model choice: GREEN.** The 30B is the more faithful model on grounded queries and removes pscode's
  confabulations. This settles the model question on the metric that matters (faithful to the KB facts).
- **Migration: BLOCKED on capacity, not quality.** cwetzel.com already owns both fleet GPUs (t5810 = LLM
  + embed/qdrant; asrock = rerank + verifier). A 30B on either starves the live pipeline. Migration
  requires the 30B to have its **own serving GPU**. The Mac run was the isolated proof; it is not a prod
  host.

## Reproduce
`scratchpad/cwdotcom-ab/` (session rig): `MODEL30=qwen3-coder:30b uv run --with websockets python3 ab2.py`
with the Mac Ollama on `:11434` and the verifier reachable on `:8007`. Raw rows in `result2.json`.
