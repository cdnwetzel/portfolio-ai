# UPS sizing for the T5810 — measured 2026-09-01

**Why this exists:** the context-window A/B (P2.3) was stopped mid-run because the T5810
draws more under inference than its UPS can supply. This is the number to buy against, and
the note to resume from.

---

## 1. Measured draw

Taken on the box while it was actually serving (`nvidia-smi` + Intel RAPL), not estimated
from TDP:

| Component | Idle (model resident) | Under inference |
|---|---|---|
| GPU 0 (RTX A4500) | 72 W | **165 W** (at cap) |
| GPU 1 (RTX A4500) | 63 W | **165 W** (at cap) |
| CPU package (Xeon E5-2699v4, RAPL) | — | **59 W** |
| **GPU subtotal** | **135 W** | **330 W** |

The CPU stays modest under this workload — vLLM is GPU-bound, so the 145 W TDP is not the
figure to plan around. 59 W was measured *while both GPUs were pegged*.

**Not directly measured** (no wall meter): 256 GB of DDR4 ECC, internal drives, chassis
fans, NVLink, and the motherboard. For a box of this class that is roughly 60–100 W.

**Estimated totals:**

| | DC (components) | AC (at the wall, ~90 % PSU efficiency) |
|---|---|---|
| Idle, model resident | ~250–290 W | **~280–320 W** |
| Under inference | ~450–490 W | **~500–545 W** |

**The current UPS is rated 330 W.** The two GPUs alone consume its entire capacity under
load, before the CPU or anything else. Even *idle with the model resident* is at or over it.

---

## 2. Why this matters more than the beeping

On line power the machine runs fine — the UPS is a pass-through and the overload alarm is
just an alarm. **The failure is what happens during an actual outage:** an overloaded UPS
drops its load immediately rather than transferring to battery. So a one-second utility blip
becomes an abrupt power cut on a machine holding

- a 29 GB model mid-inference,
- an open Qdrant collection (the entire retrieval index),
- a live SQLite verdict DB (`verdicts.db`), and
- a Gentoo root filesystem.

In other words, the UPS is currently providing approximately **none** of the protection it
exists for, and the risk is data corruption rather than downtime.

---

## 3. Recommendation

Both options under consideration are 1500 VA; the difference is real-power output.

| Option | Load at ~525 W | Verdict |
|---|---|---|
| 1500 VA / **900 W** | **58 %** | Works. Acceptable headroom. |
| 1500 VA / **1000 W** | **53 %** | **Preferred.** |

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

**A bigger UPS alone does not fix this.** At ~525 W, a 1500 VA unit gives roughly 5–10
minutes — enough to shut down cleanly, nowhere near enough to ride out a real outage.
Without automatic shutdown integration a bigger UPS just delays the same abrupt cut by a few
minutes.

So the purchase is only half the work:

1. Pick a UPS with a USB/serial data port supported by **NUT** (`sys-power/nut` on Gentoo)
   or apcupsd.
2. Configure a graceful shutdown at a battery threshold — stop `vllm-qwen38` and `qdrant`
   *first* so the model unloads and the collection flushes, then halt.
3. **Test it by pulling the plug**, on purpose, once. An untested shutdown path is a belief,
   not a control — the same lesson as the rest of this week.

---

## 5. Resuming the paused experiment

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
