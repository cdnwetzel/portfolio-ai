# Remediation plan — 2026-09-02

Everything found by probing production on 2026-09-01/02, plus the ops gaps found by
auditing the defect ledger against the live boxes. Ordered by what it costs a visitor.

**Two things gate almost all of it:**
- `./cloud/deploy.sh` — puts committed code live (**authorization required**)
- `./scripts/reindex_kb.sh` — puts committed KB edits live (**authorization required**)

Nothing in `git` is reaching users until those run. Two code fixes and three KB fixes are
already committed and inert.

---

## P0 — Live, user-visible, factually wrong

### P0.1 Retired hardware presented as current — **KB fixed, needs reindex**
Answers list **"Qwen2.5-7B on an RTX 3060 Ti"** as a current component, and assign it the
verifier role. Neither exists. Traced to `current_work_2026.md`, a changelog whose
"moved from A to B" sentences read as "the system has A and B" once chunked.

Committed (`f869bc7`): a **"What is running RIGHT NOW"** block stating the complete GPU
inventory positively before any history, and retired items named as retired in the same
sentence so a chunk cannot lose the framing.

- [ ] Reindex, then verify across ≥4 phrasings that no 3060 Ti or 7B appears
- **Gate:** this is the one that must be re-asked, not assumed. "Add it to the KB" is not
  a fix.

### P0.2 Router deflected real questions — **FIXED, needs deploy**
`"selection"` contains `"election"`; 8/10 probes deflected, including questions about this
system's own evaluation. Fixed at `57a5832` with word boundaries plus de-ambiguated
keywords, 14 regression tests in two directions.

- [ ] Deploy

### P0.3 Truncated FOLLOWUPS became a clickable chip — **FIXED, needs deploy**
A cut-off array rendered as a chip labelled with raw JSON; clicking it sent that text as a
query and seeded a garbage turn. Fixed at `57a5832`.

- [ ] Deploy
- [ ] **Separately: find out why the array truncated at all.** The client fix makes the
      symptom harmless but does not explain it. That turn was short (8.1 s), so
      `max_tokens` exhaustion is unlikely. Check the proxy log for the request: was the
      upstream stream cut, or did the model stop mid-array?

### P0.4 Arithmetic in the KB is wrong
`avd_migration_200_users.md:237` — *"$155/user/month x 210 users = $39k/month.
Payback: ~5 months."*

**$155 x 210 = $32,550.** Payback at the correct figure is **6.1 months**. The $155 itself
is right ($300 Citrix - $145 AVD); the multiplication is not.

This is the most damaging class here, because **nothing in the system can catch it.** The
answer is faithfully grounded; the verifier scores it grounded; the golden set does not
check arithmetic. A reader who does the multiplication finds a 20 % error on a portfolio
whose selling point is rigour.

- [ ] Correct to $32,550/month and ~6.1 months
- [ ] **Sweep every other derived figure in the case studies** — this was found by
      accident, so assume it is not the only one. Check SAP's "$200k build / $68k maintain
      / $212k savings / 1 month payback" and the AVD cost tables.

---

## P1 — Correctness and credibility

### P1.1 Cross-chunk conflation invents facts
Two observed:
- **"2x RTX A4500 (56 GB total VRAM)"** — they are 20 GB each, 40 GB aggregate. **56 GB/s
  is the NVLink bandwidth**, four lines away under a different heading. The model took a
  number from the bandwidth line and relabelled it capacity.
- **"the 2026-08-31 evaluation... mean grounding 4.48"** — no such evaluation. The date
  comes from a *Speed* section in one document, the score from a different document.

**This is model behaviour and cannot be eliminated by editing.** It can be made harder:

