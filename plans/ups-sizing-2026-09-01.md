# UPS sizing for the T5810 — measured 2026-09-01

**Why this exists:** the context-window A/B (P2.3) was stopped mid-run because the T5810
draws more under inference than its UPS can supply. This is the number to buy against, and
the note to resume from.

---

## 1. Measured draw

> **CORRECTED 2026-09-01, later the same day.** The first version of this note put idle
> GPU draw at 135 W. That reading was taken moments after a generation, while the cards
> were still spinning down — it was decay, not idle. Continuous sampling puts **true idle
> at 28 W GPU total**. The correction matters: it moves average whole-box draw from ~300 W
> to **~152 W**, which changes the runtime expectation substantially (though not the peak
> rating, which is what the purchase hinges on).

Taken on the box while it was actually serving (`nvidia-smi` + Intel RAPL), not estimated
from TDP:

| Component | True idle (model resident) | Under inference |
|---|---|---|
| GPU 0 (RTX A4500) | 21 W | **165 W** (at cap) |
| GPU 1 (RTX A4500) | 7 W | **165 W** (at cap) |
| CPU package (Xeon E5-2699v4, RAPL) | 28 W | **59 W** |
| **GPU subtotal** | **28 W** | **330 W** |

### This workload is BURSTY, and that is the whole point

From the proxy log (metadata only — request counts and timestamps, never content):

| | |
|---|---|
| generations/day | **193–367** |
| time per generation | **~8 s** (request → `Response: GROUNDED`) |
| GPU-busy time/day | **~26–49 min** |
| **duty cycle** | **~2–3 %** |

So the box sits at ~152 W AC about 97 % of the time and spikes to ~520 W for eight-second
bursts. It is a public portfolio chat with light traffic, not a training rig.

The CPU stays modest under this workload — vLLM is GPU-bound, so the 145 W TDP is not the
figure to plan around. 59 W was measured *while both GPUs were pegged*.

**Measured at the wall — a Kasa KP125M smart plug meters the UPS load.**

| | Scope | Under inference |
|---|---|---|
| Component sum, this note | T5810 alone | ~520 W (**estimate, never validated**) |
| **Plug reading** | **T5810 + asrock together** | **642 W** |

**These two figures are not comparable, and an earlier revision of this note wrongly compared
them** — declaring the estimate "23 % low" and, separately, adding an asrock estimate on top
of the 642 W to reach "~820 W". Both were wrong: the plug covers *both* machines, so the
642 W already includes the asrock, and there is no measurement of the T5810 by itself to
check the ~520 W estimate against.

**What is actually known:** 642 W for both boxes under real load, i.e. **64 % of the 1000 W
unit**. That is the number to plan against, and it is comfortable.

**What is still unknown:** the split between the two machines. Metering them separately with
the second KP125M (the KP125MP is a two-pack) would settle both the split and whether the
~520 W estimate for the T5810 was any good.

**The lesson, corrected:** not "component sums run low" — that was never demonstrated — but
**know what your meter covers before you reason from it.** A wattage figure without its scope
attached is how a correction turned into a double-count.

**Not directly measured on the T5810:** 256 GB of DDR4 ECC, internal drives, chassis fans,
NVLink, and the motherboard, assumed at roughly 60–100 W. Note this box runs **two PSUs
simultaneously** (the Dell 825 W internal plus the external Corsair 1000 W feeding the GPU
rails), each carrying conversion overhead well below its efficient load band — a plausible
reason a single-PSU model could under-predict it, but with no isolated measurement that
remains a hypothesis, not a finding.

---

## 2. The actual risk, stated honestly

> **HISTORICAL — this section describes the risk under the OLD 330 W UPS, which is what
> prompted the purchase.** It no longer describes the running system: both boxes are now on
> the 1500 VA / 1000 W unit at 64 % under load (§3). Kept because the reasoning is what
> justified the spend, and because the *shape* of the risk — a compound event, corruption
> rather than downtime — is unchanged and still governs the shutdown work in §4.

On line power the machine runs fine — the UPS is a pass-through and the overload alarm is
just an alarm. **The failure is a compound event:** an outage that happens *during* a
generation burst. The UPS is over its rating at that instant, so instead of transferring to
battery it drops the load.

Given a ~2–3 % duty cycle, that coincidence is unlikely per outage — this is not an
emergency. But two things keep it worth fixing rather than tolerating:

- the consequence is **data corruption, not downtime**, and
- traffic growth or any deliberate sustained load (an eval sweep, a benchmark soak, a
  reindex) raises the duty cycle and therefore the odds directly. This note exists because
  a 10-minute eval run pushed it to ~100 %.

When it does coincide, a one-second utility blip becomes an abrupt power cut on a machine
holding

- a 29 GB model mid-inference,
- an open Qdrant collection (the entire retrieval index),
- a live SQLite verdict DB (`verdicts.db`), and
- a Gentoo root filesystem.

In other words: the UPS protects the box for the 97 % of the time it is idle, and provides
nothing during the bursts. The exposure is data corruption, not downtime.

