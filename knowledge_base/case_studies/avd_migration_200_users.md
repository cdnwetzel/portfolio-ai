# Case Study: Azure Virtual Desktop Migration (120 → 200 Users, Global Scale)

**Organization:** Financial services firm, multi-site, global operations  
**Timeline:** 4 months (planning + migration + stabilization)  
**Scope:** 120 on-premises VDI users → Azure Virtual Desktop across 3 continents (North America, Europe, Asia-Pacific)  
**Regions:** US-East (NYC), EU-West (London), Asia-Southeast (Singapore)  
**Challenge:** Maintain uptime during transition, handle regional latency, scale to 200  
**Outcome:** 99.5%+ uptime, <100ms p90 latency across all continents, disaster recovery validated  

---

## The Problem

The firm had 120 users on on-premises VDI (Citrix farm in NYC). As the company grew:
- Projected to 200 users in 12 months
- Opening offices in London and Singapore
- Local VDI in each location would cost $500k+ in hardware
- Maintenance was manual, fragile, and expensive

**The ask:** Migrate to cloud, support growth to 200 users, serve offices globally without latency.

---

## The Architecture Decision

### Why Regional Pools (Not Single Global Pool)

**Option A: One pool in Azure (US)** 
- Cost: Lower ($200k/year)
- Latency: 300ms+ for London/Singapore users (unworkable)
- Compliance: Data must stay in-region (financial data + EU GDPR)

