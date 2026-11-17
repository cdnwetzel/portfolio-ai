# Remediation plan — revised 2026-09-03

Supersedes `remediation-2026-09-02.md`. Most of that plan is done; this re-orders what is
left, and **the ordering principle has changed.**

Yesterday's plan was ordered by *what it costs a visitor*, which was right when the open
items were wrong answers being served. Those are fixed. What remains is a different mix, so
the order is now:

1. **What cannot be recovered from remotely** — an outage needing physical access outranks
   any quality issue, because everything else can be fixed from a laptop.
2. **What changes the discovery rate** — every defect fixed yesterday was found by Chris
   asking a question, not by any sweep. That is not a method that scales, and improving it
   is worth more than the next individual fix.
3. **What silently loses data.**
4. Quality, then known-unfixables.

---

## Done since the last revision

| Item | Evidence |
|---|---|
| Retired 3060 Ti / 7B advertised as current | reindexed, verified, pinned |
| "56 GB VRAM" (NVLink bandwidth relabelled) | now 40 GB, pinned |
| Architecture inverted (asrock "handles retrieval") | fixed, pinned |
| Topic bleed from the Gentoo fleet doc | fixed, pinned |
| Router deflecting real questions (`selection`→`election`) | deployed, 14 unit tests |
| Truncated FOLLOWUPS rendered as a clickable chip | deployed, 7 parser tests |
| AVD arithmetic ($39k → $32.5k, ~5 → ~6 months) | fixed |
| SAP arithmetic + inconsistent labour rate | $229.5k/yr, ~10.5 months, rate now printed |
| SAP warehouse count (5 vs 6 listed) | 6 confirmed by Chris, doc self-consistent |
| About-panel count drift | reads live from Qdrant |
| `forbid_substrings` was not actually gating | now blocks, verified by synthetic regression |
| GPU power cap: removed 130 W profile read as current | fixed, and the cap made retrievable |

Gate: **52 items, 42 grounded, mean 4.69, faithfulness 5.0, 0 forbid hits, PASSED.**

---

## P0 — Can take the site down, and may need hands on hardware

### P0.1 Two vLLM units are armed for the same port, model and GPUs
**Verified on the box 2026-09-03 — still live, nothing has changed.**

```
rc-update show default   ->  qwen38-writer | default
                             vllm-qwen38   | default
```

Both set `PORT=8007`, both serve Qwen3.8-27B-FP8 at TP=2, both use the same venv
`/opt/pscode/vllm-serve-env-0.27.1`.

**Why this is now the top item.** It is the only open defect that can take the site down
completely, it is triggered by something entirely routine (a reboot), and the recovery may
not be remote. Two vLLM instances contending for the same two A4500s is the scenario this
lab already has on record as causing *"OOM and GPU dirty-state crashes requiring a physical
PSU power cycle"*. vLLM's TP workers are separate processes that survive the API server
holding ~19 GB VRAM each, so the loser of the race does **not** fail cleanly.

**Correcting a claim made about this.** The framing that `/opt/pscode` existing again
*retires* the earlier reboot warning is backwards. A unit pointing at a deleted venv fails
fast and is harmless; a unit that can now successfully launch a second 27B on the same GPUs
is worse. The old warning is **superseded by a bigger one**, not retired.

- [ ] `rc-update del qwen38-writer default` — keep `vllm-qwen38`: newer (Aug 30 vs Aug 26),
      carries the orphan reaper / `respawn_max=0` / `CUDAHOSTCXX` hardening (the writer has
      none of it), is repo-tracked in `home/vllm-service/`, and is what is serving now
- [ ] Move `/etc/init.d/qwen38-writer.bak-20260826-202850` out of `/etc/init.d`. It is
      executable and startable — a third copy of the same service sitting where OpenRC looks
- [ ] **Verify by rebooting**, not by reading the runlevel. This defect is *about* boot
      behaviour, so a boot is the only honest test

---

## P1 — Change how defects are found

### P1.1 Every defect this week was found by Chris asking a question
Not one came from a sweep. The graded eval gates **known** defects; it discovers nothing.
Manual probing found: the 3060 Ti, the fake 56 GB, the inverted architecture, topic bleed,
the router deflection, the truncated chip, two arithmetic errors, the warehouse count, and
the 130 W power profile. That is a discovery method that depends entirely on someone
happening to ask the right question.

