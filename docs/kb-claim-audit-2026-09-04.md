# Systematic claim audit — 2026-09-04

Method: collect ground truth from every machine, then check each documented claim against it.
This is the audit proposed in `plans/remediation-2026-09-03.md` §P1.1, run because **every
defect this week was found by Chris asking a question rather than by any sweep**.

Scope: hardware, ports, services, models, versions, counts. Performance claims are covered in
`docs/claims.md`.

---

## Ground truth collected 2026-09-04

| | T5810 | asrock B550 |
|---|---|---|
| CPU | Xeon E5-2699 v4, 44 threads | Ryzen 9 5950X, 32 threads |
| RAM (usable) | 251 GB | 62 GB |
| OS / kernel | Gentoo, 6.18.21-gentoo | Gentoo |
| GPU | 2× RTX A4500, 20,470 MiB each | 1× RTX 5060 Ti, 16,311 MiB |
| NVLink | NV4 | — |
| Power cap | 165 W, 165 W | — |
| ECC | Disabled | — |
| vLLM | 0.27.1, serves `qwen3.8-27b`, max_model_len 32768 | — |
| Qdrant | 101 points, 768-d, Cosine | — |
| GPU memory in use | 19,190 MiB × 2 (vLLM TP workers) | 13,362 MiB (judge + reranker) |
| Listening | 22, 6333, 6334, 8001, 8004, **8006**, 8007, 8787, 8788 | 22, 8006, 8007, 11434 |

---

## Findings

### A1. There are TWO rerankers, and only one is documented — **OPEN**
`rerank-service` is running on the **T5810** as well as the asrock:

```
/opt/rerank-service/rerank.py   ->  127.0.0.1:8006   (CPU, 1.6 GB RSS)
rc-update show default          ->  rerank-service | default      # starts every boot
```

It works — a live `/rerank` call returned real cross-encoder scores. It is **CPU-only**
(`nvidia-smi` shows only the two vLLM workers holding GPU memory).

`CLAUDE.md` describes the reranker as having *moved* from T5810 CPU to the asrock GPU and
lists the T5810's services as labrouter, Qdrant, embed and compress. **The CPU reranker was
never retired**, and nothing documents it.

**The risk is silent degradation, not cost.** `RERANK_URL` is env-overridable, and the VPS
tunnel forwards `VPS:8006 → T5810:8006`. Point it at 8006 by accident and the site keeps
working, just **15.8× slower on every rerank**, with no error and no health-check failure —
and the docs would actively mislead whoever investigated, because they say this service does
not exist.

Verified the site is *not* affected today: `RERANK_URL` is unset on the VPS, so the code
default `127.0.0.1:8016` (asrock GPU) applies. No established connections to T5810:8006.

**Not stopped.** It may serve the fleet or pxx; that is not this repo's call. Recommendation:
either retire it, or document it and give the two rerankers distinguishable ports so a
mis-set URL fails loudly instead of silently halving performance.

### A2. `CLAUDE.md` carried four chunk counts at once — **FIXED**
94, 94, 99 and 62 chunks, plus 34 and 35 docs, all simultaneously, all stale. Reality:
**101 chunks / 35 docs**.

This is the same drift that was removed from the KB yesterday when the golden-set size had
gone through ~30 / 35 / 42 — **and the same mistake: the instance was fixed, the class was
not.** The generalization was even written down at the time.

Fixed by deleting the counts rather than updating them, and adding a rule to `CLAUDE.md`:
`/api/system-info` reads the count live from the collection and cannot drift; quote that, or
quote a number *with the date it was measured*.

### A3. Claims that check out
Verified correct, no action:

- Xeon E5-2699 v4, 22C/44T · 2× A4500 · 20 GB per card / **40 GB total** · NVLink NV4 · ECC
  disabled · 165 W cap
- vLLM **0.27.1** · served as `qwen3.8-27b` · **32,768** context
- Qdrant **768-d cosine** on 6333 · embed on 8005 · labrouter on 8004 · compress on 8788
- asrock: Ryzen 9 5950X 16C/32T · 64 GB · RTX 5060 Ti 16 GB · judge
  `qwen2.5:14b-instruct-q4_k_m` · `RERANK_DEVICE=cuda`
