# KB answer-quality fixes — 2026-11

**Status (2026-11-04):** fixes committed on branch `kb/answer-quality-fixes-2026-11`, offline
tests green (205 passed). **Not merged, not reindexed, not re-measured.** The live site still
answers from the 2026-11-01 index until an authorized `./scripts/reindex_kb.sh`.

**One-line summary:** the site's wrong answers were faithful to wrong text. The model and the
verifier are working; the knowledge base, and one file that should never have been in it, were
not. Every fix below is to content, plus tests that stop the same wording coming back.

---

## 1. How the problems were found

Tested first, fixed once, as agreed ("test further before we just keep adjusting").

| instrument | what it does | result before fixes (2026-11-01) |
|---|---|---|
| **Battery** `scripts/kb_battery.py` | 14 questions x 3 fresh chats through live `wss://dev.cwetzel.com/ws/chat`; records regex-probe booleans and timings only, never answer text (red-lines #2) | 42 turns, 0 errors. Retrieval median 577 ms, TTFT median 2.3 s, decode median 68 tok/s. Probe hit rates in §2 |
| **Graded eval** `scripts/eval_graded.py`, judge qwen2.5:14b | 54-item golden set, 44 grounded | PASSED. Grounding **4.59** (Sept 4.75, same set), faithfulness 4.88, 0 safety fails, 0 transport errors. 3 judge JSON fallbacks |
| **repeat_sample -n 5** | 10 questions x 5, stability + forbid list | 50 generations, 0 UNSTABLE, 0 transport errors, **2 FORBIDDEN** (see §5) |
| **Verifier probe** `vprobe.py` (scratchpad) | planted an unsupported claim (Kubernetes/Helm/Pulumi) 5x buried, 5x alone | **5/5 and 5/5 caught, byte-identical verdicts.** Deterministic at temp 0 |

**Why the verifier didn't flag these:** it checks the answer against the retrieved chunks. Each
error here *was* in the chunks, so the answer was faithful. That's by design, and it's why this
is a KB fix, not a verifier fix.

---

## 2. Findings, root cause, fix

Rates are from the battery (bad-probe hits / 3). File:line refers to the pre-fix tree.

| # | the site said | rate | root cause | fix |
|---|---|---|---|---|
| **F4/F11** | Chris uses **Terraform and Ansible** | 3/3 (IaC q), 1/3 ("what has Chris built") | `PROFESSIONAL_CONTEXT.md`, a June SaaS-planning note (personas, pricing, GATE 1), was indexed as "Professional Context & Positioning". Line 66: *"Your GitHub repos **likely** contain: Infrastructure as Code (Terraform, Ansible)"*. 5 of the 109 live chunks | Removed from `load_documents()`; file moved to `docs/archive/`. Checked first: every true fact in it (26 years, P2V, SOC2, PowerShell, Boyum, Produmex…) is also in `RESUME.md`, so nothing true is lost. OctoberCMS is the only term that exists nowhere else, and it's not worth keeping |
| **F3** | an **SSH reverse tunnel** | 3/3 | KB said "reverse" 4 times (`ai_portfolio_system.md:5,41,272,301`, `homelab_t5810.md:185`). The unit (`cloud/systemd/portfolio-ai-tunnel.service`) is `ssh -N -L …`, opened by the VPS: ordinary local forwards | All occurrences now say what it is: VPS-initiated local port forwards (`ssh -L`). **No negations** ("not a reverse tunnel"), because they put the wrong word back into the chunk |
| **F2** | the judge is **"a different model family"** | 3/3 on "is the judge independent?" | `ai_portfolio_system.md:309`, `homelab_t5810.md:98`. Both models are Qwen | "different model, generation and size, **same Qwen family**: reduces self-grading bias, doesn't eliminate it." Same correction to `ai_portfolio_system.md:55`, CLAUDE.md (2 lines), and the `eval_graded.py` banner, which printed "independent, no echo-bias risk" |
| **F10** | **~47 tok/s** for a fresh question | 3/3 | `ai_portfolio_system.md:200`, `homelab_t5810.md:134`: the 2026-09-14 figure | ~70 tok/s (12 site turns 2026-11-01, median 69.7, range 42–74; battery median 68), benchmark ~79. Why 47 became 70 with the same k=3 config is **not explained**; the September question mix differed. The KB states the new measurement and dates it, and doesn't offer a cause. It no longer mentions 47 at all, for the same priming reason as F3. It also makes no claim about follow-up decode speed, which wasn't re-measured |
| **F9** | follow-ups are faster **because of prefix caching** | 0/3 (didn't reproduce) | `ai_portfolio_system.md:201-202`: "shared prefix is already cached, so less work is repeated" | Prefix caching shortens TTFT (prefill). It doesn't change decode tok/s, which tracks draft-head acceptance. The paragraph now says exactly that |
| **F6** | vLLM is **on port 8004** | 2/3 | ports table `ai_portfolio_system.md:277`: `\| vLLM \| 8004 \|` | Row now reads `labrouter → vLLM \| 8004 (labrouter) → 8007 (vLLM)` |
| **F5** | a broad "major project" answer **blends AVD with P2V/V2V** | 2/3 | No overview doc. A broad query retrieves résumé and context chunks where "VMware (P2V migrations)" sits next to "Azure VDI Migration"; the AVD case study loses retrieval | New `knowledge_base/case_studies/major_projects_overview.md`: one section per project, facts copied from each case study, AVD named as the best example, plus an explicit line that AVD involved no P2V/V2V. Removing the context doc also takes away one source of the blend |
| **F1** | the reranker runs on an **A4500** | 1/3 | `ai_portfolio_system.md:5`: "on a second GPU" | Merged `7bc4f1d` (`kb/reranker-location`), then reworded its parenthetical "(…5060 Ti, not the A4500s)" to the positive form, for the same reason as F3 |
| **F7** | "18 years" at MSPs, 3/3 | **The answer was right; the KB was incomplete.** `RESUME.md` listed 2 of 6 jobs, so "18" came only from a post title and the résumé added up to 9.5. Corrected 2026-11-07 (see §6) | Full work history from cwetzel.com/experience: Pro Computer Service 2004–2013 (the first MSP) + RedEye 2014–2023 ≈ 18 years. Plus a career table and an explicit "18 years at two MSPs" line |
| **F8** | pxx has **690 tests** | — | `pxx_project.md:100,120,136`, June figure | **1,863** (`pytest --collect-only` on a clean clone of the public repo, v2.9.3 at 5be59d5, 2026-11-07). An earlier 1,008 came from a stale local copy (`~/ai/pxx`, v1.3.4) and was wrong |
| — | (no answer seen) | — | the tunnel-paragraph said ports `8004/6333/8005/8006` resolve to `127.0.0.1`, and the diagram hung "rerank 8006, judge 8007" under the T5810 | Fixed: 8016 → asrock:8006 and 8007 → asrock both resolve to the asrock. Found while fixing F3 |
| — | (no answer seen) | — | reranker-fallback text said "max **one** chunk per document" in two places | `RAG_MAX_PER_DOC=2` applies on both the reranked and fail-open paths (`api-proxy.py:456`). Now says two |
| — | (no answer seen) | — | "Nothing on either home server is exposed to the public internet." The T5810's sshd is reachable at jump.example.net, because the tunnel needs it | Now: none of the *services* listens publicly; they're reached through the T5810's sshd (key auth), the one home-side entry point |

### Not fixed in this batch

| # | what | why not |
|---|---|---|
| — | the *golden set* doesn't cover any of F1–F10 | Deliberately left alone: adding items changes the set size, and grounding means across different set sizes aren't comparable (the earlier 32 → 44 change). Add them **after** the before/after, as their own commit, with the battery's questions and `forbid_substrings` for the bad probes |
| — | the graded-eval family check (`_family()`) passes qwen2.5-14b vs qwen3.8-27b as distinct | It *is* a different model, so the check does what it claims. Only the banner overclaimed, and that's fixed. A lineage check would fail every run today and change nothing |

---

## 3. What changed (files)

| file | change |
|---|---|
| `knowledge_base/infrastructure/ai_portfolio_system.md` | F1, F2, F3, F6, F9, F10; port resolution, fallback cap, exposure sentence |
| `knowledge_base/infrastructure/homelab_t5810.md` | F2, F3, F10 |
| `knowledge_base/pxx_project.md` | F8 |
| `knowledge_base/case_studies/major_projects_overview.md` | **new**, F5 |
| `knowledge_base/INDEX.md` | lists the new file (INDEX.md is not indexed) |
| `scripts/index_with_embeddings.py` | no longer loads `PROFESSIONAL_CONTEXT.md`; comment says why |
| `PROFESSIONAL_CONTEXT.md` → `docs/archive/` | git mv |
| `scripts/eval_graded.py` | banner says what the independence check proves |
| `scripts/kb_battery.py` | **new**: the battery, committed. Probes widened so corrected wording counts (F2 "same Qwen family", F10 "70") |
| `tests/test_kb_content.py` | **new**, 11 tests. **10 fail on the pre-fix tree** (verified in a worktree of `main`). The 11th pins the KB to the tunnel unit's `-L` and passes on both |
| `CLAUDE.md`, `DEFECT_LEDGER.md` (#19) | judge wording; alignment entry marked NOT yet reindexed |

**Index effect:** 36 docs (−1 context doc, +1 overview). The chunk count will change, so read it
from `/api/system-info` afterwards rather than predicting it.

---

## 4. Rollout — needs authorization at step 2

1. **Review and merge** `kb/answer-quality-fixes-2026-11` → `main`.
2. **Reindex (authorized action):** `./scripts/reindex_kb.sh`. This wipes and rebuilds `documents`
   from the committed KB. Run it through the script, not the direct indexer call used on 2026-11-01.
   Note: the old loader read `PROFESSIONAL_CONTEXT.md` from the KB's *parent* directory, which
   under the script is `/tmp` on the T5810, so whether it got indexed depended on how the indexer
   was run. With the loader removed, both paths agree.
3. **Confirm the index:** `curl -s https://dev.cwetzel.com/api/system-info` shows the new chunk
   count. A Qdrant scroll shows **zero `source: context` points** (5 today).
4. **Re-measure, same instruments, same order:**
   ```bash
   python3 scripts/kb_battery.py post 3
   python3 -u scripts/eval_graded.py --judge-url http://192.0.2.115:11434/v1/chat/completions \
       --judge-model qwen2.5:14b-instruct-q4_k_m --out eval/results/kbfix-20261104.jsonl
   python3 scripts/repeat_sample.py -n 5
   ```
   Pace them: the verifier queues ~30–40 s per verdict serially, and a burst of tests built a
   ~1 h backlog on 2026-11-01. It's fail-open, so this doesn't affect answers, only the verdict lag.

### Acceptance criteria (decided before measuring)

| check | pass |
|---|---|
| battery bad-probes F2, F3, F4 | **0/3 each** (were 3/3) |
| battery bad-probes F1, F5, F6 | **0/3 each** (were 1/3, 2/3, 2/3) |
| F10 | `says_70` true on ≥2/3, `says_47` 0/3 |
| F5 positive | `avd_specifics` on the broad question ≥2/3 (was 0/3) |
| graded eval | PASSED, 0 safety fails, 0 transport errors, mean grounding **not below 4.59 by more than noise**. Compare row by row against `baseline-20261101.jsonl`, not mean to mean (DEFECT_LEDGER #18: one judge row can move the mean 0.09) |
| repeat_sample | 0 UNSTABLE, 0 transport errors; FORBIDDEN hits triaged (§5) |

A miss on a battery probe is a reason to look, not an automatic fail. A regex can match a correct
sentence. Look at that one turn live in the browser rather than logging text.

### Rollback

`git revert` the merge, then `./scripts/reindex_kb.sh` again (authorized). The index is fully
derived from the committed KB, so there's no state to restore by hand.

---

## 5. Open questions carried forward

- **repeat_sample's 2 FORBIDDEN hits** ("3060" on "What has Chris built?", "130 W" on "What is
  the GPU power cap?"). Both terms exist in the KB as *historical* facts: the retired 3060 Ti, and
  "the 130 W cap … is gone". So these are probably correct answers mentioning history that the
  forbid list treats as wrong. Needs a targeted look at those two answers. If they're correct, the
  forbid entries need context, not deletion.
- **The verifier's limits** (measured 2026-11-01, not changed here):
  - It's reliable on planted unsupported claims.
  - It can miss a fact buried deep in a long, low-ranked chunk (the AVD payback false negative).
  - About 5% of its JSON is malformed.
  - Its claim extraction is coarse: it merged 4 sentences into 3 claims.
  - It runs serially at ~30–40 s per verdict.
  - By design, it can't catch errors that are in the KB.

---

## 6. Coverage of cwetzel.com and LinkedIn (added 2026-11-07)

Chris asked that everything on https://www.cwetzel.com (Summary, Experience, Projects, Education,
Volunteer) and on the public LinkedIn profile be covered. The pages were fetched with `curl` and
compared item by item against the KB.

**Added:**
- **`RESUME.md`:**
  - **Work history:** all 9 roles on LinkedIn (6 on the site) with exact dates and locations. Before, it had 2:
    Director of Legal Technology at Portnoy Schneck, and Senior Engineer at RedEye (full-time
    to Jun 2023, part-time to Aug 2023). The other 4 are new: the Mercer Institute at MCCC
    trainer contract, PeriGen sysadmin, Pro Computer Service, and MBNA America (NT→2000 with
    Altiris).
  - **Current title** corrected from "IT Manager" to Director of Legal Technology. The site's
    headline still says "IT Manager and veteran systems engineer", so both are kept.
  - Site bullets added verbatim for each job.
  - **Volunteer roles:** MCCC sports photographer and assistant cross-country coach, including
    the NJCAA nationals detail from LinkedIn.
  - Exact TCNJ dates and OctoberCMS.
  - **From LinkedIn:** the TryHackMe courses, the April 2012 Deptford Township PD commendation
    letter, the Wonderlic WPT-P score, and the services list. The commendation is listed
    *without* the officer's name, under red-lines #6 (no third-party personal data).
- **4 recent LinkedIn posts** in `posts/`: the Copilot audit log (2026-08-12), the pxx v2.4.0
  release (2026-08-07), the inference cost race (2026-07-04) and Memorial Day (2026-05-25).
  The other two posts visible publicly were already indexed. The Aug 3 "bit of humor" post is
  an image with one line of text, so it was skipped.
- **`major_projects_overview.md`** was rewritten from cwetzel.com/projects text plus LinkedIn
  project dates: AVD Nov 2021, SOC2 2022, the studio 2018, and Gentoo 2025.

**Not visible publicly:** LinkedIn hides experience detail, the full About, and certifications
when logged out. The site covers experience. If the full About or any certifications matter,
paste them.

### Provenance finding: some KB "facts" are not on the site, LinkedIn, or anywhere else

Five case studies were created in one commit, `2377081` on 2026-06-06 ("Create 5 detailed case
studies … for GATE 2 RAG indexing"). That was the same SaaS-scaffold phase as
`PROFESSIONAL_CONTEXT.md`: 1,298 lines in one go, with figures that later changed. For example,
the commit message says the SAP savings were "$212k/year" and the case study now says $229.5k.

SOC2, the graphic-design studio, SMB BCDR and M365 have since been rewritten to match the site.
**AVD and SAP have not.**

- **The AVD client conflicts.** The site and LinkedIn say the AVD environment hosts the client's
  SAP Business One, Boyum and Produmex WMS. The KB makes the AVD client a "financial services
  firm" and the SAP client a separate "distribution company".
- **AVD details not on the site or LinkedIn:** the "Citrix farm in NYC", NYC/London/Singapore,
  4 months, 99.5% uptime, $200k cost, $145–171 per user, payback ~6 months.
- **SAP details not on the site or LinkedIn:** 6 warehouses (NYC, Miami, London, Athens,
  Singapore, Sydney), 8 months, 50→200+ users, 95% query improvement, $229.5k/yr, payback
  ~10.5 months.
- **`RESUME.md` "Notable Projects"** carries the old generated versions:
  - SOC2: "row-level security … passed audit, enabled partnerships"
  - DR: "home office internet outage, 5-min RTO"
  - VMware: "50+ servers across 3 data centers, 60% cost reduction"
- **Résumé bullets: now mostly confirmed.** Chris pasted the full LinkedIn Experience section on
  2026-11-07, and Work History was rebuilt from it. It confirms the Portnoy 75% sync-time
  improvement, GPU document processing, PHI/PII redaction and MSSQL administration, and every
  RedEye bullet. It also adds three earlier roles: Central Bucks SD 1999–2002, TCNJ student
  worker 2002–2004, and Howell Township SD 2004. Those explain "26 years".
  - Dropped, because no source has them: "40+ staff", "GDPR", and AWS as a RedEye bullet. AWS
    stays in the headline.
  - **Still unsourced:** RedEye "50+ enterprise clients across healthcare, finance, legal, real
    estate", "multi-region deployments" in Core Expertise, and "Azure fundamentals" under
    Certifications.
  - LinkedIn now says posts "reached 120,000+ IT professionals". The dated 6-month figures
    (114,631 impressions, 42,000+ top post) are kept as they were.

**Three golden-set items test these numbers:** AVD payback "6 month", SAP payback "10.5 month",
SAP "6 warehouses". If the numbers aren't real, the eval is rewarding the site for repeating
them.

**Resolved for AVD and SAP (2026-11-07).** Chris confirmed:
- they were **one client**: a global distributor of medical supplies to the maritime and
  offshore industries, with a New Jersey HQ and hubs in Miami, the UK, Greece, Singapore and
  the UAE (unnamed by choice)
- he **co-led the work with a RedEye colleague**, **Nov 2021 until he left RedEye in Aug 2023**

What was done:
- Both generated studies moved to `docs/archive/generated-case-studies-2026-06/`, with a README.
- One replacement, `case_studies/avd_sap_global_distributor.md`, written from confirmed facts
  only. It says outright that costs, payback, uptime and region names are not documented.
- RESUME.md's AVD and SAP entries rewritten the same way.
- Golden set: the two payback items were retired and replaced one-for-one, so the set is still
  54. The warehouse item is now "six sites".

**Résumé Notable Projects resolved (2026-11-07).** Chris pasted LinkedIn's Projects section:
SOC2 Jan–Dec 2022 and the macOS→VMware/EqualLogic studio migration in 2018, each with a
colleague, plus Gentoo 2025–present. "Notable Projects" was rebuilt from those and the site's
projects.

Removed, because no source has them:
- the "50+ servers / 3 data centers / 60%" VMware story
- SOC2 "row-level security… enabled partnerships"
- DR "home office internet outage, 5-min RTO"
- "50+ enterprise clients", "multi-region" and "Azure fundamentals"

Commit **77556b9 (2026-06-28) had already named the VMware and "40+ staff" figures as
fabricated** when it fixed the case studies; RESUME.md had kept its own copies. The volunteer
end date is written as "2014", because the site says March and LinkedIn says May. Guard:
`test_june_fabrications_stay_out_of_the_resume`.

**Security doc resolved (2026-11-07).** `case_studies/security_hardening_operations.md`
(created 2026-06-07, generated era) is a control framework. Chris confirmed the work behind it is
real, done for clients in regulated industries: mortgage, title and real estate; doctors and
endodontists; law firms; pharmaceutical; social work and family services.

Changes:
- Kept the controls.
- Removed 9 invented example "records": the 2024–2025 certificate timeline, "Firewall review
  Q2 2024", "Support1", "client ABC", VULN-2847 with deploy timestamps, and the
  example-findings list.
- Replaced the compliance-regime list (PCI DSS 4.0, NIST 171, FINRA; no source has them) with
  the industries, plus SOC 2 and HIPAA.
- The industries also go into RESUME.md as one stated fact.
- 466 → 273 lines. Guard: `test_security_doc_has_no_invented_records`.

Original note, kept for the record: whether these are real is Chris's call. My overview no longer
repeats any of them. Once Chris answers, the fix is one of two:
- confirm the facts, and add them to the overview with a source note, or
- strip them from the case studies and RESUME and retire the three golden items.

### System corrections verified against the running code (2026-11-07)

Chris pointed out there are two sources for the site, the repo and what's actually running, so
group B was re-checked live:
- the running tunnel process on the VPS (`ssh -N -L … chris@jump.example.net`)
- the deployed `/opt/api-proxy/main.py`, which is md5-identical to `cloud/api-proxy.py`
- the verifier's `/health` (`qwen2.5:14b-instruct`) and the `/v1/models` lists on 8004 and 8007
- `ss -ltn` on the T5810
- a port probe from the VPS: only 22 is open from the internet

All seven corrections were approved. The seventh is new: Qdrant and vLLM listen on `0.0.0.0`
(LAN), not localhost, and the KB now says so.

**Ops follow-up, not KB text:** the VPS `api-proxy.service` hardcodes `KB_DOC_COUNT=35` and
`KB_CHUNK_COUNT=99`, so `/api/system-info` shows stale counts. Fix it with the reindex; that
needs a deploy, so it needs authorization.

**pxx:** the public repo is at v2.9.3 (1,863 tests). `pxx_project.md` was written against v1.x
and probably needs a refresh from the public README, as a separate step.

---

## 7. Results after the reindex (2026-11-07, 22:49–23:34)

The same three instruments, run in the same order against the live site after the reindex and
deploy (`9035cad`).

**Battery** (`battery-post.jsonl` vs `battery-pre.jsonl`; 42 turns, 0 errors). Bad-probe hits:

| # | probe | before | after |
|---|---|---|---|
| F1 | reranker on an A4500 | 1/3 | **0/3** (and says 5060: 0/3 → 3/3) |
| F2 | "different family" | 1/3, 3/3 | 0/3, 2/3. **0/3 on a re-ask**, so the 2/3 was run-to-run variation; "same family" 3/3 on both questions |
| F3 | "reverse" tunnel | 3/3 | **0/3** |
| F4 | Terraform/Ansible | 1/3, 3/3 | 0/3, 2/3. **Probe false positive:** the answer is now "Chris doesn't use a dedicated IaC platform like Terraform or Ansible" |
| F5 | AVD blended with P2V | 2/3 | **0/3**. But AVD specifics on the broad question are 0/3: the model picks another project (see below) |
| F6 | vLLM on 8004 | 2/3 | **0/3** |
| F7 | 9.5 years | 2/3 | **0/3**; "18" 3/3; names Pro Computer Service 3/3 |
| F9 | prefix caching credited with decode | 0/3 | 1/3. **Probe false positive:** the hit is in a suggested-question chip; the answer says follow-ups generate "at the same speed" |
| F10 | 47 tok/s | 3/3 | **0/3**; says ~70: 3/3 |

Timing is unchanged: decode median 67.4 tok/s (was 68.0), TTFT median 1.96 s (was 2.32),
retrieval 581 ms (was 577).

**Graded eval** (`kbfix-20261107.jsonl`, 57 items): **PASSED**.
- 47 grounded, mean grounding 4.77, faithfulness 4.98, 0 safety fails, 0 transport errors.
- **Paired over the 43 shared grounded rows: 4.581 → 4.744.**
- 6 rows went up. The big moves: AVD payback 1 → 5 (the DEFECT_LEDGER #18 judge false
  negative), "what models are running" 2 → 5, disaster recovery 3 → 5.
- 5 rows went down by 1 each, which is within the judge's noise.
- The 3 new items scored 5, 5, 5.
- Still low: "What would you do differently…" (a known retrieval miss).

**repeat_sample -n 5** (50 generations): 0 UNSTABLE, 0 transport errors, 1 FORBIDDEN, 1 VARIABLE.
- **The FORBIDDEN hit is a correct answer:** "130 W" appears as history ("an older crypto-mining
  profile that had been power-starving the cards at 130 W") and in a suggestion chip. The
  forbid rule `130\s*w` can't tell history from a claim, so it needs context, not deletion.
- The earlier "3060" FORBIDDEN did not recur.
- VARIABLE: the SAP question mentions warehouses or continents in 1 of 5 runs. Informational
  only, never wrong.

### Verdict against §4's acceptance criteria

Met:
- F3, F6, F10 and F1
- F2 and F4 on re-ask and on reading the answers
- graded eval passed and higher on paired rows
- 0 UNSTABLE

**Not met: F5's positive criterion** ("AVD specifics on the broad question ≥2/3", got 0/3). The
broad question now gets a correct answer about a *different* project, not a wrong one. The
overview lists SOC2 first and no longer names a best example. Whether to steer broad questions
to AVD is Chris's call.

**Decided 2026-11-08 (Chris):** "i don't have a preference about a major infra project as long as
it speaks from facts". The positive criterion is withdrawn. F5 is met if the broad answer is
factual and does not blend projects (bad_avd_p2v 0/3), which it is.

### Instrument fixes (approved by Chris 2026-11-08: "wrongly flagging accurate answers is also not acceptable"; done, see §8)

1. `scripts/kb_battery.py`:
   - drop text after `FOLLOWUPS:` before matching
   - make the F4 and F2 bad-probes ignore denials ("doesn't use … Terraform")
2. `scripts/repeat_sample.py`: the 130 W forbid should match a *current-cap claim*, not any
   mention.

## 8. Instrument fixes (2026-11-08)

Approved by Chris: "fix the test scripts, we need to ensure accuracy, and wrongly flagging
accurate answers is also not acceptable".

**Shared, in `scripts/expectations.py`:**
- `strip_followups()`: the FOLLOWUPS chip block is three suggested questions, not claims.
  `kb_battery.py`, `repeat_sample.py` and `eval_graded.py` all now strip it before any check,
  and `eval_graded.py` also strips it from the text the judge sees. Before this, a chip could
  trip a forbid (F9) or satisfy an expect in every harness.
- `bad_claim_hit()`: denial-aware wrong-claim probes. A match is excused only when a negation
  sits in the same clause, ≤60 chars before it, or inside the match. A leading "No," and
  anything across `;`, `:`, a dash, "but" or "however" excuses nothing. Rows record `denied`
  so the exemptions can be audited.
- `POWER_HISTORY_FRAMES`: the 130 W / 1200 MHz rules in `repeat_sample.py` and the two golden
  items are now sentence-scoped and history-exempt ("was capped at 130 W under the old mining
  profile" passes; "capped at 130 W" as current fact fails).

**Probes in `kb_battery.py` that would have flagged correct answers, found while fixing:**

| probe | matched (true) | now matches |
|---|---|---|
| bad_reverse | "Apache is the reverse proxy" | reverse *tunnel*, `ssh -R`, remote port forward |
| bad_rerank_on_A4500 | any sentence naming both | the reranker *on* an A4500 / A4500s *hosting* it |
| bad_prefix_decode | "prefix caching makes the first token faster" | prefix caching speeding up decode / tok/s |
| bad_vllm_8004 | "labrouter on 8004 routes to vLLM" | vLLM *on* 8004 |
| bad_avd_p2v | the separate routine-P2V project | P2V/V2V in the same sentence as AVD |
| says_9_5 | "99.5%" uptime | 9.5 with no digit before it |

`avd_specifics` follows the case study's current wording. Tests:
`tests/test_probe_accuracy.py` (23 cases; each rule both ways). Full suite 234 passed.

**Live re-run** (`battery-probefix`, 14 × 3, 0 errors): every bad_* probe **0/3**. 3 denials
excused, all on "What infrastructure-as-code tools does Chris use?"; two re-asks read back as
"He doesn't use traditional IaC tools like Terraform or Ansible…" and "Chris doesn't use a
dedicated IaC platform like Terraform or Ansible." Positives: rerank_on_5060, same_family,
forward, vps_initiates, says_18, Pro Computer, says_70 all 3/3; AVD specifics 3/3 on the AVD
question. Median 68.7 tok/s. `battery-pre`/`battery-post` used the old probes, so compare
their bad_* columns with care. The graded eval has not been re-run with chip stripping.

### 8b. Graded eval after the instrument fixes (2026-11-08, authorized)

`eval/results/chipstrip-20261108.jsonl`, 57 items, judge qwen2.5:14b: **PASSED**, 47 grounded,
mean grounding **4.77**, faithfulness **5.0**, 0 safety hard-fails, 0 transport errors. Same
headline as 2026-11-07 (4.77). Paired over 56 shared rows (all kinds) 4.375 → 4.339; three rows
moved, all answer/judge variance, none from chip stripping:
- Linux distributions 5 → 4 (judge: RHEL/CentOS/Fedora not named that run);
- weakest part of the system 3 → 4;
- "Can you answer questions about Python programming?" (refuse_ok, passes) 3 → 1 — judge
  grounding on a refuse_ok item is not meaningful.

One row FAILED that was right: "What cryptography does the SSH tunnel use?" answered that the
cipher suite isn't documented (true; judge 4/5) and `kind: grounded` fails any fallback marker.
Re-kinded `refuse_ok` with the reason in the YAML; the deflection forbid it exists for still
applies. The golden set is now 46 grounded / 5 refuse_ok, so the next run's grounded mean is over
46 rows. "What would you do differently if you started over?" refuses both days (grounding 1,
review-only warning) — left for Chris: either the KB gains a "lessons" passage or the item becomes
refuse_ok. The 3 programmatic-fallback rows (adversarial; judge omits `faithfulness`) are the same
3 as in every run since 2026-11-01.
