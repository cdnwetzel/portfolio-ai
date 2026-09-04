# What this system can honestly claim — 2026-09-04

Every number here was verified against the running system on the date shown, not carried
forward from an earlier document. **That is the point of the file:** most of the corrections
made this week were to claims that were true once and were never re-checked.

Three sections: what is measured, what needs a caveat, and what we stopped claiming. The
third is the one that makes the first two worth believing.

---

## 1. Measured — say these freely

| Claim | Evidence | Verified |
|---|---|---|
| Qwen3.8-27B-FP8 on 2× RTX A4500 (NVLink, TP=2), 32K context | `/api/system-info`, `/v1/models` | 2026-09-04 |
| **33.6–34.0 tok/s** single-stream generation | `bench-vllm.sh 8007 3`, three runs | 2026-09-04 |
| CUDA graphs on, custom all-reduce disabled, capture sizes capped | bench asserts all three flags, not assumed | 2026-09-04 |
| **~4.4× from CUDA-graph tuning** (6.2 → 27.7 tok/s at the time) | `t5810-vllm-cudagraph-tuning-2026-08-19.md` | 2026-08-19 |
| 40 GB VRAM total (20 GB per card) | `nvidia-smi` | 2026-09-04 |
| GPU power cap 165 W/card, chosen at the throughput/thermal knee | `gpu-tune.sh`, `nvidia-smi --query-gpu=power.limit` | 2026-09-04 |
| Out-of-band faithfulness verification is **actually running** | `verdicts.db`: **10,631 verdicts**, written the same day | 2026-09-04 |
| Verifier and reranker are **fail-open** — site answers without them | `api-proxy.py`; rerank falls back to cosine top-5 | code |
| Regression-gated deploys: 52-item golden set, **13 hard forbid-rules** | `eval/golden_set.yaml`; gate proven to fire on a real recurrence | 2026-09-02 |
| Deploy blocked unless a live self-test passes | `cloud/deploy.sh` runs it before finishing | 2026-09-02 |
| Metadata-only logging — never query or response content | `red-lines.md` #2, enforced in `api-proxy.py` | code |
| **642 W at the wall** for both boxes under load = 64 % of the UPS | Kasa KP125M smart plug | 2026-09-02 |
| Zero cloud GPU spend; ~$20/month VPS | — | — |
| 35 documents / 101 chunks indexed | `/api/system-info`, read **live** from Qdrant | 2026-09-04 |

---

## 2. True with a caveat — attach the caveat

### "Grounded" is not the same as "correct"
The verifier scores whether an answer's claims are supported by the retrieved chunks. **An
error in the chunks scores as grounded, because it is.** Two arithmetic errors in the case
studies — a payback period of ~5 months that was really ~6, and one of 1 month that was
really ~11 — passed *every* control this system has: they were faithfully grounded, the
judge scored them grounded, and no eval checks arithmetic.

Say "grounded in a curated knowledge base", not "verified correct". The only control that
catches a wrong source is a human auditing the source.

### The eval score is not comparable across versions
**Mean grounding 4.69** (42 grounded items, faithfulness 5.0, 0 safety hard-fails,
2026-09-02). Not comparable to the older 4.78 or 4.48: the set has grown and now deliberately
includes the hardest known failure cases. Quote the number *with* the set size and date, or
do not quote it.

### Throughput has two different numbers
**33–34 tok/s is single-stream.** A separate measurement showed ~115 tok/s aggregate at
concurrency 4 — that is continuous batching, a different axis, and it is capped by
`--max-num-seqs 4`. Do not merge the two into one speedup figure, and do not describe the
batching result as if a visitor experiences it: this site is single-stream dominated at a
2–3 % duty cycle.

### The GPU cap is applied at boot — with one gap
Proven that the runlevel starts `gpu-tune` and applies the cap (`openrc default` test,
2026-09-03, zero downtime). **Not** exercised for cold-boot driver timing. Bounded either
way by a 5-minute check that reapplies on drift, so worst case is five minutes at the 200 W
default, with a log line.

### Retrieval returns at most 2 chunks per document
`RAG_MAX_PER_DOC=2`. A fact that lives in only one chunk of a large document may not surface
for a differently-phrased question — this happened on 2026-09-03 with the GPU power cap, and
the fix was to state the fact where the question actually lands. Worth knowing before
claiming the KB "contains" something.

---

## 3. Withdrawn — do not claim these

| Withdrawn claim | Why |
|---|---|
| "Detects conflicting sources" | The system prompt instructs it to say so when sources conflict. Two documents genuinely contradicted each other about the verifier hardware and **it did not fire** — it picked the wrong one and stated it without hedging. Pushed on a second contradiction, it invented two separate artifacts rather than report one. It is not a control. |
| "verdicts.db backups, weekly digest with silence alerts" (Tier 7) | Neither is scheduled. One backup exists, dated 2026-08-06; the asrock has **no cron daemon at all**. Corrected in `CLAUDE.md`. |
| A single "4.5×" speedup | Merges CUDA-graph tuning (single-stream) with continuous batching (aggregate). Two mechanisms, two axes. |
| "165 W set at boot" (as stated before 2026-09-03) | It was not. The cards came up at the 200 W default; `/etc/local.d` never ran because `local` declares `after *` and starved behind vLLM's multi-minute start. True now, via an ordered service. |
| "The E2E canary runs every 30 minutes" (as stated before 2026-09-02) | Was parked at once/day during the UPS episode. Restored to 1800 s and verified. |

---

## The claim actually worth making

Not "this system is accurate". Every RAG demo claims that, and this one has been wrong in
public about its own GPUs, its own architecture, and its own arithmetic — all inside one week.

The defensible claim is narrower and rarer: **it is measured, it is gated, and it is explicit
about what it cannot catch.** The evidence is section 3. A system that publishes its
withdrawn claims is making a stronger statement than one that publishes only its wins.

---

**Maintenance rule.** Every row here carries a verification date. A row whose date is older
than the last hardware or model change is **not** a claim, it is a memory — re-verify it or
delete it. That failure mode is what produced most of section 3.