---

## 3. Recommendation

Both options under consideration are 1500 VA; the difference is real-power output.

> **RESOLVED: a 1500 VA / 1000 W UPS is fitted, carrying BOTH the T5810 and the asrock.**
> The old 330 W / 550 VA unit was kept for unrelated devices, which draw **116 W** on it (35 %).
>
> **Measured at the plug: 642 W for both boxes together, under real load — 64 % of 1000 W.**
> That is the concurrent peak, not a sum of separate maxima: the asrock's judge grades every
> answer the T5810 writes, so the two always load together. GPU side, sampled at 1 Hz on both
> boxes during one E2E probe: T5810 **330.0 W** (at the 165 W/card cap), asrock **63.5 W**.
>
> Headroom, scaling those GPU readings (estimates, not readings): both GPUs pegged — asrock to
> its 180 W cap, the 5950X toward 142 W PPT — is roughly **870 W (~87 %)**, and adding a
> return to the 200 W T5810 cap takes it to about **950 W (~95 %)**. Under rating, but that is
> where the remaining margin lives, so **avoid heavy lab inference on the asrock while the
> site is serving** (that box also hosts `llama3.3:70b`).
>
> **Correction, 2026-09-02:** a previous revision read the 642 W as the T5810 *alone* and
> added an estimated ~180 W for the asrock on top, reporting ~820 W / 82 %. The plug already
> included both boxes — a double-count, now withdrawn. The same revision claimed the ~520 W
> component-sum estimate below had been proven "23 % low"; that compared an estimate for one
> box against a measurement of two and is withdrawn as well. **The T5810's own draw has never
> been measured in isolation** — metering it separately with the second KP125M is the way to
> settle both questions, and the reason the table below is labelled "T5810 alone, estimated".
>
> The lesson that does survive: **know what your meter covers before reasoning from it.** A
> wattage number without its scope attached is how this happened.

| Option | Load at peak — **estimated** ~520 W, T5810 alone, UNVALIDATED | Load at peak — **measured 642 W, BOTH boxes** | Verdict |
|---|---|---|---|---|
| 1500 VA / **900 W** | 58 % | **71 %** | Would have worked at normal load, but ~97 % at the both-GPUs-pegged case — too close. |
| 1500 VA / **1000 W** | 52 % | **64 %** | **Correct choice** — and the worst case stays under rating at ~87 %. |

Both still clear the peak, which is what decides whether you get protection at all — but note
how much of the apparent headroom the estimate invented. At the real 642 W, a 900 W unit sits
at 71 % new, which is around 85 % effective after a few years of battery ageing, and leaves
no room at all for raising the GPU cap back to 200 W (+70 W → 79 %). The 1000 W unit absorbs
that; the 900 W one would have quietly foreclosed it.

**Take the 1000 W.** The price delta is small and it buys headroom for things already on the
table:

- The GPU cap is **165 W by choice, not by limit** (`/usr/local/bin/gpu-tune.sh`). Raising
  it to the 200 W default adds **+70 W** — measured 34.23 vs 33.43 tok/s, so it is a real
  option, just currently not worth 8 °C.
- Batteries lose capacity as they age; a UPS sized at 58 % new is closer to 70 % effective
  in three years.
- Any GPU change (a third card, or a swap to something hungrier — an RTX Pro 6000 has
  already been tested in this chassis) blows straight through a 900 W budget.

Sizing at ~50 % is also where most UPS designs are most efficient and where runtime is
long enough to be useful.

### Also check when buying

- **Pure sine wave output.** The T5810 runs a Dell 825 W internal PSU *plus* an external
  Corsair ATX 3.0 1000 W supplying the GPU rails. Active-PFC PSUs can behave badly on
  simulated/stepped sine wave, and this box has two of them.
- **Both PSUs on the UPS.** Powering only the internal one leaves the GPU rails unprotected,
  which is the opposite of useful — the GPUs are the load that matters.
- **Enough outlets on the *battery* side**, not just surge-only outlets.

---

## 4. The part that actually protects the data

**A bigger UPS alone does not fix this.** Runtime follows the *average*, and at ~152 W a
1500 VA unit will hold this box far longer than the peak-based estimate suggests — likely
tens of minutes rather than the 5–10 I first wrote. That is genuinely useful: it turns most
outages into a non-event.

But it is still finite, and an unattended box that runs the battery flat ends in exactly the
abrupt cut you bought the UPS to avoid. Without automatic shutdown integration, a bigger UPS
converts a corruption risk into a *slower* corruption risk.

So the purchase is only half the work:

0. **Verify the numbers first.** `/usr/local/bin/power-report.py` now reports peak, average
   and duty cycle from continuously sampled data (`home/power-metrics/`). Let it collect for
   a few days and buy against the observed peak, not against this note's estimate.
1. Pick a UPS with a USB/serial data port supported by **NUT** (`sys-power/nut` on Gentoo)
   or apcupsd.
2. Configure a graceful shutdown at a battery threshold — stop `vllm-qwen38` and `qdrant`
   *first* so the model unloads and the collection flushes, then halt.
