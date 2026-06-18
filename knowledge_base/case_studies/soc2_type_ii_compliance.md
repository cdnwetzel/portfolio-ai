# Case Study: SOC2 Type II Compliance Audit

**Organization:** Professional services firm, 40+ staff  
**Timeline:** 6-month audit engagement, ongoing validation  
**Scope:** IT infrastructure, access controls, data security  
**Outcome:** Passed SOC2 Type II audit; enabled enterprise partnerships  

---

## The Problem

The firm wanted to expand partnerships with enterprise clients who require SOC2 Type II certification. Without it, doors were closed. With it, new revenue opportunities unlocked.

But SOC2 isn't just a checkbox. It requires continuous validation across seven categories: security, availability, integrity, processing accuracy, confidentiality, and privacy.

**The gap:** We had decent security practices, but they weren't *documented*, *consistent*, or *auditable*. An auditor needs to see: "Here's the policy, here's the evidence it's being followed, here's how we prove it every month."

---

## The Approach

### Phase 1: Assessment (Month 1)
**Action:** Walk through every system and ask: "Could an auditor verify this?"

Findings:
- Database passwords stored in plaintext config files ❌
- Access logs scattered across multiple systems, no centralized audit trail ❌
- No formal change control process ❌
- Backup procedures undocumented ❌
- No evidence of monthly security reviews ❌

**Decision:** Build the system for auditing first, security second. Easy to audit = easy to maintain.

### Phase 2: Infrastructure Hardening (Months 2-3)

**Access Control:**
- Implemented role-based access control (RBAC)
- Removed shared admin accounts (service accounts instead)
- Multi-factor authentication (MFA) mandatory for all remote access
- Documented every access level and business justification

**Data Encryption:**
- TLS 1.2+ for all network traffic
- PostgreSQL encryption at rest (pgcrypto)
- Database backups encrypted with 256-bit AES
- Documented encryption key management (rotation schedule, backup)

**Audit Logging:**
- Centralized syslog server (all systems log to it)
- Every authentication attempt logged (success and failure)
- Every database query logged with user context
- Every privileged command logged (sudo, administrative actions)
- Log retention: 12 months minimum, immutable (no deletion)

**Change Control:**
- Every change requires approval + documentation
- Change log: who made it, when, what, why, business justification
- Tested in non-production first
- Rollback procedure documented

### Phase 3: Documentation (Month 4)

SOC2 auditors live on evidence. Created:

1. **IT Security Policy** (10 pages)
   - Access control procedures
   - Password requirements (length, complexity, rotation)
   - MFA requirements
   - Remote access protocols
   - Incident response process

2. **Operational Procedures** (15 pages)
   - Backup procedure (daily automated, weekly full, monthly off-site)
   - Backup restoration testing (monthly validation)
   - Patching schedule (monthly security updates, emergency procedure)
   - Change control process
   - Incident response (detection, containment, eradication, recovery)

3. **Data Classification Guide**
   - What data is sensitive (PII, financial records, legal docs)
   - Who can access what (job title based)
   - How it's protected (encryption, access controls, audit logging)

4. **Risk Register**
   - Identified 12 risks (e.g., "employee with access leaves company")
   - For each: mitigation strategy and owner
   - Reviewed quarterly

### Phase 4: Monthly Validation (Months 5-6 and Ongoing)

Built a monthly audit checklist:

- [ ] Review all access grants/revokes from past month (were they approved?)
- [ ] Spot-check 10 random logs (are they capturing what we said they would?)
- [ ] Test backup restoration (can we recover?)
- [ ] Verify MFA is enforced (are there any exceptions? why?)
- [ ] Review changes (were all approved? were all tested?)
- [ ] Scan for unpatched systems (is security update schedule followed?)
- [ ] Check for default credentials (any admin passwords unchanged?)
- [ ] Verify encryption keys are stored safely

**Owner:** Same person every month (continuity).  
**Time:** 2-3 hours per month.  
**Proof:** Dated evidence file (screenshot of audit results, log of checks, notes on anything unusual).

### Why Monthly: The 90-Day Rolling Lookback

