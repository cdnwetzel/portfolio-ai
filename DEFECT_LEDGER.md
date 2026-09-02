# Defect Ledger

**Purpose:** Track known defects and regressions discovered during development.  
**This is the source of truth for continuous improvement priorities.**  
**Policy:** Once fixed, move to CLOSED section with date and commit hash.

---

## OPEN DEFECTS (Priority Order)

### 14. A Changelog Chunk Reads as Current Inventory — KB FIXED 2026-09-02, NEEDS REINDEX
**Status:** KB corrected in git; **NOT live until `./scripts/reindex_kb.sh` runs**
**Severity:** HIGH for a portfolio site — it advertises hardware that does not exist
**Found by:** Chris, live query "What has Chris built?", 2026-09-02

**Symptom.** The answer listed the system's models as *"Qwen2.5-14B-Instruct (on RTX 5060
16 GB), Qwen2.5-7B (on RTX 3060 Ti), and Qwen3.8-27B-FP8"* — presenting a **retired GPU and a
retired model as current hardware**, alongside a stale "35-question golden-set eval (mean
grounding 4.48/5)".

**The model did not hallucinate any of it.** Every element traced to
`knowledge_base/infrastructure/current_work_2026.md`, which is written as a *changelog*:

> "the out-of-band faithfulness judge moved **from Qwen2.5-7B (RTX 3060 Ti) to**
> Qwen2.5-14B-Instruct on a new RTX 5060 Ti 16 GB"

Retrieval worked perfectly. The corpus was the problem.

**Root cause — worth generalizing.** *A "moved from A to B" sentence, retrieved as a chunk
without its framing, reads as "the system has A and B."* Chunking strips the narrative
context that made the tense unambiguous, so the "from" side of every migration becomes a
present-tense fact. Any KB doc written as a history log carries this hazard on **every**
transition sentence it contains.

