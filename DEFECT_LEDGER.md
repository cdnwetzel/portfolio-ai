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

## CLOSED DEFECTS

*None yet. This ledger is new (2026-08-05).*

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

**Last Updated:** 2026-08-05  
**Owner:** Claude (reviews weekly), Kimi (discovers during tests)  
**Next Review:** 2026-08-12 (weekly flagged-queue)  
**Next Full Review:** 2026-09-05 (monthly ops review)
