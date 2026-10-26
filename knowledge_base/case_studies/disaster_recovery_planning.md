# Case Study: Standardized Virtualization + BCDR for SMB Clients

**Role:** Chris Wetzel — engineered, deployed, and managed the end-to-end lifecycle of these rollouts.

**Context:** A diverse SMB client roster (managed-services)
**Architecture:** Single-host VMware ESXi + a dedicated BCDR appliance per client, with hybrid-cloud failover
**Outcome:** Enterprise-grade business continuity, rapid recovery times, and data protection — within a minimal physical and financial hardware footprint

---

## The Problem

SMB clients typically run legacy, non-resilient setups, yet they need enterprise-grade business continuity — without enterprise budgets or rack space. The challenge was delivering real BCDR (instant failover, fast recovery, data protection) repeatably across a *diverse* client roster, on a minimal physical and financial footprint per site.

---

## The Standardized Footprint

Rather than bespoke builds per client, the work engineered a standardized, highly resilient virtualization footprint and deployed it across the roster:

- Converted legacy setups into efficient **single-host VMware ESXi** environments.
- Paired each deployment with a **dedicated Business Continuity and Disaster Recovery (BCDR) appliance**.

Standardizing the footprint made it repeatable, supportable, and consistent across a varied set of SMB environments.

---

## The Hybrid-Cloud Failover Strategy

Architected a robust hybrid-cloud failover strategy capable of **instantly virtualizing critical workloads both on-premises and in the cloud**. If the primary host fails, the BCDR appliance brings workloads back up locally; if a site is lost entirely, those workloads fail over to the cloud — enterprise-grade resilience on an SMB footprint.

---

## End-to-End Lifecycle

Managed the full lifecycle of each rollout:

- **Server virtualization** — converting legacy hardware into ESXi-hosted VMs
- **Network configuration**
- **Backup synchronization** — keeping the BCDR appliance and cloud copies current so failover targets are always recent

---

## Outcome

Delivered **enterprise-grade business continuity, rapid recovery times, and data protection** — within a **minimal physical and financial hardware footprint** per client: a repeatable resilience standard across the SMB roster, not a one-off build.

---

## Why It Worked

- **Standardize, then scale** — one resilient footprint deployed repeatably across a diverse roster beats bespoke builds.
- **Virtualization + BCDR as a pair** — single-host ESXi paired with a dedicated BCDR appliance turns a fragile legacy box into an instantly recoverable workload.
- **Hybrid failover** — on-premises for speed, cloud for full site loss — enterprise resilience without enterprise hardware.
