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

*Verifier note:* none of these were flagged by the 14B judge, so the faithfulness verifier is also
missing this class. Worth checking against defect #3 before trusting flag counts as a quality signal.

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

### 5. Router: "Favorite Language" Answers Neither Way
**Status:** OPEN
**Severity:** LOW (cosmetic; graded eval reports it as review-only, not a gate failure)
**Discovery:** Graded eval after the 2026-08-19 router fix (commit 4565c8b)
**Issue:** `"What is Chris's favorite programming language?"` scores g=1 — "neither cleanly
refused nor substantive." Under the old off_topic default it got a clean canned refusal;
now it routes on_topic, retrieves weak evidence, and waffles instead of committing.
**Fix options:**
- [ ] Option A: KB gap — the corpus has no explicit preference statement; add one if true
- [ ] Option B: Prompt — strengthen the "commit or say you don't have it" instruction
**Note:** Do NOT fix by reverting the router default. That default caused defect #6.
**Discovered by:** Claude (2026-08-19 session)

---

### 6. WATCH: Grounding 4.80 → 4.70 After the T5810 Storage Reindex
**Status:** OPEN (watch item, not a confirmed regression)
**Severity:** LOW — graded eval PASSED; both flags are review-level, not gates
**Discovery:** 2026-08-19, graded eval run immediately after the homelab_t5810.md reword + reindex
**Observation:** mean grounding 4.80 → 4.70, and a new sub-2.5 flag on
`"What Linux distributions has Chris used in production?"` that was not present in the run 40
minutes earlier on the same code.
**Two candidate causes, not yet separated:**
- Run-to-run variance. Generation is temperature 0.2 and the judge is an LLM; a 0.10 swing on a
  30-item mean is plausibly noise. One re-run would tell.
- Real effect of the edit. Adding a `### Storage` section to `homelab_t5810.md` shifts chunk
  boundaries in that doc, which can displace OS/distro content into a different chunk and change
  what surfaces under the ≤2-per-doc cap.
**Next step:** re-run `scripts/eval_graded.py` unchanged. If 4.70 reproduces, diff retrieval for
that question against the pre-reindex ranking before touching anything.
**Do not** "fix" this by reverting the storage reword — that fix is verified on 4 of 5 phrasings.
**Discovered by:** Claude (2026-08-19 session)

---

## CLOSED DEFECTS

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

**Last Updated:** 2026-08-19  
**Owner:** Claude (reviews weekly), Kimi (discovers during tests)  
**Next Review:** 2026-08-26 (weekly flagged-queue)  
**Next Full Review:** 2026-09-05 (monthly ops review)
