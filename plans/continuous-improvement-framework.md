# Continuous Improvement Framework

**Status:** Proposed (not yet implemented)  
**Purpose:** Define how the portfolio chat learns and improves beyond the 7-tier initial deployment  
**Gap addressed:** Monitoring exists (health checks, baselines), but no documented feedback loops or continuous improvement policy

---

## Current State (Post-Tier 5)

### What We Monitor
- ✅ Health checks (every 5 min)
- ✅ Judge flagged-rate (0.50 on n=10, watch line 0.35)
- ✅ Latency baselines (5.6s TTFB, 259ms reranker)
- ✅ Golden set eval (20/20 retrieval, mean 4.48)
- ✅ GPU metrics (T5810: 93% util, asrock: 1.3GB idle)

### What We DON'T Have
- ❌ Automated metric-driven decisions (if X triggers Y)
- ❌ Periodic eval cadence (when to re-run golden set?)
- ❌ Off-topic query tracking (triggering KB expansion)
- ❌ Judge calibration loop (flagged_rate > 0.35 → action)
- ❌ Voice/persona drift detection
- ❌ Performance regression response protocol
- ❌ Polish priority framework (what gets polished next?)

---

## Proposed: Continuous Learning Loop

### Monthly Cadence

#### Week 1: Metrics Review
- [ ] Judge flagged-rate: Review last 30 days of verdicts
  - If mean > 0.35: investigate whether judge is over-flagging
  - Action: Adjust VERIFY_MIN_SCORE or judge system prompt
  
- [ ] Latency trends: Compare current p50/p90/p99 vs baseline
  - If TTFB drifts >20%: investigate (GPU util? tunnel? T5810 load?)
  - Action: Optimize or debug the regressed stage
  
- [ ] Off-topic query analysis: Group failed/refusal queries
  - If >10% of queries get "I don't have that documented":
    - Analyze what topics are missing
    - Action: Queue KB expansion for next sprint

- [ ] Golden set re-run: Pick 5 random golden set questions, score manually
  - If any score drops >1 point: investigate
  - Action: Debug the retrieval/generation stage

#### Week 2: KB Freshness
- [ ] Review query logs for trends (if available)
  - What questions recur?
  - What questions fail?
  - Action: Add docs for trending questions

- [ ] Date drift check: RESUME.md, current work docs
  - If any "Present" or "Current" is >3 months old: update
  - Action: Write current status

- [ ] Opinion/voice check: Sample 3 recent responses
  - Are they sounding like Chris? (first-person, opinionated, direct)
  - If not: review system prompt or add voice exemplars
  - Action: Tune persona or add KB grounding

#### Week 3: Performance Optimization
- [ ] GPU memory trending: Is T5810 creeping toward OOM?
  - Action: Profile and optimize or disable features
  
- [ ] Tunnel health: Any connection resets or latency spikes?
  - Action: Monitor or reconfigure

- [ ] Rate limiter: Any abuse patterns?
  - Action: Adjust limits or IP block if needed

#### Week 4: Polish & Future Planning
- [ ] Tier 6/7 progress: What's next?
- [ ] User experience observations: Any UX pain points?
- [ ] Baseline update: If systems are stable, record new baseline
- [ ] Plan for next sprint improvements

---

## Decision Framework: "What Gets Fixed?"

### Critical (Fix immediately)
- System is down (E2E chat fails)
- Latency >50% worse than baseline
- Judge flagged-rate > 0.50 (trending wrong)
- Any security/PII issue