Worse, it is **statistically unreliable**: the 130 W answer and the 3060 Ti answer both
appeared roughly 1 run in 4. A defect that surfaces 25 % of the time is invisible to casual
use and to small manual samples — my own "verified clean across 6 phrasings" was not proof,
and I said it as though it were.

- [ ] **Systematic claim audit.** Enumerate every factual claim in the KB about the live
      system — model, ports, hardware, counts, throughput, versions — and check each against
      the machine. This is the method that caught the VRAM and architecture errors; run it
      deliberately instead of opportunistically
- [ ] **Repeat-sample the high-traffic questions.** Ask the top ~10 questions 5x each rather
      than 1x, because the failures observed are intermittent. One pass proves nothing
- [ ] Consider a periodic version of both, since the KB and the fleet drift independently

### P1.2 Why did the FOLLOWUPS array truncate?
The client fix makes a truncated array harmless, but nothing explains why it truncated. That
turn was short (8.1 s), so `max_tokens` exhaustion is unlikely.

- [ ] Check the proxy log for that request — upstream stream cut, or model stopped mid-array?

---

## P2 — Silent data loss

### P2.1 Backups and the weekly digest have never run
`verdicts.db` modified today; **one** backup, dated 2026-08-06. The asrock has **no cron
daemon at all** — `cronie` and `dcron` both absent, root crontab and `/etc/cron.d` empty, no
VPS timer covering it. `weekly_verifier_digest.sh` has never run either.

- [ ] Install a periodic-job mechanism on the asrock (**box change — needs authorization**)
- [ ] Schedule both, then **verify by checking the directory a day later**, not by checking
      that the crontab line exists

### P2.2 UPS has battery but no automatic shutdown
- [ ] Plug in the USB cable (**physical**)
- [ ] NUT: T5810 as `upsd` + `upsmon` master, asrock as slave halting first (both its
      services are fail-open, so the site keeps answering while it is down)
- [ ] Order: `vllm-qwen38` **as a service**, then `qdrant`, then halt
- [ ] **Pull the plug on purpose, once**
- [ ] Meter the two boxes separately — the 642 W split between them is still unknown

### P2.3 Alert delivery never verified end to end
- [ ] Send a test page to the critical ntfy topic; confirm it reaches the phone (**Chris**)

---

## P3 — Quality

- [ ] **P1.5 prompt reword** (scaffold leak root cause). Its own deploy and its own
      re-baseline against today's 4.69 — batching it makes a bad result ambiguous
- [ ] **The conflict rule is decorative.** It did not fire on a real contradiction and, when
      pushed, invented two artifacts rather than report one. Stop counting it as a control;
      decide whether to make it real or drop the claim
- [ ] **Verdict window** 25 s stopgap — at minimum, log the drops so silent loss is visible
- [ ] `FLEET-ENDPOINTS.md` D1 and D3 — both verified correct: the reranker row says CPU and
      implies the T5810 (it is CUDA on the asrock), and the tunnel list omits `8007` and
      `8016`, the two forwards that make RAG work. **T5810-owned file, not this repo's**
- [ ] Orphan venv `/home/chris/vllm-serve-env-0.27.1` (7.7 GB, nothing references it).
      **Do this separately from P0.1** so a surprise is attributable to one change

---

## P4 — Known limits, not tasks

- **Cross-chunk conflation** ("56 GB" from the NVLink line) is model behaviour. Layout makes
  it less likely; it does not make it impossible.
- **Premise inheritance across turns.** A wrong turn-1 answer generates follow-up chips about
  the wrong thing, and the grounding refusal then *corroborates* the false premise.
- **Faithfulness is not correctness.** Both arithmetic errors scored as grounded, because
  they were. No control here catches a KB that is wrong — only the P1.1 audit does.
- **DEFECT #15, "SAP One".** Two KB attempts; the first backfired by putting the wrong string
  into the corpus. Deliberately excluded from the deploy gate so the gate stays meaningful.

---

## Suggested order

**P0.1 first, today** — one command plus a reboot test, and it is the only thing that can
cost physical access.

**Then P1.1**, because it changes the rate at which everything else is found. Every other
item on this list is a known defect; the audit is the only line item that produces *new*
knowledge, and this week's evidence is that unknown defects outnumber known ones.

**Then P2.1**, the only silent-data-loss item that is purely software.

**P2.2/P2.3 whenever Chris is at the hardware.** **P3 as capacity allows**, prompt reword
last because it needs a clean re-baseline.