SOC2 Type II (unlike Type I) isn't a snapshot — auditors sample a continuous **90-day rolling window** of evidence. Each new day enters the window; each day older than 90 drops off. The hard implication: **you can't retroactively fix a control failure from 91 days ago** — the control has to actually work, every day, throughout the period. That's exactly why the monthly review matters: drift caught on day 20 is fixable; the same drift discovered at audit time, 91 days later, is an audit finding. Weekly evidence collection plus the monthly internal review keep the rolling window clean.

---

## Key Decisions

### Decision 1: Centralized Logging (Not Local Logs)
- **Why:** Auditors need one source of truth. If each system keeps its own logs, attackers could delete logs from the system they compromised.
- **How:** Syslog server in a protected DMZ. All systems forward logs. Server accepts logs but systems can't delete them.
- **Benefit:** If someone breaches a database server, we can still prove it because the logs are on a different system.

### Decision 2: Immutable Logs (Append-Only)
- **Why:** Auditors verify "this happened on this date." If logs can be deleted or edited, the audit trail is broken.
- **How:** Logs stored in a database with INSERT-only permissions. No UPDATE, no DELETE.
- **Benefit:** Three years later, auditor asks "did this access happen?" We have proof.

### Decision 3: Monthly Manual Review (Not Just Automation)
- **Why:** Automated systems are great, but they can be misconfigured. Manual review catches "we thought we were doing X, but actually we're doing Y."
- **How:** One person, same day every month, spot-checks logs + procedures.
- **Benefit:** Catches drift. Example: "MFA should be on all admin accounts, but I notice dev1 doesn't have it. Why?" Prevents compliance creep.

### Decision 4: Documented Exceptions (Not Zero-Trust)
- **Why:** SOC2 expects "here's the policy" AND "here's where we break the policy and why."
- **How:** Risk register + approval. Example: "VPN access requires MFA, except for the backup system because it doesn't support MFA. Risk: if backup account is compromised, attacker can restore data. Mitigation: backup system is air-gapped, never connected to production network."
- **Benefit:** Auditor sees: you know the risk, you documented it, you mitigated it.

---

## Outcomes & Metrics

**Audit Result:** Passed SOC2 Type II (Year 1)  
**Timeline to Pass:** 6 months of work  
**Cost:** ~$15k (3x80 hours internal work + $3k audit fee)

**Business Impact:**
- Unlocked partnerships with 5 enterprise clients (previously required SOC2)
- Contract values: $50k-$150k per year
- Revenue impact (first year): $200k+
- ROI: 13x return on the $15k investment

**Operational Impact:**
- Monthly compliance work: 2-3 hours
- Zero compliance incidents in past 2 years
- Quick incident response (because everything is documented + auditable)
- Easy onboarding for new IT staff ("here's how we do it, here's the proof")

---

## Lessons Learned

### Lesson 1: Compliance is Continuous, Not a Project
Most organizations do the audit, pass, then relax. Six months later, they've drifted.

**What we do:** Monthly 2-hour review. Keeps it fresh. When the next audit comes, we're not scrambling—we've been doing it all along.

### Lesson 2: Document the Exception, Not Just the Rule
"We don't allow shared admin accounts" is the rule. "Except for the backup system because it doesn't support individual logins. Mitigation: it's air-gapped and monitored." That exception + mitigation is what auditors actually want to see.

**Impact:** Moved from "zero exceptions = safe" to "documented exceptions = understandable."

### Lesson 3: Immutability Beats Encryption
You can encrypt logs and still delete them. You can make them immutable and still recover them in 5 seconds.

**What we changed:** Stopped encrypting logs as a primary control. Made them immutable instead. Encryption is still there, but immutability is the security layer.

### Lesson 4: Audit Trails Are Cheap Insurance
One year, a hacker got into an employee email account and changed forwarding rules. We caught it in 12 hours because the audit log showed "forwarding rule created from IP 5.5.5.5 at 2 AM" (employee was asleep).

**Cost of that detection:** $0 (logs already existed).  
**Value:** Caught breach before damage was done.

---

## How It Applies to Your Work

If you're building something customers trust with data (SaaS, compliance tool, managed service):

- **Document your security model early** (don't bolt it on later)
- **Make everything auditable** (logs, access, changes)
- **Test your audit process monthly** (not just at audit time)
- **Document exceptions explicitly** (risk register approach)
- **Automate what you can, review what you can't**

The firm went from "we're secure, probably" to "we can *prove* we're secure." That's worth millions in B2B revenue.