- asrock GPU usage ~13 GB of 16 GB — measured **13,362 MiB**, matching the documented ~13 GB

### A4. Minor — RAM is quoted as installed, not usable
Docs say 256 GB (T5810) and 64 GB (asrock); `free` reports 251 GB and 62 GB. That is the
normal installed-vs-usable gap, not an error. Recorded so the next audit does not re-open it.

### A5. Stale comments in `labrouter.yaml` — **T5810-owned, reported not changed**
```yaml
qwen3.8-27b:  http://127.0.0.1:8007   # dense hybrid, 105k KV, 29.5 tok/s
pscode-14b:   http://127.0.0.1:8009   # Qwen2.5-Coder-14B (live lane for cwdotcom)
```
Two stale claims: throughput is **33–34 tok/s** measured today, not 29.5; and `pscode-14b` is
**not** cwdotcom's lane — the proxy pins `qwen3.8-27b` server-side. That file is fleet ground
truth owned by whoever changes the hardware, so it is flagged here rather than edited.

---

## What the audit says about the method

Two of five findings are cases where **a fix was applied to one instance while the
generalization was already written down** — the changelog-reads-as-current bug (fixed in one
KB file, still live in another until Chris found it) and the count drift (fixed in the KB,
still live in `CLAUDE.md`).

That is the actual failure mode worth naming: *writing down the class is not fixing the
class*. A sweep is not optional follow-up work after a fix — it **is** the fix.

---

## Part two — repeat sampling (run 2026-09-04)

Single-pass checking cannot clear this system: the 130 W and 3060 Ti defects each surfaced
roughly **1 run in 4**. So `scripts/repeat_sample.py` asks 10 high-traffic questions 5× each
and reports contradictions, not just wrong strings.

**Result: 150 generations across three passes, zero real defects.** Both questions that were
broken 1-in-4 two days ago are now stable, and the SAP answer gave the corrected 6
warehouses / 4 continents in **21 of 21** samples.

### The harness was wrong three times before the system was wrong once

First pass flagged three failures. All three were the probes:

| Flag | Reality |
|---|---|
| forbid `3060` on "What has Chris built?" | *"retired RTX 3060 Ti"* — a correct historical statement |
| forbid `29.4` on throughput | *"moved generation from 29.4 to 33.2 tok/s"* — correct, with the current value present |
| probe `"6 warehouse"` | missed every run that wrote *"six warehouses"* — word vs digit |

One root cause: **matching a token instead of the claim.** That is the same trap as the
router's `selection` → `election`, and the same lesson the golden set had already recorded the
previous day as *"encode the defect, not the token"* — repeated here by the person who wrote
that line. Probes are now regexes that accept word-or-digit forms, and history-vs-current is
checked by **requiring the current figure** rather than forbidding the historical one.

Second pass then reported the SAP question `UNSTABLE` because one run gave a shorter answer
that omitted the warehouse count. Across 21 samples it never once gave a *wrong* count. So the
harness now separates three outcomes:

- **FORBIDDEN** — a known-wrong value appeared. Failure.
- **UNSTABLE** — runs produced *different values* for the same fact. Failure, and the signature
  of an intermittent defect.
- **VARIABLE** — a fact was present in some runs and absent in others, never contradicted.
  **Informational, not a failure.** Answer length varies; calling that a defect is how a
  checker becomes noise people learn to ignore, which is DEFECT #8's failure mode.

Third pass: **0 FORBIDDEN, 0 UNSTABLE, 0 VARIABLE, 0 transport errors.**

### What this does and does not establish

It establishes that the ten most likely questions are stable across five runs each, including
every fact corrected this week. It does **not** establish that the KB is correct — 21 stable
runs of a wrong number would look identical to 21 stable runs of a right one. That is what
part one (claim-vs-machine) is for, and why both halves exist.
