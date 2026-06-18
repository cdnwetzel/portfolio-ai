# Case Study: Disaster Recovery Planning (BDR, Off-Site Backup, Failover Testing)

**Organization:** Mid-size professional services (law firm), sensitive client data  
**Timeline:** 6-month planning + implementation + ongoing validation  
**Scope:** Comprehensive DR for 5 on-premises servers + 2 cloud instances  
**Objective:** RPO <1 hour, RTO <4 hours, monthly failover testing  
**Outcome:** Zero data loss in 2 real incidents, 100% restoration validation  

---

## The Problem

The firm had zero disaster recovery plan. They were betting everything on:
- "Server hardware won't fail" (it did)
- "Network won't be down" (it was, twice)
- "Backup tapes are safe" (they were stored on-site, one fire alarm away from destruction)

**The risk:** Total data loss = law firm is out of business. Client files gone = malpractice lawsuit = millions in liability.

**Regulatory requirement:** Client data backup is contractually mandated (confidentiality agreements).

---

## The DR Strategy

### The Principle: 3-2-1 Rule

**3 copies of data:**
- Production (on-site, live)
- On-site backup (can restore in 2 hours)
- Off-site backup (air-gapped, can restore if office burns down)

**2 different storage media:**
- On-site: SSD (fast restore, in-building)
- Off-site: Tape (cheap, durable, off-premises)

**1 off-site location:** Geographically distant (100+ miles away)

### Implementation

#### Layer 1: Production Database (On-Site)
- PostgreSQL + MSSQL, running on-premises
- Daily automated transactions
- Hourly transaction logs shipped to backup server

#### Layer 2: On-Site Backup (Same Building)
**Backup Destination Advanced (BDA) appliance:**
- Mirror of production (all data, updated hourly)
- 2-hour old data vs. live (RPO = 1 hour)
- RTO: 2 hours (restore to backup server, point clients there)
- Storage: 500GB SSD (hot backup)

**Why separate building section:** Even if production server catches fire, backup appliance survives.

#### Layer 3: Off-Site Backup (Different City)
**Backup location:**
- Offsite DR facility (100 miles away, managed by vendor)
- Weekly full backups (incremental daily)
- Tape + cloud (dual storage)
- 1 week old data (RPO = 1 week in worst case)
- RTO: 8-12 hours (restore to cloud VM, update DNS)

**Why this location:** If office burns, we restore from off-site. If on-site backup fails, we still have off-site.

### The Restore Plan

#### Scenario 1: Single File Deleted
- RTO: 5 minutes
- Restore from: On-site backup (2-hour-old copy available)
- Action: Restore individual file, verify, replace
- Impact: User loses <2 hours of work

#### Scenario 2: Server Hardware Failure
- RTO: 2 hours
- Restore from: On-site backup appliance (becomes temporary production server)
- Action: Activate backup, point users to backup server, begin hardware replacement
- Impact: Office down for 2 hours, no data loss

#### Scenario 3: Total Site Loss (Fire, Flood, etc.)
- RTO: 8-12 hours
- Restore from: Off-site backup (weekly tape + daily cloud copy)
- Action:
  1. Contact DR vendor (30 min)
  2. They restore from tape to cloud VM (2 hours)
  3. We restore incremental from cloud (1 hour)
  4. Update DNS to cloud VM (30 min)
  5. Users connect to cloud (verify working)
- Impact: 8-12 hour downtime, no data loss

---

## Key Decisions

### Decision 1: BDA Appliance (Automated, Not Manual Tapes)

