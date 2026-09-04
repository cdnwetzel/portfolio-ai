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

## Not yet done

`docs/claims.md` §2 notes the failures observed this week were intermittent — the 130 W and
3060 Ti answers each surfaced roughly **1 run in 4**. Repeat-sampling the top questions 5× is
the second half of this audit and has not been run.