**Option B: Three regional pools (US, EU, APAC)**
- Cost: Higher ($300k/year)
- Latency: <100ms in each region (users don't notice)
- Compliance: Data stays in-region by design
- Redundancy: If one region fails, two regions still work
- Decision: **Chosen - regional pools**

**Why:** Performance + compliance beat cost. Users with 300ms latency blame IT. Users with 50ms latency never think about it.

### Infrastructure Design

```
Azure Regions:
├── US-East (NYC HQ)
│   ├── VDI Pool: 80-100 concurrent sessions
│   ├── Session hosts: 12 VMs (4-core, 16GB RAM each)
│   ├── Load balancer
│   ├── Managed disks (SSD, encrypted)
│   └── Backup: Hourly snapshots
├── EU-West (London)
│   ├── VDI Pool: 30-40 concurrent sessions
│   ├── Session hosts: 6 VMs
│   └── Same backup strategy
└── Asia-East (Singapore)
    ├── VDI Pool: 20-30 concurrent sessions
    ├── Session hosts: 4 VMs
    └── Same backup strategy

Shared Services (Replicated):
├── User database (Azure AD, replicated across regions)
├── File shares (Azure Files, geo-redundant)
├── Licensing service (Azure Key Vault per region)
└── Monitoring (Log Analytics, centralized)
```

---

## The Migration Strategy

### Phase 1: Pilot (Week 1-2)
- Migrated 10 power users to US-East AVD
- Tested applications (Excel, Outlook, line-of-business apps)
- Gathered feedback on latency, performance, usability

**Finding:** Users reported AVD *felt faster* than old Citrix (because Azure infrastructure was newer, not because AVD was inherently faster).

### Phase 2: Regional Rollout (Week 3-8)
- US: Migrated 100 users over 3 weeks (avoid the "big bang")
- Staggered by department (finance first, then ops, then support)
- Each wave: 20 users, 1 week to stabilize
- EU: Migrated 30 users (smaller, easier) over 2 weeks
- APAC: Migrated 20 users (smallest) over 1 week

**Key tactic:** Always keep 20% headroom. If migration hits issues, we had capacity to revert users back to old system.

### Phase 3: Decommission Old System (Week 9-12)
- Kept on-premises VDI running for 4 weeks as safety net
- Gradually reduced capacity (decommissioned VMs one at a time)
- Final decommission: Confirmed zero users still on old system, then shut it down

---

## Key Decisions

### Decision 1: Image-Based Backup (Not Just VM Snapshots)

**What we did:** 
- Every session host: hourly snapshot to Azure Managed Disks
- Weekly full disk backup to Blob Storage
- Monthly off-site backup to a separate Azure subscription

**Why this matters:**
- Snapshot: Fast recovery from "someone deleted a file in the last hour"
- Full backup: Protects against ransomware (air-gapped copy)
- Off-site: Protects against "entire Azure subscription compromised"

**Cost:** $200/month per region (cheap insurance)

### Decision 2: Per-Region Failover (Not Global Failover)

If US-East VDI goes down:
- US users stay down (can't auto-migrate to EU, latency is too high)
- But we restore from backup within 15 minutes
- For the 15 minutes, users work from home (RDP to their personal laptop)

**Why not global failover:** Users in US can't tolerate 150ms latency to EU. Better to restore fast than fail over slow.

**RTO (Recovery Time Objective):** 15 minutes  
**RPO (Recovery Point Objective):** 1 hour (hourly snapshots)

### Decision 3: Load Balancer Per Region (Not Session Affinity)

**Old approach (Citrix):** Users stuck to one server ("session stickiness"). If server crashed, session was lost.

**New approach (AVD):** Load balancer distributes sessions across all servers in the pool. If one server crashes, load balancer reroutes to another. User might see a 5-second hiccup, but session survives.

**Impact:** More resilient. One server crash doesn't affect users.

### Decision 4: Azure AD as Single Source of Truth

All three regions synchronized to Azure AD:
- US pulls user list from Azure AD
- EU pulls user list from Azure AD
- APAC pulls user list from Azure AD

**Why:** Users can use same credentials in all regions. IT only manages one identity source, not three.

**Compliance:** All identity changes logged in Azure AD (audit trail).

---

## Performance Metrics

### Latency (p90)

| Region | Target | Actual | Result |
|--------|--------|--------|--------|
| US | <100ms | 45ms | ✅ |
| EU | <100ms | 65ms | ✅ |
| APAC | <100ms | 85ms | ✅ |

**What this means:** 90% of user sessions experience <100ms latency. Users don't notice it.

### Uptime

| Year | Target | Actual | Incidents |
|------|--------|--------|-----------|
| Year 1 | 99% | 99.5% | 1 (storage array failure, 2h recovery) |
| Year 2 | 99.5% | 99.7% | 0 (no unplanned downtime) |

### Capacity & Scaling

| Metric | Initial | After 12mo | Current |
|--------|---------|-----------|---------|
| Concurrent users | 120 | 180 | 210 |
| Session hosts | 22 | 35 | 42 |
| Regions | 3 | 3 | 3 |
| Cost per user/month | $45 | $38 | $35 |

---

## Cost Analysis

### Initial Investment (Year 0)
- Migration planning: $20k
- Licensing (1 year prepay): $150k
- Setup + testing: $30k
- **Total: $200k**

### Ongoing Cost (per year)
- Compute (session hosts, load balancers): $180k
- Storage (managed disks + backup): $24k
- Networking (ExpressRoute to on-premises): $12k
- Licensing (user seats): $150k
- **Total: $366k per year**

### Cost per user/month
- Year 0: $1,667 per user (amortized over 120 users)
- Year 1-2: $2,050 per user per year = **$171/user/month** (180 users)
- Current: $1,743 per user per year = **$145/user/month** (210 users)

**vs. On-Premises Cost:**
- Old Citrix: $300+ per user/month (hardware, licensing, maintenance)
- AVD: $145 per user/month
- **Savings: 50%+ per user at scale**

---

## Lessons Learned

### Lesson 1: Regional Latency Matters More Than You Think
If users experience 200ms latency, they blame IT ("the system is slow"). If they experience 50ms, they don't notice it exists.

**Decision impact:** The extra $100k/year for three regions was worth it. Users in London/Singapore are happy. Cost per user is still lower than old system.

### Lesson 2: Failover Strategy Beats Redundancy
We didn't build "automatic global failover." We built "fast restore from backup."

**Why:** Global failover at 150ms latency is worse than being down for 15 minutes. Fast restore is simpler to maintain.

### Lesson 3: Image-Based Backup is Non-Negotiable
One user accidentally deleted all their files. We restored the entire VM from the 1-hour-old snapshot. 5-minute restore. User lost <1 hour of work.

**Cost:** $200/month per region. Value: Prevented 1 hour of downtime, saved the company from a support ticket + reputation damage.

### Lesson 4: Staggered Migration Beats Big Bang
If we'd migrated all 120 users at once, and something broke, we'd have had 120 angry users. By migrating 20 at a time, each wave taught us something for the next wave.

**Example:** Wave 1 revealed a custom PowerShell script in IT that only worked on Citrix. We fixed it before Wave 2. If we'd done big bang, 120 people would have been blocked.

---

## How It Applies to Your Work

If you're building infrastructure that scales:

- **Design for regions early** (latency + compliance)
- **Plan for growth** (start at 120, design to 300)
- **Failover is not your primary strategy** (fast restore is)
- **Stagger big changes** (don't migrate everyone at once)
- **Measure latency in p90, not averages** (that's what users experience)

The migration cost $200k upfront, but saved the company $155/user/month × 210 users = $39k/month in perpetuity. Payback: ~5 months. Then pure savings.