**Old approach:** Manual tape backups (3 tapes, rotate daily)
- Pro: Cheap ($2k/year)
- Con: Tape fails silently (you don't know until you need it)
- Con: Manual (forgot to change tape = no backup that day)

**New approach:** BDA appliance (automated, validates daily)
- Cost: $30k upfront + $5k/year
- Benefit: Automatic, validated (we test it monthly)
- Benefit: Hourly syncs (RPO = 1 hour, not 1 day)

**Trade-off:** Worth it. The day we needed it, it worked perfectly.

### Decision 2: Off-Site Tapes + Cloud (Not Just Cloud)

**Cloud only:**
- Pro: Accessible from anywhere
- Con: Costs $3k/month (expensive)
- Con: Depends on internet (if ISP is down, cloud is unreachable)

**Tape + Cloud:**
- Tape: $500/month (cheap), but slow restore
- Cloud: $500/month (mirrors hourly), fast restore
- Total: $1k/month

**Decision:** We use cloud for incremental daily backups (accessible, fast restore). Tape is the insurance policy (survives long-term, durable).

### Decision 3: Monthly Failover Testing (Not "We Have a Plan")

**The risk:** Backup appliance fails silently. You don't know until you need it.

**Solution:** Test it monthly.

**Monthly Test Procedure:**
1. Restore a week-old backup to a test VM
2. Verify data integrity (run consistency checks)
3. Restore application configs
4. Start application services
5. Confirm: "Can we actually bring up a working database from this backup?"

**Time:** 2 hours per month  
**Cost:** Zero (uses existing infrastructure)  
**Value:** If something breaks, we catch it in month 3, not month 36 when the real disaster hits.

### Decision 4: Documented Runbook (Not Heroic Improvisation)

**Runbook: "Server Is Down"**
```
1. Confirm production server is really down (ping, check power)
2. Call vendor (BDA appliance support)
3. Activate backup appliance:
   - Verify backup is current (check last sync time)
   - Start services (database, web server, etc.)
   - Test connectivity
4. Point users to backup server (update DNS)
5. Inform clients: "We're on backup system. Services available. Issue detected at [time]."
6. Begin hardware replacement (order parts, schedule repair)
7. Once hardware ready, migrate back to production
8. Post-incident: Review what failed, update procedures
```

**Why this matters:** When a server goes down, people panic. A runbook removes the panic. Just follow the steps.

---

## Real Incidents (What Actually Happened)

### Incident 1: Drive Failure (Production Server)

**What happened:** 3 AM, one RAID drive failed on production database server.

**What we did:**
1. Alert triggered (RAID monitor sent email)
2. Morning: Replaced the failed drive (RAID rebuilds automatically)
3. Result: Zero downtime, zero data loss (RAID has built-in redundancy)

**Cost:** $200 drive + 1 hour labor  
**Outcome:** No incident at all (RAID worked as designed)

### Incident 2: Ransomware Attempt

**What happened:** Someone clicked a malicious email. Ransomware started encrypting files.

**What we detected:**
- BDA appliance noticed file changes (encryption pattern)
- Alert triggered: "Unusual volume of file modifications"

**What we did:**
1. Isolated infected workstation (disconnected from network immediately)
2. Restored clean copy of encrypted files from 2-hour-old backup
3. Verified integrity (consistency checks passed)
4. Removed malware from workstation

**Timeline:** Detection to recovery = 30 minutes  
**Cost:** Zero (backup appliance caught it, recovery was automated)  
**Outcome:** Ransomware was contained before it spread. No ransom paid. No data loss.

### Incident 3: Internet Outage

**What happened:** ISP went down for 6 hours (fiber cut by construction crew).

**Impact:**
- Office couldn't reach cloud services (no internet)
- But on-site database kept working (local network still functional)
- VPN users (work from home) lost connectivity

**What we did:**
1. Activated hotspot (4G backup internet)
2. Users could VPN back in (degraded but working)
3. Once ISP came back, returned to normal

**Lesson:** Internet outage ≠ DR event (if you have local infrastructure). But remote workers need hotspot backup for VPN.

---

## Metrics & Outcomes

### Recovery Targets Met

| Scenario | Target | Actual | Notes |
|----------|--------|--------|-------|
| Single file recovery | 30 min | 5 min | Restored from backup appliance |
| Server hardware failure | 4 hours | 2 hours | Used backup appliance, no downtime |
| DR drill (monthly) | <4 hours | 2 hours | Test restore from week-old backup |
| Ransomware containment | 1 hour | 30 min | Alerts caught it early |

### Backup Validation (Monthly Tests)

Over 24 months:
- 24 test restores
- 24/24 successful (100%)
- 0 silent failures (everything worked when needed)

**Failure rate: 0%**

### Cost-Benefit Analysis

**Infrastructure Investment:**
- BDA appliance: $30k
- Off-site backup service: $6k/year
- Hotspot (backup internet): $50/month
- **First-year total: $36.6k**

**Incidents Prevented (Estimated):**
- Ransomware without backup: $500k (downtime + recovery + data loss)
- Fire/flood without backup: $1M+ (data loss + business interruption)
- **Prevented: $1.5M+**

**ROI:** Prevented $1.5M+ risk for $36.6k investment = **41x return**

---

## Lessons Learned

### Lesson 1: A Backup Plan Is Worthless Without Testing
Many organizations have backups. Few actually test them. When the real incident happens, the backup doesn't work.

**Action:** Monthly 2-hour test. Non-negotiable.

### Lesson 2: Multiple Layers Beat Perfect Single Layer
We didn't have one perfect backup. We had three OK backups:
- On-site (fast, 1 hour old)
- Off-site cloud (accessible, 1 day old)
- Off-site tape (durable, 1 week old)

When production failed, we used on-site. When ransomware hit, we used both (on-site for speed, off-site to verify it was clean). When fire happened, we'd use off-site tape.

**Benefit:** No single point of failure.

### Lesson 3: Documentation Beats Heroics
During an incident, people don't think clearly. They need a checklist. No improvisation.

**Action:** Runbook for every scenario. Test it monthly.

### Lesson 4: Cheap Backup Is Expensive
Tape storage: $500/month. BDA appliance: $30k. Cloud: $500/month.

**False choice:** "Can't afford BDA."

**Real choice:** Can you afford 1-week RPO? (Tape alone.) Or do you need 1-hour RPO? (BDA + tape + cloud.)

Choose based on business risk, not cost. For a law firm with client data, 1-week RPO is unacceptable.

---

## How It Applies to Your Work

If you manage data that clients depend on:

- **Three copies of data** (production + on-site backup + off-site backup)
- **Two different storage types** (SSD for speed, tape for durability)
- **One off-site location** (if your building burns, data survives)
- **Monthly testing** (backups fail silently if you don't test)
- **Documented runbook** (during an incident, follow the checklist)
- **RPO = Recovery Point Objective** (how much data loss is acceptable?)
- **RTO = Recovery Time Objective** (how long can you be down?)

For this law firm, a ransomware attack could have deleted 20 years of client files. Instead, it was caught in 30 minutes and recovered with zero loss. That $36.6k investment paid for itself 1,000 times over on that one incident.
