# Continuous Improvement Framework: Convergence & Next Tasks

**Status:** Framework converged (2026-08-05). Defect-driven, not monitoring-calendar-driven.

---

## Convergence: What We Agreed On

### The Real Improvement Loop (Kimi's insight)
The system already produces the best learning signal: every flagged answer in `verdicts.db` is a labeled defect. 260+ flagged verdicts exist. Nobody reviews them.

**The loop that matters:**
- Weekly 15-minute flagged-queue review
- Mine `verdicts.db` for answers flagged by 14B judge
- Pick worst 5–10 offenders
- Categorize: KB gap, prompt gap, or judge error
- Log decision (drives DEFECT_LEDGER closure)

This is the only loop here that continuously improves answer quality. Everything else is instrumentation.

### Why This Works Within Red-Line #2
- ✓ No query content stored (verdict metadata only)
- ✓ Defects categorized without text details
- ✓ Learning via verdict scores, not query logs
- ✓ Privacy-compliant and effective

### Monitoring Calendar (Claude's framework, corrected)
Keep the monthly ops-hygiene review, but with fixes:
- **Fixed:** VERIFY_MIN_SCORE decision was backwards (lowering verifies MORE, not fewer; raise to reduce flags)
- **Struck:** The fake 0.50 baseline (n=10, cold loads, 4 idle days) — not a real baseline
- **Clarified:** Golden set metrics (20/20 retrieval from Tier 1; mean 4.48 graded eval from Tier 2)
- **Real baseline TBD:** Will establish at n≥50 real traffic (mid-week 2026-08-10)

---

## Known Defects (Priority Order)

All tracked in `DEFECT_LEDGER.md`. Four items:

### 1. SAP Business One: Generation Hallucination (HIGH, LIVE IN PROD)
- **Status:** Live in production; violates prompt rule #6 (grounding required)
- **Discovery:** Tier 2.3 golden-set eval; flagged by 14B judge
- **Evidence:** Rank-1 chunk has correct answer; model generates speculative fluff instead
- **Symptom:** Query returns non-KB details despite correct chunk available
- **Fix:** Verify chunk is passed to LLM; adjust system prompt grounding clause or fine-grain chunk content

### 2. Judge Timeout Wrapper: Infrastructure Debt (MEDIUM)
- **Status:** Lives in `/tmp/judge_timeout_wrapper.py` (will be lost on reboot)
- **Impact:** Next eval run will re-hit 60s timeout; no consistent baseline
- **Fix:** Move to `home/verifier-service/judge_timeout_wrapper.py`; update `scripts/eval_graded.py` to import permanently

### 3. Verdict Window: Silent Drop Risk (MEDIUM, STOPGAP)
- **Status:** `VERDICT_WINDOW_MS = 25000` (25s) is hardcoded
- **Risk:** If judge latency grows beyond 25s, verdicts silently drop
- **Current:** Mean 16.6s (n=10), max 56.6s (cold load) — room exists, but not guaranteed
- **Fix:** Option A (easy) = raise to 30–35s; Option B (right) = late-arriving verdict redesign

### 4. Verdicts.db: No Backup (HIGH, CRITICAL INFRASTRUCTURE)
- **Status:** Only durable metrics store; single point of failure
- **Risk:** If asrock fails, all judge-verdict history lost; can't analyze trends
- **Fix:** Add to backup routine (Tier 7); monthly restore test

---

## Next-Up Tasks (Prioritized)

### IMMEDIATE (This Week)

**Task 1: Weekly Flagged-Queue Review Protocol**
- First run: 2026-08-12
- Mine `verdicts.db` for worst 5–10 flagged answers
- Categorize each: KB gap / prompt gap / judge error
- Log decisions (closure driver for DEFECT_LEDGER)
- **Effort:** 15 min/week
- **Owner:** Claude (can automate later)
- **Why first:** Establishes the improvement loop before machinery

**Task 2: SAP Business One Fix**
- Verify query in prod: "Tell me about Chris's SAP Business One work"
- Check if rank-1 chunk is passed to LLM (or context-fitting issue?)
- Fix: Adjust system prompt or fine-grain chunk
- Test: Re-run query, verify uses retrieved chunk
- **Effort:** 1–2 hours (investigation + fix)
- **Owner:** Kimi or Claude
- **Why now:** Live bug, violates grounding rule

**Task 3: Judge Timeout Wrapper → Permanent Location**
- Move `/tmp/judge_timeout_wrapper.py` → `home/verifier-service/judge_timeout_wrapper.py`
- Update `scripts/eval_graded.py` to import permanently
- Document: why 240s (16.6s judge latency + overhead + cold-load buffer)
- Test: Run eval, no timeout errors
- **Effort:** 30 min
- **Owner:** Kimi or Claude
- **Why now:** Unblocks next eval run

---

### THIS SPRINT (Next 2 Weeks)

**Task 4: Tier 6 — KB Expansion**
- Index 14 remaining blog posts (28 exist, 14 indexed)
- Write "Current work / 2026" doc (newest content is May)
- Add philosophy pieces (why Gentoo, why self-host, AI governance)
- Fix RESUME.md date drift
- **Effort:** 4–6 hours
- **Owner:** Kimi
- **Why:** Covers off-topic queries; addresses flagged-queue findings

**Task 5: Verdicts.db Backup (Tier 7 prep)**
- Add `verdicts.db` to backup routine
- Monthly restore test
- Document retention policy
- **Effort:** 1–2 hours
- **Owner:** Kimi
- **Why:** Part of Tier 7; verdicts.db is the only durable metrics store

---

### NEXT SPRINT (Weeks 3–4)

**Task 6: Tier 7 — Ops Maturity**
- Alerting: watch flagged_rate + latency regression (weekly cron)
- `/version` endpoint + rollback procedure
- Formalize incident runbooks (Qdrant outage documented)
- **Effort:** 1–2 days
- **Owner:** Kimi or Claude
- **Why:** Depends on Tier 6; ops priority after KB current

**Task 7: Verdict Window Late-Arrival Redesign** (Optional)
- Option A (easy): Raise VERDICT_WINDOW_MS to 30–35s
- Option B (right): UI redesign for late-arriving verdicts
- **Effort:** 15 min (A) or 2–4 hours (B)
- **Owner:** Kimi
- **Why optional:** Current 25s has headroom; not urgent yet

---

## Which Task First?

Pick one to start this week:
1. **SAP defect fix** — Highest severity, known bug in prod
2. **Flagged-queue review** — Establishes the improvement loop
3. **Judge timeout wrapper** — Unblocks next eval

Recommendation: **Start with SAP fix + wrapper (parallel)**, then run first flagged-queue review by 2026-08-12.

---

## Files Updated

- `DEFECT_LEDGER.md` — Source of truth for defects
- `plans/continuous-improvement-framework.md` — Monthly ops review with corrections
- `OPERATIONS.md` — Health verification guide (unchanged)

---

**Generated:** 2026-08-05  
**Converged with:** Kimi + Claude  
**Next review:** Weekly (2026-08-12 first flagged-queue run), monthly (2026-09-05 full ops review)