### Important (Fix this week)
- Judge flagged-rate 0.35–0.50 (investigate, don't yet fix)
- Latency drifting 20–50% worse
- Off-topic rate >20%
- Voice/persona noticeably off

### Nice-to-have (Backlog, Polish)
- UI paper cuts (Tier 5 already handled most)
- KB docs that could be more detailed
- Latency optimization ideas
- New feature ideas

---

## Automation Triggers (Optional)

If you want to formalize feedback loops, these could be automated:

```bash
# Weekly script (cron: every Monday 6 AM)
scripts/continuous-improvement.sh
├─ Judge flagged-rate check (yesterday, last 7 days, last 30 days)
├─ Latency comparison (p50/p90/p99 vs baseline)
├─ Off-topic query count (queries returning fallback response)
├─ Golden set spot-check (5 random queries, manual scoring)
├─ Send summary to ntfy.sh channel
└─ Log results to metrics.jsonl for trending

# Monthly deep-dive (cron: first day of month)
scripts/monthly-eval.sh
├─ Full golden set re-run (all 40 questions)
├─ KB freshness audit (date drift, orphaned docs)
├─ Voice/persona sampling (3 random E2E queries, human review)
└─ Report: continue as-is, or schedule improvements?
```

---

## Judge Flagged-Rate: Decision Tree

**IMPORTANT: Current n=10 baseline (0.50) is NOT REAL.** 
- Small sample size (n=10)
- Collected after 4 idle days (cold loads inflate latency, not a steady-state signal)
- Do NOT make decisions against this number

**Real baseline TBD:** Will establish at n≥50 real traffic (mid-week 2026-08-10)

```
Is flagged_rate > 0.35 at n≥50 real traffic?
├─ YES (persistent over-flagging)
│  ├─ Check: Is the judge correct? (review 10 flagged answers via verdicts.db)
│  ├─ YES, judge is right, but too strict
│  │  └─ Action: RAISE VERIFY_MIN_SCORE (gates when verification runs; lower = more flags)
│  └─ NO, judge is wrong
│     └─ Action: Adjust judge system prompt or add grounding examples
└─ NO (under 0.35, converged to acceptable range)
   └─ Action: Monitor, continue baseline
```

**NOTE:** VERIFY_MIN_SCORE gates whether verification runs at all. Lowering it verifies MORE queries → MORE flags. To reduce flag volume, RAISE the threshold.

---

## Voice/Persona: Drift Detection

**How to catch if the system stops "sounding like Chris":**

1. **Weekly spot-check:** 3 random E2E queries, manual review
   - Does the response sound first-person (I, my, we) vs generic?
   - Does it show conviction/opinion vs hedging?
   - Does it reference personal experience?

2. **Metrics-based:** Count first-person pronouns in responses
   - If "I" + "we" + "my" < 2 per 100 words: investigate
   - Action: Review system prompt, add grounding examples

3. **Eval-based:** Run voice-specific golden set questions
   - "What's your philosophy on infrastructure design?"
   - "Why do you run your own infrastructure?"
   - If scores drop >1 point: voice has drifted

---

## KB Freshness Policy

### When to add new docs:
1. Same question asked 3+ times in production (off-topic rate rising)
2. Any major life/work update (new project, new role, new hardware)
3. Every 3 months minimum (keep "current work" current)
4. When a golden set question fails (update KB to cover it)

### When to retire/update docs:
1. Any "Present" or "Current" that's >6 months old
2. Outdated tech that's no longer relevant
3. Docs that are factually wrong (discovered via judge feedback)

---

## Success Criteria

✅ **System is continuously learning if:**
- Judge flagged-rate converges to 0.15–0.35 range (acceptable; TBD at n≥50)
- Latency stays within ±10% of Tier 3 baseline (5.6s TTFB, 259ms reranker)
- Off-topic rate stays <15%
- Voice/persona remains consistent (first-person, opinionated)
- KB stays fresh (no docs >6 months old)
- Graded eval mean ≥3.5 (Tier 4 baseline: 4.48)
- Retrieval recall ≥20/20 on golden set (Tier 1 baseline)

❌ **System is degrading if:**
- Flagged-rate trends >0.40 consistently at n≥50
- Latency drifts >20% worse than baselines
- Off-topic rate >25%
- Voice becomes generic or hedged
- KB has docs 12+ months old
- Graded eval mean drops below 3.5
- Retrieval recall drops below 19/20

---

## Implementation Options

### Option A: Manual Review Loop (Low effort, low enforcement)
- Monthly 1-hour review by operator (Claude or Kimi)
- Check metrics, investigate issues, document decisions
- **Cost:** ~4 hours/month
- **Effectiveness:** Catches big issues, misses small drifts

### Option B: Automated Reporting (Medium effort, better enforcement)
- Weekly automated reports (flagged-rate, latency, off-topic count)
- Metrics dashboard showing 30-day trends
- Triggers alerts if thresholds exceeded
- **Cost:** ~2 hours setup, ~1 hour/month maintenance
- **Effectiveness:** Catches drifts early, provides data-driven decisions

### Option C: Fully Automated Loops (High effort, high enforcement)
- Weekly auto-run of golden set eval
- Monthly auto-adjust of VERIFY_MIN_SCORE if flagged-rate wrong
- Auto-generate KB gap report from off-topic queries
- **Cost:** ~8 hours setup, ~0.5 hours/month maintenance
- **Effectiveness:** System continuously self-optimizes

---

## Recommendation

**Start with Option A (Manual Monthly Review):**
- Low overhead for now (single-user system)
- Gives you experience with what metrics matter
- Graduate to Option B when you have more usage data
- Only go to Option C if drifts become frequent

**Next: Schedule first monthly review for 2026-09-05** (1 month post-Tier-5 deployment)

---

**Owner:** Chris (or operator running Tier 6/7)  
**Cadence:** Monthly review, weekly trending (if automated)  
**Last Updated:** 2026-08-05