This is a corpus-shape defect, and it is the *inverse* of the surface-form heuristic family
(#5, #6, DEFECT #13): there the code was too clever about a question's form; here the KB is
insufficiently explicit about a statement's tense.

**Also stale in the same doc, and corrected:**

| Claim | Was | Now |
|---|---|---|
| WebSocket rate limit | "1 concurrent connection per IP" | **2** (`api-proxy.py:198`) — 1 is the bug from #7 that surfaced as "Connection lost" |
| Golden set | 35 questions, mean grounding 4.48/5 | **42 questions, 4.59/5** measured 2026-09-01 |
| Time-to-first-token | ~5.6 s | **1-2 s** on the current Qwen3.8-27B config |

**Resolution applied to the KB:**
1. A **"What is running RIGHT NOW"** section at the top of the doc, stating the complete GPU
   inventory positively — two A4500s and one 5060 Ti — before any history appears.
2. The changelog section explicitly labelled as history, with retired items named as retired
   *in the same sentence* so a chunk cannot lose the framing.
3. The stale numbers corrected, each pointing at what superseded it and why.

Note the phrasing follows the lesson from the earlier "there is no 14B reranker" mistake:
**lead with the positive fact, and let the negation only clarify it** — never ship a bare
negation into the KB.

**Not yet verified, and this is the part that matters:** per this repo's own rule, *"add it to
the KB" is not a fix — verify it retrieves.* Requires `./scripts/reindex_kb.sh`
(**authorization needed**), then re-asking several phrasings — "what has Chris built", "what
models run this system", "what GPUs does this use" — and confirming no 3060 Ti or 7B appears.

### 1. SAP Business One — RETITLED 2026-09-02: hallucination is gone, a 5/4 conflation remains
**Status:** OPEN but **downgraded HIGH → LOW**. The original premise no longer holds.
**Original claim (2026-07-28):** "response invents non-KB details", "speculative fluff"
instead of using the rank-1 chunk.

**Re-verified live 2026-09-02** against the current model (Qwen3.8-27B, not the 14B that was
serving when this was written). Every distinctive specific in the answer traces to
`knowledge_base/case_studies/sap_business_one_integration.md`:

| Claim in the answer | In the KB? |
|---|---|
| `idx_inventory_warehouse_sku`, `idx_wmssync_status` | yes — verbatim |
| Athens / Singapore / Sydney / Produmex | yes |
| "8 months" timeline | yes, line 12 |
| "8s to 0.8s (10x)" | yes, line 77 |
| "99%+ inventory accuracy" | yes, line 15 |
| "200+ users" | yes |

**The model is now using the chunk, not inventing around it.** Two graded evals the same
night scored it g=4 / faithfulness=5 in both arms.

**What actually remains, and it is small:** the opening sentence says the company operates
"across five continents". The KB says **5 warehouses spanning 4 continents** — the answer
conflates the two, then *contradicts itself* two lines later with the correct "5 warehouses
across 4 continents". A number-swap in a summary sentence, not fabrication.

**Note on the judge's read:** it scored g=4 with "lacks specific details from case study" on
an answer dense with case-study specifics. The judge only sees the chunks handed to it, so an
answer drawing on a chunk outside that evidence slice gets under-scored. Worth remembering
before trusting a single judge note over the source text.

**Fix required:** nothing urgent. If touched, the lever is the case study's own summary line,
not the prompt — line 5 pairs "5 warehouses" and "4 continents" in one sentence, which is
exactly the shape that invites the conflation.
**Discovered by:** Kimi (2026-07-28). **Re-verified and downgraded by:** Claude, 2026-09-02.

### 3. Verdict Window: Silent Drop Risk
**Status:** STOPGAP FIX  
**Severity:** MEDIUM (silent data loss if judge latency grows)  
**Discovery:** During Tier 2 deployment (2026-07-29)  
**Issue:** `VERDICT_WINDOW_MS = 25000` (25s) is a hardcoded timeout for receiving judge verdicts  
**Risk:** If judge latency grows beyond 25s (e.g., asrock under load, cold load stack up), verdicts silently drop  
**Current latency:** Mean 16.6s (n=10), max 56.6s (cold load). Room exists, but not guaranteed.  
**Fix required:**
- [ ] Option A (easy): Raise VERDICT_WINDOW_MS to 30–35s (temporary)
- [ ] Option B (right): Late-arriving verdict redesign (2.4 Option B from Kimi's earlier plan)
  - Instead of closing socket after 25s, accept verdicts that arrive up to N seconds after done message
  - UI shows "checking..." → "verdict received" (late patch) instead of no verdict

**Discovered by:** Kimi (Tier 2, noted as stopgap)  
**Last reviewed:** 2026-08-05 (accepted as stopgap during deployment rush)

---

### 4. Verdicts.db Backups and the Weekly Digest Never Run — CONFIRMED WORSE 2026-09-02
**Status:** OPEN. **Severity raised** — this is not "no backup configured", it is "configured
and silently never executing", which is worse because it reads as done.

**Measured on the asrock 2026-09-02:**

| | |
|---|---|
| live DB | `/home/chris/verifier/verdicts.db`, 1.66 MB, mtime today |
| backups directory | `/home/chris/verifier/backups/` |
| backups in it | **exactly one**, `verdicts-20260806T011520Z.db`, **2026-08-06** — 27 days stale |
| **cron daemon on the asrock** | **none installed** (`cronie` and `dcron` both absent) |
| root crontab / `/etc/cron.d` entries | none |
| VPS timers or cron for either job | none |

So the single backup was a manual run the day it was set up, and nothing has run since.
`weekly_verifier_digest.sh` sits next to the DB and is **also** unscheduled — so the
"weekly digest with silence alerts" is not running either.

**This makes two claims in CLAUDE.md overstated.** Tier 7 is described as complete with
"verdicts.db backups, weekly digest with silence alerts". Neither is scheduled anywhere.

**Fix required:**
- [ ] Install a cron daemon on the asrock (or an OpenRC-friendly timer) — there is currently
      no mechanism to run *any* periodic job on that box
- [ ] Schedule the backup, and **verify by checking the directory a day later**, not by
      checking that the crontab line exists
- [ ] Schedule `weekly_verifier_digest.sh` likewise
- [ ] Correct the Tier 7 claim in CLAUDE.md

**Same shape as the outages this repo already learned from:** a thing that looks configured,
fails silently, and is believed because a document says so. An unverified schedule is a
belief, not a control.
**Discovered by:** Claude, 2026-09-02, checking the ledger's own open items on the box.

### 8. Alert delivery, not alert generation
**Status:** OPEN — **code side done, the remaining step is human verification**
**Severity:** HIGH — this is why a two-day outage went unnoticed
**Issue:** the monitor did its job. It detected the 2026-08-26 vLLM outage and paged
`[urgent] Portfolio AI DOWN — outage signature` on **Aug 27 and Aug 28**. Nothing happened.
**Cause:** the routine daily heartbeat landed on the **same ntfy topic** as urgent pages. A
channel that pings you daily with "all green" trains you to ignore it, so the one message
that mattered looked like the ninety that didn't.

**Shipped 2026-08-31:** severity separated onto two topics — `NTFY_CRITICAL_URL`
(`cwdotcom-critical-…`) carries DOWN/recovered transitions only, while the daily heartbeat
stays on `NTFY_URL`. The critical topic is silent unless something is wrong, which is the
whole point of it.

**Still open, and it is not a code task:** *confirm the critical topic actually reaches a
device that notifies you.* Delivery has never been verified end to end on a phone. Until it
has, this defect is not closed — the original failure was not detection and not routing, it
was that a page nobody sees is the same as no page.

**Do not** respond to this by adding more probes. Detection is not the failure.
**Discovered by:** Claude (2026-08-31, correcting an earlier wrong claim in this ledger that
monitoring was blind)

---

## CLOSED DEFECTS

### 2. Judge Timeout Wrapper: Infrastructure Debt — CLOSED 2026-09-02 (verified on the box)
**Was:** the judge's timeout handling lived in a wrapper script under `/tmp` — critical-path
behaviour in a directory that does not survive a reboot.
**Verified resolved:** `/etc/init.d/verifier-service` runs
`/home/chris/miniforge3/bin/python3 /opt/verifier-service/verifier.py` directly — no wrapper,
nothing in `/tmp`. The timeout is a first-class setting in the service code
(`JUDGE_TIMEOUT`, default 120 s, `verifier.py:72`), applied to the httpx client at
`verifier.py:155`. The unit is supervised with `respawn_max=0` and an `output_log`.
**Checked by:** Claude, 2026-09-02, reading the live unit and source rather than the docs.

### 13. Eval Harness Cried Wolf About Judge Independence — CLOSED 2026-09-01
**Was:** every graded-eval run printed
`⚠ WARNING: judge model looks like the 14B answerer — echo bias. Use a DIFFERENT model.`
The check was `"14b" in judge_model`, which was correct only while the answerer actually
**was** Qwen2.5-Coder-14B. Since the generator moved to **Qwen3.8-27B-FP8**, the 14B-Instruct
judge is genuinely independent — so the warning fired on every run and was always wrong.

**Why it is worth a ledger entry rather than a shrug:** this is the *fifth* instance of the
house pattern — **a heuristic keyed on a surface form that silently goes stale.** The others
were the router default, the "favorite language" rule, the education retrieval miss, and
`max_tokens` set by question word count. It also has a second cost specific to warnings: a
warning that cannot be acted on trains the operator to ignore warnings, so the next one — a
*real* echo-bias run — reads exactly like the noise.

It never corrupted a score. The judge was independent throughout; only the harness was wrong
about it.

**Resolution:** `judge_echo_risk()` now compares the judge against the **actual served
model**, read live from the proxy's `/api/system-info` (which reports the server-pinned
`MODEL_ID`), instead of a hardcoded string. Models are swapped behind labrouter without the
VPS changing, so reading the served model is the only version of this check that stays true
across a model change. It **fails closed**: if `/api/system-info` cannot be read, it warns
that independence is UNVERIFIED rather than staying silent.

Five cases tested, deliberately including the historical one — a 14B judge against a 14B
answerer must *still* warn, so the fix tightens the check rather than deleting it — and the
unknown-answerer case. On a clean run it now prints the positive confirmation
`judge ... vs answerer ... — independent, no echo-bias risk`, which is worth more than
silence: it shows the check ran.
**Discovered by:** Claude, 2026-09-01, while re-baselining the graded eval after the UPS
replacement unblocked sustained GPU load.



### 11. Answers Appeared Cut Off — Prompt Scaffold Leak — CLOSED 2026-09-01
**Was:** answers ended with a dangling `**Mandatory`, reading as truncation.
**It was not truncation** — the reply was 838 tokens against a 2048 cap. The model
sometimes reproduces the system prompt's own `MANDATORY OUTPUT — append this after every
answer:` heading immediately before the FOLLOWUPS block. The client strips from
`FOLLOWUPS:` onward, so anything the model wrote *before* that marker survived into the
visible answer. Also a small prompt leak: internal instruction text reaching a visitor.
**Resolution:** `stripTrailingScaffold()` in `useChat.js`, applied on both the
FOLLOWUPS and no-FOLLOWUPS paths. Deliberately conservative — a trailing line is dropped
only if it lacks terminal punctuation AND is either pure markdown decoration or carries
scaffold wording. A real closing sentence always ends in punctuation and is never touched.
Six cases tested including "must keep" negatives.
**Not fixed at the prompt level on purpose (at the time):** rewording `SYSTEM_PREFIX`
changes `PROMPT_VERSION` and needs a graded-eval re-baseline, which costs sustained GPU
the box could not spend while on an undersized UPS.

**UNBLOCKED 2026-09-01** — the UPS is replaced and sustained eval load is affordable
again. The client-side strip stays regardless (defence in depth: the model can echo
scaffold wording no prompt edit fully prevents), but the root cause is worth removing:
the literal string `MANDATORY OUTPUT — append this after every answer:` reads like a
header the model is *supposed* to emit, which is precisely why it sometimes emits it.
Phrasing the same requirement as an instruction rather than a shouty template heading
deletes the string the model was copying. Requires a deploy + re-baseline, so it is a
proposal, not a silent change.

### 12. Proxy Finished Generations Nobody Was Waiting For — CLOSED 2026-09-01
**Was:** 1,456 log lines in 24 h of `Cannot call "send" once a close message has been
sent`. When a visitor pressed Stop, hit New chat, or navigated away, the send failed, the
error was logged, **and the loop continued** — so the proxy kept pulling tokens from vLLM
and the GPUs kept generating an answer that could never be delivered.
**Why it mattered more than the log noise:** on a box with a ~2-3 % duty cycle that
exceeds its UPS during every burst, finishing abandoned work is real waste — it extends
exactly the window in which an outage would cause corruption.
**Resolution:** a `ClientGone` exception raised from the chunk loop, which exits the
`async with _http.stream(...)` block and closes the upstream connection so vLLM stops.
The caller skips the `done` frame and the verifier (judging an undelivered answer wastes
the judge's GPU too) and leaves the receive loop, which releases the IP's rate-limit slot
— important, because holding it would 429 the visitor's next question as
"Connection lost" (defect #7).
**Detector tested** against the real Starlette strings and against genuine failures
("Connection reset by peer", "vLLM HTTP 500") so a broad match cannot silently
reclassify a real error as a user leaving.

### 7. labrouter Was Not Supervised — CLOSED 2026-08-31
**Was:** `/etc/init.d/labrouter` set `command_background="yes"` with **no `supervisor=` line**,
so start-stop-daemon launched uvicorn and then nothing watched it — the process ran as PPID 1
and `respawn_max=5` was inert. labrouter is the front door for cwdotcom: the VPS tunnel forwards
`:8004` and nothing else routes that traffic, so a crash meant generation stopped with no
recovery. The most externally visible component in the lab had the weakest supervision.
**Resolution:** `supervisor="supervise-daemon"`, `respawn_max=0`, `respawn_delay=15`. Also found
that `restart_delay` was never a supervise-daemon key — the correct name is `respawn_delay`, so
the old backoff did nothing even in intent.
**Second fix, easy to miss:** under supervise-daemon the pidfile holds the SUPERVISOR's pid, not
uvicorn's, so the existing `reload()` (`start-stop-daemon --signal HUP --pidfile`) would have
SIGHUPed the wrong process and silently done nothing. `reload()` now resolves the child by
parentage. Same trap that made an earlier respawn test kill a supervisor instead of its child.
**Verified by test:** SIGKILL the child → respawned and healthy in ~20 s; `rc-service labrouter
reload` reaches the child and the service stays up; live site returns 5 sources streaming
(`ttft_ms=1928`); aggregator 7/7 green including E2E.
**Where it lives:** `/etc/init.d/labrouter` on the T5810 — the lab lane, NOT this repo. It is
deliberately not vendored here; a copy would drift, which is the failure mode this week's doc
work exists to stop. Backup: `/root/init.d-labrouter.bak-20260831`.

### 9. Answers Truncated Mid-Word — CLOSED 2026-08-31 (b6efc2e)
**Was:** `estimate_answer_length()` scaled the generation cap by the QUESTION's word count
(≤5 words → 256 tokens). "What has Chris built?" is four words, so the most important question
a visitor can ask was cut off mid-word at ~279 tokens.
**Root cause was the premise, not the thresholds.** Its goal was "short questions get short
answers to avoid verbose responses", but `max_tokens` does not make a model concise — it makes
it stop mid-sentence. Brevity is a prompt concern; the cap only decides where the cut lands.
**Resolution:** flat `DEFAULT_ANSWER_TOKENS=2048`. Verified live: the same question now
returns 569 tokens ending cleanly, while "What GPU?" self-terminates at 192 — proving a
generous cap costs nothing, because the model stops on its own.
**Lesson — third instance this week of one pattern:** a heuristic keyed on *surface form*,
silently wrong on the highest-value input. See also #6 (router default deflecting a third of
the golden set) and #5 (favourite-language). When a rule keys on question shape rather than
meaning, test it against the questions that matter most.

### 10. Supervision Gaps Across the Fleet — CLOSED 2026-08-31 (1c3fc6e, and 2026-08-30)
**Was:** four incidents in one week shared a root cause — critical-path processes that nothing
supervised, failing silently. vLLM ran unsupervised from a **deleted** installation for four
days; the reranker was stopped and retrieval silently degraded to cosine; `embed-service` and
`verifier-service` both carried `respawn_max=5` and wrote **no logs**.
**Why `respawn_max=N` is wrong here:** it does not "give up gracefully", it latches the service
OFF permanently after a transient squeeze. qdrant hit this (its unit still records
"respawn_max exceeded → service latched off"), then rerank-service, then these two. Fixed in
isolation each time; the lesson never propagated.
**Resolution:** `respawn_max=0` + `output_log`/`error_log` on embed, verifier, rerank and the
new `vllm-qwen38` unit. vLLM additionally needed an **orphan reaper**: its TP workers are
separate processes that survive a SIGKILL of the API server and hold ~19 GB VRAM each, so every
respawn found a full card and refused — the service supervised itself into a permanent outage.
Proven by SIGKILL → self-heal in 225 s.
**Still open:** labrouter (#7).

### 5. "Favorite Language" Answers Neither Way — CLOSED 2026-08-29 (0cf8af1)
**Was:** `"What is Chris's favorite programming language?"` scored g=1, "neither cleanly
refused nor substantive". The 2026-08-19 entry guessed at two causes and named the wrong
one first — it supposed a KB gap. There was no gap.
**Actual root cause (found 2026-08-29 when the answer got worse, not better):** the fact
was present AND indexed but **unrankable**. `"Favorite languages: Python and SQL"` sat at
`RESUME.md:49` inside the "Automation & Scripting" list, so the chunk's dominant topic was
tooling. For the natural phrasing the resume did not appear in the top-5 at all (best
score 0.0587, all unrelated docs) and the model lifted **"Bash"** from a tangential
sysadmin chunk and asserted it as a preference — Bash IS in the KB, as a scripting tool.
So between 08-19 and 08-29 this silently escalated from waffling to confidently wrong.
**Fix:** a Preferences section high in `RESUME.md` (placed AFTER Education so as not to
displace that fix) + a `favorite/favourite/preferred/prefers/preference/go-to` alias
group. Retrieval: absent from top-5 → **rank 1 at 0.9591**.
**Verification:** graded eval `[ok] refuse_ok g=3` (was `[FAIL] g=1`); consistency battery
probe 5/5 forbidding "favorite … is bash/powershell".
**Lesson — third instance of one pattern.** Education, T5810 storage, and now this: the
fact was in the KB every time, and every time the failure was that it could not rank.
"Add it to the KB" is not a fix; **verify it retrieves for the phrasing users actually
type.** Section placement within a merged chunk is a retrieval lever, not cosmetics.

### 6. WATCH: Grounding 4.80 → 4.70 — CLOSED 2026-08-29, SUPERSEDED
Never resolved on its own terms and no longer resolvable: the model changed underneath it,
voiding both numbers. The watch item asked whether 4.70 was noise or a chunk-boundary
effect; the new baseline is 4.78 with zero review warnings, so whatever it was is not
present now. Do not re-open — re-measure against the baseline above instead.

### 6. Router Default Deflected a Third of the Golden Set — CLOSED 2026-08-19 (4565c8b)
**Severity:** HIGH (user-facing; the site refused to describe the person it exists to describe)
**Issue:** `classify_query()` defaulted to `off_topic`, making the router a grounding gate it
could never be — the on-topic keyword list had no entry for "chris", so
`"what can you tell me about chris"` got a canned redirect. **13 of 40 golden-set `grounded`
questions classified off_topic**, including "Summarize Chris's professional background" and
"How can I contact Chris professionally?".
**Why it went unseen:** `compare_retrieval.py` (the source of the "20/20" figure in CLAUDE.md)
measures retrieval only and never invokes the router. `eval_graded.py` asks via `/ws/chat` but
grades evidence via `/api/retrieve`, so the router's deflection never showed as a retrieval miss.
**Resolution:** Default is now `on_topic`; redirects come from an explicit off-topic list.
Grounding stays on api-proxy's `RAG_MIN_SCORE` guardrail, where it always belonged. Adversarial
probes remain caught upstream by `is_prompt_extraction` (verified). Added `tests/test_query_router.py`
— the module had no test coverage at all.
**Verification:** graded eval 30 grounded / mean 4.80 (baseline 4.82), 0 safety hard-fails,
0 transport errors; self-test 3/3.
**Lesson:** a retrieval-level metric cannot see a routing-level bug. The "20/20" number was
true and irrelevant. Measure the path the user actually takes.

### 7. Verdict Window 429'd the User's Own Next Turn — CLOSED 2026-08-19 (4565c8b)
**Severity:** HIGH (presented as "Connection lost" with the question silently unanswered)
**Issue:** The client armed `VERDICT_WINDOW_MS` (25s) after every `done` to await a faithfulness
verdict. Four paths (guardrail, meta, off-topic, not-documented) never run the verifier, and
`should_verify()` gating skips others — so the socket was held the full window for a verdict that
could never arrive. `ConnectionRateLimiter(max_concurrent_per_ip=1)` then rejected the user's own
follow-up with a 429 **before `accept()`**, which the browser surfaces as an opaque close (1006).
**Presentation:** intermittent and typing-speed dependent — read the answer slowly and the next
turn works; fire off two questions quickly and both vanish. This misdirected diagnosis toward an
"empty-retrieval branch that crashes," which does not exist.
**Evidence:** 8 logged `rate limit: rejected duplicate /ws/chat connection` entries from a single
IP, clustered in bursts seconds apart, matching every observed failure 1:1.
**Resolution:** `done` now carries `verify`; the client only waits when a verdict is actually
coming, and closes a superseded socket before opening the next. Limiter raised to 2 to absorb
handoff overlap (still trips a scripted loop immediately).
**Verification:** scripted repro of all three failing pairs — including holding the first socket
open exactly as the old client did — passes; 0 rejections and 0 errors post-deploy.
**Lesson:** a client that waits for a message the server may never send needs the server to say
so. Relates to open defect #3 (verdict window), which this partially de-risks.

### 8. Canned Paths Were Dead Ends — CLOSED 2026-08-19 (4565c8b)
**Severity:** MEDIUM (worst-case first impression for a new visitor)
**Issue:** Every canned path returned a refusal with nothing to click. Suggestion chips are parsed
from a `FOLLOWUPS` block in the answer, and the canned strings had none — so a visitor asking
"what can I ask?" was told no and handed a blank slate.
**Also:** `meta_keywords` lacked "what do you know" / "what am I supposed to do", so visitors asking
the chat for help were told they were off-topic.
**Resolution:** All three canned responses carry a `FOLLOWUPS` block (no client change needed —
the existing parser renders them), with chips spanning distinct corpus domains rather than three
flavours of the same question. Meta keyword list extended.
**Credit:** the "the answer to 'what can I ask?' is in the doc titles" framing came from a parallel
CC session; its causal diagnosis was wrong but the product instinct was right.

### 1. SAP Business One: Generation Hallucination — CLOSED 2026-08-06
**Resolution:** Fixed incidentally by the Tier 4 persona prompt rewrite (commit 5586ad5).
**Verification (Kimi, 2026-08-06):** Two consecutive live queries returned grounded answers
(Produmex WMS, multi-region specifics from the case study); zero rule-#6 speculation markers
("likely", "could include", "not provided"). Deterministic pre-Tier-4, absent post-Tier-4.
**Lesson:** the defect sat unowned for 9 days (T2.3 → convergence doc) — the ledger exists
so that doesn't happen again.

### 5. Verifier Wiring Outage (VERIFIER_HOST + VERIFIER_URL) — CLOSED 2026-08-06
**Severity:** HIGH while live — the verifier was dark ~4 days with zero verdicts recorded
(last row 2026-08-01 18:00), and nothing alerted.
**Root cause (two breaks, both from runbook-era redeploys):**
1. `/etc/default/portfolio-ai-tunnel` (VPS) had no `VERIFIER_HOST` — the tunnel unit's
   `-L 127.0.0.1:8007:${VERIFIER_HOST}:8007` expanded empty; 8007 listened but dead-ended.
2. No systemd drop-in set `VERIFIER_URL` for api-proxy — `_fire_verify` no-ops without it.
**Fix (Kimi, 2026-08-06):** added `VERIFIER_HOST=10.0.1.115` (env file backed up first),
restarted tunnel — 8007 health OK; added `api-proxy.service.d/verifier.conf` with
`VERIFIER_URL=http://127.0.0.1:8007`, restarted proxy. E2E proof: live chat → verdict row
with request_id landed in verdicts.db (faithfulness 1.0, latency 22.2s).
**Lesson:** redeploys must preserve out-of-repo config. The tunnel env file and the proxy
drop-ins are invisible to git — DEPLOYMENT.md now lists them as required state to verify.
Also: "zero verdicts in N days" should itself be an alert condition (Tier 7 candidate).

---

## HOW THIS LEDGER DRIVES CONTINUOUS IMPROVEMENT

### Weekly Flagged-Queue Review (15 minutes)
1. Query verdicts.db for answers flagged by the 14B judge in the last 7 days
2. Pick the 5–10 worst offenders (lowest confidence or most content-free)
3. For each: decide
   - **KB gap:** Missing or wrong doc → queue for Tier 6 KB expansion
   - **Prompt gap:** System prompt rule violated → adjust prompt or fine-grain chunk
   - **Judge error:** Judge is wrong → document as false positive for future eval calibration

4. Log decision and move on

### Monthly Ops Review (1 hour, includes this ledger)
1. Review open defects above
2. Check if any are resolved (move to CLOSED with date/commit)
3. If defect is aging >2 weeks without action: escalate priority or document decision to defer
4. Add any new defects discovered during the month

### Example: SAP Defect Closure
```
// Week 1: Flagged-queue review discovers SAP query returned speculative text
// Week 2: Investigation finds chunk IS being passed; model is just ignoring grounding rule
// Action: Strengthen system prompt clause #6 (grounding requirement)
// Test: Run SAP query in prod, verify response uses the rank-1 chunk
// Commit: "fix: strengthen grounding clause for SAP Business One answers"
// Ledger update: Move SAP to CLOSED, cite commit hash, log lesson learned
```

---

## Privacy Note (Red-line #2 Compliance)

This ledger is safe because:
- ✅ No query content stored (only verdict metadata)
- ✅ Defects are categorized (KB gap, prompt gap, judge error) without text details
- ✅ Learning happens through verdict scores, not query logs
- ✅ If a defect needs examples, they come from the golden set (curated, stable), not production queries

This is why "mine query logs for trends" doesn't work here — and why the verifier's flagged-queue review is the real loop that's both legal and effective.

---

**Last Updated:** 2026-09-01  
**Owner:** Claude (reviews weekly), Kimi (discovers during tests)  
**Next Review:** 2026-08-26 (weekly flagged-queue)  
**Next Full Review:** 2026-09-05 (monthly ops review)
