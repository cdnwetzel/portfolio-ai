# Case Study: Virtualization Migration — High-Throughput Graphic Design Studio

**Role:** Chris Wetzel — planned, tested, and executed this migration, and provided ongoing support.

**From:** Legacy bare-metal macOS X Servers
**To:** Highly available Dell PowerEdge + EqualLogic SAN running VMware vSphere, hosting Windows and Ubuntu Linux VMs
**Outcome:** Near-zero operational downtime; creative asset libraries migrated with full data integrity and preserved file permissions and asset links

---

## The Problem

A high-throughput graphic design studio was running on aging, bare-metal macOS X Servers — no high availability, limited scalability, and massive creative asset libraries (the studio's core working capital) sitting on single points of failure. Any migration had to protect those libraries absolutely and avoid disrupting active production pipelines, where downtime directly halts billable creative work.

---

## The Target Architecture

A highly available, scalable virtualization stack replaced the legacy bare-metal servers:

- **Dell PowerEdge** servers + **EqualLogic SAN** for shared, resilient storage
- **VMware vSphere** hosting a mix of **Windows and Ubuntu Linux VMs**

This eliminated single points of failure and gave the studio room to scale and consolidate workloads.

---

## The Migration Methodology

The real risk wasn't the technology — it was the data. The plan was organized around protecting the creative asset libraries:

- **Rigorous staging and testing methodology** to guarantee absolute data integrity before anything moved in production.
- **Incremental data syncs** instead of a single bulk copy, keeping the cutover delta small and verifiable.
- **Iterative client-environment evaluations** at each phase to confirm the new environment behaved correctly before advancing.

Executed gradually across multiple phases, this kept operational downtime near zero throughout.

---

## The Cutover

Cutovers were run as **seamless, overnight** transitions to stay clear of production hours — and engineered around what breaks *silently* in a creative studio:

- **Complex file permissions** preserved end to end.
- **Localized asset links** (the references that tie creative files together) kept intact.

Active production pipelines came back the next morning with no broken links, no permission errors, and no re-linking scramble.

---

## Ongoing Support

After cutover, provided **Tier 3 support, capacity planning, and optimization** for the newly virtualized environment — tuning and scaling the stack as the studio's workloads grew.

---

## Why It Worked

- **Data integrity first** — the entire plan was built to never risk the asset libraries.
- **Gradual over big-bang** — incremental syncs plus iterative evaluations kept every step low-risk and reversible.
- **Preserve what silently breaks** — permissions and asset links are what derail creative-studio migrations; protecting them was treated as a primary requirement, not an afterthought.
