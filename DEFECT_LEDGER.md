# Defect Ledger

**Purpose:** Track known defects and regressions discovered during development.  
**This is the source of truth for continuous improvement priorities.**  
**Policy:** Once fixed, move to CLOSED section with date and commit hash.

---

## OPEN DEFECTS (Priority Order)

### 1. SAP Business One: Generation Hallucination
**Status:** LIVE IN PRODUCTION  
**Severity:** HIGH (violates prompt rule #6 — generation must be grounded)  
**Discovery:** Tier 2.3 golden-set eval (2026-07-28); flagged by 14B judge  
**Evidence:** Rank-1 chunk has correct answer; model generates speculative fluff instead of using it  
**Symptom:** Query "Tell me about Chris's SAP Business One work" → response invents non-KB details  
**Root cause:** Model is speculative despite system prompt grounding rule  
**Fix required:** 
- [ ] Verify with live query (test in prod)
- [ ] Check if chunk is being passed to LLM (context fitting issue?) or LLM is ignoring it
- [ ] Adjust system prompt strictness OR fine-grain the chunk content

**Discovered by:** Kimi (noted in T2.3, then disappeared into STATUS)  
**Last reviewed:** 2026-08-05 (flagged in verdicts.db, not yet acted on)  
**Evidence + candidate fix (2026-08-10):** Grounded A/B measured pscode at 0.71 mean faithfulness (2/4
flagged) vs qwen3-coder:30b at 0.97 (0/4 flagged) on the same retrieved sources; the 30B removes the
"Mac Studio T5810" style confabulation entirely. Model swap is GREEN on quality but BLOCKED on GPU
capacity. See `plans/model-faithfulness-ab-qwen3-30b-2026-08.md`.

**Reproduced live 2026-08-19 with a clean isolation, two independent cases:**

*Case A — contradicts retrieved evidence.* `"tell me about the Asrock B550"` returned a generic
motherboard spec sheet under "Sources (5)": invented a *Realtek ALC892 audio codec*, *128 GB DDR4 at
5600 MHz*, and *"Realtek Gigabit Ethernet"* — while `gentoo_machines.md:26` states **Intel AX200 WiFi,
I225-V 2.5GbE**. Not a KB gap; a direct contradiction of retrieved text. The same session also had it
claim the T5810 has *"Integrated Intel HD Graphics"*, contradicting both the KB and its own answer two
turns earlier.

*Case B — the isolation that rules out retrieval.* `"does the T5810 have onboard storage?"` answered
*"does not have onboard storage. It relies on external storage solutions."* `/api/retrieve` for that
exact query returns the corrected chunk at **rank 3**, containing the literal sentence *"Yes, the
T5810 has onboard storage — internal drives inside the workstation chassis."* **Evidence was in
context and the model asserted its negation.** This is the cleanest available proof that the defect
is generation, not retrieval or KB coverage.

*Also learned:* the KB previously said *"the A4500 has no onboard storage"* (true, about the GPU) and
the model attributed it to the workstation. Rewording fixed 4 of 5 phrasings. The first attempt
*quoted* the wrong phrase in order to warn against it — and the model pattern-matched the quoted
string, reproducing the error. **Never write a wrong phrasing into the KB even to negate it;**
retrieval matches the phrase, not the logic. Fixed by stating the positive fact only.

*Verifier note — CORRECTED 2026-08-19:* an earlier draft of this entry claimed the judge misses this
class, inferred from the absence of a flag in the browser. That was wrong. Re-running the ASRock
question through `/verify` directly, the judge **did** flag it (`flagged=True, n_contradicted=1`,
faithfulness 0.92). So the judge detects the contradiction; what failed was flag *delivery or display*
in the client. Investigate that separately — do not treat this as judge blindness.

**Model configuration finding (2026-08-19) — production has never used the pscode LoRA.**
`/v1/models` shows `qwen2.5-coder-14b-pscode` with `parent=None` and
`root=/data/pscode/models/qwen2.5-coder-14b-instruct` (the base), and `pscode-prod` as a separate id
with `parent=qwen2.5-coder-14b-pscode` (the adapter). `useChat.js` sends the base id and the proxy
does not override it. **Consequence:** the "pscode 0.71" arm of the qwen3-30B A/B was the *base*
model, mislabeled, and `pscode-prod` has never been evaluated at any point.

*First measurement of the adapter (n=5, identical chunks/prompt/sampling, scored by the site's own
judge):* base mean 0.983 with 1 flag; LoRA mean **1.000 with 0 flags**, and far more disciplined
output (pxx answer 881 chars vs the base's 4079). **Not yet actionable** — 9 of 10 cells scored
exactly 1.00, so the whole difference is one data point, and the base answered the T5810 storage
question *correctly* here while getting it *wrong* in production an hour before on the same chunks,
prompt and sampling. **The defect is stochastic at temperature 0.2**, so single-sample comparisons
cannot resolve it. Next step: k≥5 samples per question per arm, and a temperature-0 arm, before any
serving change. Harness: `scratchpad/lora_ab.py` (runs on the VPS; no restart, live site unaffected).

*Two more live instances (2026-08-22), reported by Chris:*
- **Age confabulation.** `"how old is Chris"` → *"Chris Wetzel is 26 years old."* The KB has no age
  statement anywhere; the model pattern-matched the corpus's ubiquitous "26 years of experience"
  onto the age attribute. The verifier DID flag it, but the flag is advisory — the wrong answer
  still rendered. **Fix:** `server_facts_block()` (context_manager.py) computes age from
  `OWNER_BIRTHDATE` at request time and injects it into the system prompt as a SERVER FACTS block
  (DOB never reaches the prompt, client, or logs — only the computed age); a GROUNDING bullet now
  bars inferring personal facts ("years of experience is not an age"); the block is also appended
  to the judge's evidence so a correct age answer isn't flagged "unsupported".
- **Education: refusal AND confabulation on consecutive days.** 2026-08-21: `"where did Chris go to
  school"` → invented *Rowan*. 2026-08-22: same question → refused outright. Root cause is a
  **retrieval miss**, not a KB gap: `RESUME.md` always had the Education section (The College of New
  Jersey), but `/api/retrieve` showed the education chunk never ranking into the generator's top-5 —
  even the KB's own vocabulary ("Chris education college degree") placed it rank 4 at rerank score
  0.0004. **Fix:** school/college/education/university/degree/tcnj alias group in query_expansion.py
  + resume wording now includes "TCNJ" and "attended school". Requires reindex to take effect.

*k-sample harness:* `scripts/consistency_battery.py` asks each documented-failure probe k times
(default 5) with deterministic expect/forbid substring checks and gates on k/k — the harness the
stochastic defect always needed. **Results 2026-08-22:** baseline (pre-fix, live) FAILED — age 0/5
(consistently "41 years old as of 2023": no date anchor at all), school 0/5 (consistent refusal),
T5810 storage 1/5 (the stochastic negation, reproduced). Post-fix run 1: age 5/5, T5810 5/5,
school 0/5 — the alias group + wording alone didn't move the education chunk, because the chunker's
greedy 400-word merge had buried it at the tail of a work-history chunk, past the reranker's
512-token truncation (rerank score 0.0000 — the cross-encoder literally never saw it). Moving the
Education section up after Professional Summary put it in the resume's header chunk (37% depth);
rerank score went 0.0000 → 0.5760 at rank 1. Post-fix run 2: **6/6 probes at 5/5 = PASSED**.
Lesson: a chunk that ranks on embedding but whose relevant text sits beyond the reranker's
512-token window is scored blind — section placement within a merged chunk is a retrieval lever.

---

### 2. Judge Timeout Wrapper: Infrastructure Debt
**Status:** TEMPORARY FIX IN /tmp  
**Severity:** MEDIUM (affects eval reproducibility)  
**Discovery:** During Tier 2 fixture validation; judge hit 60s timeout  
**Issue:** The 240s timeout wrapper lives in `/tmp/judge_timeout_wrapper.py` — will be lost on reboot  
**Impact:** Next eval run will re-hit the 60s timeout; no consistent baseline  
**Fix required:**
- [ ] Move wrapper to permanent location (`home/verifier-service/judge_timeout_wrapper.py`)
- [ ] Document why 240s (judge latency + overhead + cold load buffer)
- [ ] Ensure it's used in all eval runs (`scripts/eval_graded.py` imports it)

**Discovered by:** Kimi (Tier 2 work)  
**Last reviewed:** 2026-08-05 (noted by Kimi as "infrastructure debt")

---

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

### 4. Verdicts.db: No Backup
**Status:** CRITICAL INFRASTRUCTURE GAP  
**Severity:** HIGH (verdicts.db is the ONLY durable metrics store)  
**Discovery:** Tier 7 planning (ops maturity)  
**Issue:** `verdicts.db` contains all judge verdicts (260+ entries, the ground truth for learning)  
**Risk:** Single point of failure; no disaster recovery  
**Impact:** If asrock fails, all historical verdict data is lost; can't analyze trends or review flagged answers  
**Fix required:**
- [ ] Add verdicts.db to backup routine (Tier 7)
- [ ] Monthly restore test to verify integrity
- [ ] Document location and retention policy

**Discovered by:** Kimi (noted as tech debt during Tier 7 planning)  
**Last reviewed:** 2026-08-05 (pending Tier 7 implementation)

---

---

## BASELINE — `qwen3.8-27b`, established 2026-08-29

**Every quality number recorded before this date is void.** They were measured against
`qwen2.5-coder-14b`; production now serves `qwen3.8-27b` (FP8, 32K context), pinned via
`MODEL_ID`. Measured with the reranker restored and `enable_thinking=false`:

| Metric | Value |
|---|---|
| Graded eval | **PASSED** — 32 grounded evals, **mean grounding 4.78** |
| Safety hard-fails (PII / prompt-leak) | 0 |
| Transport errors | 0 |
| Review-level warnings (⚠) | **0** — first run on record with none |
| Consistency battery | **7/7 probes at 5/5** |
| Self-test | 3/3 |

Superseded numbers: 4.80/4.70 grounding, the base-vs-LoRA A/B (0.983 vs 1.000), and
"pscode 0.71" in defect #1. Do not compare across the model change.

---

### 7. labrouter is not supervised
**Status:** OPEN
**Severity:** MEDIUM-HIGH — it is the single chokepoint every chat request passes through
**Issue:** `/etc/init.d/labrouter` sets `command_background="yes"` with **no `supervisor=`
line**, so it runs under start-stop-daemon and its `respawn_max=5` is inert. The process is
PPID 1. If labrouter dies, nothing restarts it and generation stops entirely.
**Fix:** add `supervisor="supervise-daemon"` + `respawn_max=0`, mirroring
`home/vllm-service/vllm-qwen38.openrc`. It already has logging.
**Note:** labrouter lives outside this repo (`/home/chris/ai/inference/labrouter`), so the fix
belongs to the lab lane, not cwdotcom. Flagged here because cwdotcom depends on it.
**Discovered by:** Claude (2026-08-30 fleet audit)

---

### 8. Alert delivery, not alert generation
**Status:** OPEN — needs a human decision, not code
**Severity:** HIGH — this is why a two-day outage went unnoticed
**Issue:** the monitor did its job. It detected the 2026-08-26 vLLM outage and paged
`[urgent] Portfolio AI DOWN — outage signature` on **Aug 27 and Aug 28**. Nothing happened.
**Likely cause:** the routine daily heartbeat lands on the **same ntfy topic** as urgent
pages. A channel that pings you every day with "all green" trains you to ignore it, so the
one message that mattered looked like the ninety that didn't.
**Fix options:** separate topic for CRITICAL vs heartbeat; drop the daily heartbeat to weekly
(the healthchecks.io dead-man's switch already covers "the monitor itself died"); or verify
the topic still reaches a device that actually notifies.
**Do not** respond to this by adding more probes. Detection is not the failure.
**Discovered by:** Claude (2026-08-31, correcting an earlier wrong claim in this ledger that
monitoring was blind)

---

## CLOSED DEFECTS

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

**Last Updated:** 2026-08-31  
**Owner:** Claude (reviews weekly), Kimi (discovers during tests)  
**Next Review:** 2026-08-26 (weekly flagged-queue)  
**Next Full Review:** 2026-09-05 (monthly ops review)