3. **Test it by pulling the plug**, on purpose, once. An untested shutdown path is a belief,
   not a control — the same lesson as the rest of this week.

---

## 5. P2.3 context-window A/B — RESOLVED 2026-09-01: do not adopt

Run the night the UPS was fitted, both arms back to back under identical code, the same
42-item golden set and the same independent judge (Qwen2.5-14B-Instruct on the asrock,
grading answers written by Qwen3.8-27B — different family and size).

| | arm A (shipped) | arm B (wider) |
|---|---|---|
| `RAG_TOP_K` | 5 | **8** |
| `RAG_RETRIEVE_LIMIT` | 15 | **20** |
| `MAX_CONTEXT_TOKENS` | 14384 | **28000** |
| chunks actually reaching the generator | 5.00 | **7.75** |
| **mean grounding** (32 grounded rows) | **4.594** | **4.656** |
| mean answer length | 1295 chars | 1145 chars |
| mean total latency | 12.56 s | **13.26 s (+6 %)** |

**The +0.06 is noise, and the paired test says so plainly.** Scoring the same 32 questions
in both arms and testing the differences: mean difference **+0.062**, sd 0.504,
**t(31) = 0.70** against the 2.04 needed for p < 0.05, **95 % CI [-0.119, +0.244]** — it
straddles zero. **24 of 32 rows scored identically**; of the 8 that moved, 5 went up and 3
went down, which is what judge jitter looks like.

**Verdict: do not adopt.** 55 % more chunks bought a difference indistinguishable from zero
and cost **+6 % latency** — latency this site prints under every answer. Config reverted;
the proxy is back on code defaults (verified: `/api/retrieve` returns 5 chunks again, live
self-test 3/3).

Note the direction of the one signal that did move: with *more* context the answers got
**shorter** (1295 → 1145 chars). More retrieved text did not become more said.

**This is now the third A/B in a row where "more" lost on this KB** — hybrid dense+BM25
(4.41 vs 4.82), `chunk_size=250` (19/20 vs 20/20), and now wider retrieval. On a 35-doc,
99-chunk corpus the top-5 reranked chunks already contain the answer; adding candidates 6-8
adds tokens, not evidence. **Do not reopen without a hypothesis about what the current
pipeline is missing** — "try a bigger number" has now been measured three times.

### Two measurement notes worth keeping

**One transport error in arm B was not a regression.** "How old is Chris?" recorded
`ttfb=None, total_s=10.002` — exactly the harness's `open_timeout=10`, i.e. the WebSocket
never opened, which happens before any retrieval or generation and cannot be caused by
context width. Re-run 6x under the same arm-B config: 6/6 clean, 8 sources each. It tripped
the harness's hard-fail gate, but scored g=1 in **both** arms, so it does not move the
comparison. Transient.

**"How old is Chris?" scores g=1 in every run for a structural reason, not a defect.**
Personal facts come from the SERVER FACTS block, which is injected into the prompt but is
*not* a retrieved chunk — so the judge, which only ever sees retrieved chunks, cannot verify
the answer and correctly reports "No age information provided in sources." The harness
already treats it as review-level rather than a gate. Worth remembering before someone
"fixes" the answer.

---

## 6. Original resume procedure (kept for reference)

### The knobs (env-overridable, no redeploy)

P2.3 (context window / retrieval breadth) stopped here:

- **Baseline captured:** mean grounding **4.72**, 32 grounded evals, 0 safety hard-fails,
  one review-level flag ("How old is Chris?"). Settings: `RAG_TOP_K=5`,
  `RAG_RETRIEVE_LIMIT=15`, `MAX_CONTEXT_TOKENS=14384`.
- **Wider arm started and killed partway — no result.** It was `RAG_TOP_K=8`,
  `RAG_RETRIEVE_LIMIT=20`, `MAX_CONTEXT_TOKENS=28000`.
- Config was reverted; the proxy is on code defaults and healthy. Nothing left half-applied.

To resume, no redeploy is needed — the knobs are env-overridable now:

```bash
# on the VPS
cat > /etc/systemd/system/api-proxy.service.d/99-ctx-ab.conf <<'EOF'
[Service]
Environment=RAG_TOP_K=8
Environment=RAG_RETRIEVE_LIMIT=20
Environment=MAX_CONTEXT_TOKENS=28000
EOF
systemctl daemon-reload && systemctl restart api-proxy.service
# then, from the repo:
python3 scripts/eval_graded.py --url wss://dev.cwetzel.com/ws/chat
# revert:  rm .../99-ctx-ab.conf && systemctl daemon-reload && systemctl restart api-proxy
```

Keep the change only if mean grounding beats 4.72 by more than run-to-run noise (~0.1).
**Prior is against it:** on this KB, "more context" has lost every A/B so far — hybrid
dense+BM25 (4.41 vs 4.82) and `chunk_size=250` (19/20 vs 20/20) were both reverted on
evidence. A null result here is the expected outcome, and is still worth having in writing.