- [ ] Separate the VRAM and NVLink-bandwidth figures so they cannot land in one chunk, and
      state capacity in a form that resists relabelling ("40 GB of VRAM in total: 20 GB on
      each of two cards")
- [ ] Avoid bare dates next to unrelated metrics; attach each measurement to its own
      subject in the same sentence
- **Honest limit:** this reduces the odds. It does not make the failure impossible.

### P1.2 Architecture stated backwards
*"ASRock B550 handles retrieval (Qdrant, embeddings, reranker)"* — Qdrant and the CPU
embedder run on the **T5810**; only the reranker and verifier are on the asrock. The model
then justified the inversion with plausible reasoning ("avoids competing for A4500 VRAM").

- [ ] Add a single unambiguous per-service placement table to `ai_portfolio_system.md`,
      phrased so one chunk carries the whole mapping
- [ ] Add "which machine runs Qdrant / the embedder / the reranker" to the golden set

### P1.3 Topic bleed — the Gentoo fleet doc answers AI-system questions
*"Why use two separate machines?"* pulled `gentoo_machines.md` and produced kernel
cross-compilation content, then the follow-up chips walked further into the unrelated
fleet. **Nothing is removed** — the Beelink legitimately belongs to that project, and the
fleet names are generic product models, so nothing is disclosed. The defect is that a
question about *this chat's architecture* retrieved a *different project's* doc, because
both legitimately discuss the T5810 and B550.

- [ ] Give `gentoo_machines.md` an opening line that names its scope, so any chunk of it
      announces which project it belongs to
- [ ] Make `ai_portfolio_system.md` answer "why two machines" directly and specifically,
      so it outranks on that question
- [ ] Add "why does this system use two machines" to the golden set

### P1.4 The conflict rule does not fire
The prompt says *"When sources conflict: 'My knowledge base has conflicting information on
this.'"* Two documents genuinely disagreed about the verifier (14B/5060 Ti vs 7B/3060 Ti).
It did not fire. It picked the wrong side and stated it without hedging. Asked about the
golden set, it did something worse — **invented two artifacts** ("a 35-question harness"
and "a ~30-question golden set") to reconcile a contradiction rather than report it.

- [ ] **Stop counting this as a control.** It is currently decorative
- [ ] Decide whether to make it real (a retrieval-time contradiction check is a project,
      not a prompt tweak) or drop the claim. Removing the contradictions from the KB is
      the cheap path and is already underway

### P1.5 Prompt scaffold leak — root cause still unfixed
`stripTrailingScaffold()` catches the symptom client-side. The prompt still contains the
literal `MANDATORY OUTPUT — append this after every answer:`, which reads like a heading
the model is meant to emit, which is why it sometimes emits it. Deferred while the UPS
was undersized; **that block is gone.**

- [ ] Reword to an instruction rather than a template heading (draft ready)
- [ ] Keep the client strip regardless — defence in depth
- [ ] Changes `PROMPT_VERSION`, so it needs a graded-eval re-baseline (now affordable)

### P1.6 Product name mangled
Answers said **"SAP One"**; the KB says "SAP Business One" six times and never "SAP One".
A generation-side abbreviation, not a KB error. Low severity, but it is a client's product
name on a portfolio.

- [ ] Add to the golden set with an `expect_substrings` of "SAP Business One" so it is
      measured rather than remembered

---

## P2 — Ops gaps found auditing the ledger against the boxes

### P2.1 Backups and the weekly digest have never run — **highest ops risk**
`verdicts.db` is 1.66 MB and modified today. There is **exactly one** backup, dated
**2026-08-06**, 27 days stale. The asrock has **no cron daemon at all** — `cronie` and
`dcron` both absent, root crontab and `/etc/cron.d` empty, no VPS timer covering it. So
that single backup was the manual run that created it, and `weekly_verifier_digest.sh` has
never run either.

- [ ] Install a periodic-job mechanism on the asrock (**a change to a box not otherwise in
      scope — needs authorization**)
- [ ] Schedule the backup and the digest
- [ ] **Verify by checking the directory a day later**, not by checking that the crontab
      line exists. An unverified schedule is a belief, not a control

### P2.2 UPS: no automatic shutdown
Battery runtime exists; graceful shutdown does not. `lsusb` shows no UPS, neither NUT nor
apcupsd installed. Staged in `home/ups-shutdown/`.

- [ ] Plug in the USB cable (**physical, Chris**)
- [ ] `emerge sys-power/nut`; T5810 as `upsd` + `upsmon` master, asrock as slave
- [ ] Shutdown order: `vllm-qwen38` **as a service** (TP workers orphan holding ~19 GB
      VRAM each), then `qdrant`, then halt
- [ ] **Pull the plug on purpose, once.** An untested shutdown path is a belief
- [ ] Meter the two boxes separately with the second KP125M — the 642 W split between them
      is still unknown, and that ambiguity already caused one wrong conclusion

### P2.3 Alert delivery unverified
The critical/heartbeat topic split shipped. Whether the critical topic reaches a device
that actually notifies has never been tested end to end. The original failure was not
detection and not routing — it was that a page nobody sees is the same as no page.

- [ ] Send a test page to the critical topic and confirm it arrives on the phone (**Chris**)

### P2.4 `reindex_kb.sh` does not update the About-panel counts
Confirmed: the script never touches `KB_DOC_COUNT` / `KB_CHUNK_COUNT` in
`/etc/systemd/system/api-proxy.service.d/system-info.conf`. They match today (99) by
coincidence of having been set by hand. The next reindex will silently drift them.

- [ ] Either have the indexer write the counts, or have `/api/system-info` read them live
      from Qdrant. **Reading live is better** — it cannot drift

### P2.5 Verdict window is a 25 s stopgap (ledger #3)
Mean judge latency 16.6 s, max 56.6 s observed cold. Verdicts past 25 s are dropped
silently.

- [ ] Either raise the window, or accept and **log the drop** so silent loss becomes
      visible. Currently it is invisible, which is the actual defect

---

## P3 — Cannot be fully fixed; mitigate and be honest

### P3.1 Premise inheritance across turns
A wrong fact in turn 1 generated follow-up chips *about* the wrong fact, and the model
answered inside that frame. Worst case observed: asked the context window of a model that
does not exist, it replied *"The knowledge base does not specify..."* — **the grounding
refusal corroborating the false premise.** "We don't have that detail about the 7B
verifier" reads as confirmation that a 7B verifier exists.

Nothing re-checks a follow-up's presupposition against retrieval, and the chips are
generated from the previous answer, so the conversation cannot self-correct.

**Not fixable by editing.** Options, none cheap:
- [ ] Consider generating chips from the *retrieved chunks* rather than the answer, so a
      wrong answer cannot spawn questions about things not in the corpus
- [ ] Accept, and rely on getting turn 1 right — which is what P0.1 and P1.x are for

### P3.2 Faithfulness is not correctness
The verifier scores whether claims match the retrieved chunks. **An error in the chunks
scores as grounded** — exactly what happened with the AVD arithmetic. No control in this
system catches a KB that is wrong.

- [ ] State this limit plainly in the docs rather than implying the verifier is a
      correctness check
- [ ] The only real defence is periodic KB audits against source truth. Treat P0.4's sweep
      as the first one

---

## Sequencing

1. **Finish the KB batch** — P0.1 (done), P0.4, P1.1, P1.2, P1.3
2. **One reindex**, then verify P0.1 across several phrasings *before* anything else
3. **Deploy** the two code fixes (P0.2, P0.3)
4. **Add golden-set entries** for every specific failure above, so they are regression-gated
   rather than remembered — the entries are the durable part of this plan
5. **Graded eval** as the gate; compare against the 4.59 baseline measured 2026-09-01
6. **Then** P1.5 (prompt reword) as its own change with its own re-baseline, since it moves
   `PROMPT_VERSION`
7. Ops items P2.x on their own track — they need physical access and box changes

**Do not batch 3 and 6.** The prompt reword changes every answer; deploying it together
with the router and parser fixes would make a bad eval result ambiguous.
