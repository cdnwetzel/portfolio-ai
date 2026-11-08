# Major Infrastructure Projects — Overview

**Role:** Chris Wetzel — led or delivered each of the projects below. This page summarizes the
projects listed on cwetzel.com/projects, one section each, so that a broad question ("walk me
through a major infrastructure project", "what big projects has Chris done?") gets the right
project, and so that separate engagements are not blended together. Several have a longer case
study elsewhere in this knowledge base.

---

## SOC 2 Type II compliance program (at RedEye, the MSP — Jan–Dec 2022, with a colleague)

- Designed, executed, and managed the rapid transition of the MSP's infrastructure from standard
  engineering best practices to a fully compliant **SOC 2 Type II** framework within a rolling
  **90-day evaluation window**.
- Used **Secureframe** for continuous compliance monitoring and integrated all core on-premises
  and cloud environments, including M365, to build automated evidence streams.
- Authored and implemented **over 20 formal corporate information security policies**, closed
  existing governance gaps, and served as the **primary technical point of contact with the
  audit firm**.
- Outcome: **passed the SOC 2 Type II audit** (Chris and his colleague), which let RedEye retain a
  $3 billion (USD) finance client and helped it retain and win many more; continuous, auditable security
  operations across the multi-tenant MSP, without disrupting daily engineering output.

## Azure Virtual Desktop + SAP Business One for a global maritime medical-supply distributor (RedEye, Nov 2021 – Aug 2023, co-led with a colleague)

- Migrated **about 120 end users globally** from a **datacenter-hosted Citrix VDI environment on Windows
  Server 2012** to **Azure Virtual Desktop on Windows Server 2019 and Windows 10**.
- Deployed **multiple pooled AVD hosts** to suit different groups of users, including regional
  settings.
- Configured **both Azure and offsite image-based backups** for continuity.
- Results: migrated in **about 4 months**, in waves; **99.5%+ uptime** and **under 100 ms**
  latency worldwide; about **$200k** cost, **paid back in about 6 months** (about $155 per user
  per month saved against Citrix).
- Continued to document, maintain, and scale the environment to **200 end users around the
  globe**.
- The environment hosts the client's **SAP Business One (MSSQL back end)** with the **Boyum B1
  Usability Package** and **Produmex WMS**, used from desktops, laptops, and **handheld
  devices**.
- Brought **all global locations onto one SAP Business One system**: latency had previously
  forced a second, freestanding SAP instance in Australia, with inventory synced best-effort.
- Chris **deployed SAP Business One into the AVD environment**, including add-ons and handheld
  scanners. He was **not the SAP consultant**. The SAP + WMS project as a whole: about 8 months,
  50 → 200+ concurrent users, 95%+ faster queries, 99%+ inventory accuracy, about $229.5k a year
  saved (payback about 10.5 months).
- AVD and SAP Business One are the **same client**, not two projects. Full write-up:
  "Avd Sap Global Distributor".
- This was a VDI-to-cloud-desktop migration. The P2V (physical-to-virtual) work below is a
  separate set of projects.

## Graphic design studio: bare-metal macOS servers → VMware vSphere (2018, with a colleague)

- Planned, tested, and executed a multi-phase modernization: legacy bare-metal **macOS X
  Servers** → a highly available **Dell PowerEdge + EqualLogic SAN** stack running **VMware
  vSphere**, hosting Windows and Ubuntu Linux VMs.
- Staging and testing methodology for absolute data integrity of massive creative asset
  libraries; incremental data syncs and overnight cutovers that preserved file permissions and
  asset links, for near-zero downtime.
- Provided ongoing Tier 3 support, capacity planning, and optimization afterwards.

## Routine P2V and V2V consolidation (RedEye)

- Converting clients' physical and older virtual servers (P2V and V2V) was routine work across the
  MSP's client base, done to keep server footprint, electricity use and cooling lean.

## Standardized virtualization + BCDR for SMB clients

- Converted legacy setups across a diverse SMB client roster into standardized single-host
  **VMware ESXi** environments, each paired with a dedicated **BCDR appliance**, with a
  hybrid-cloud failover strategy that can virtualize critical workloads on-premises or in the
  cloud.
- Managed the end-to-end lifecycle: server virtualization, network configuration, backup
  synchronization.
- Image-based BCDR backups kept **onsite, offsite, and in a secondary offsite** location, for
  full DR compliance. Proven: a single-VM client could be spun up **within 5 minutes**, onsite or
  in the cloud. Backup images were boot-tested as VMs automatically every night, and any failure
  was remediated within 24 hours.

## Email migrations to Microsoft 365

- Migrated numerous client organizations from on-premises **Exchange Server** and **Google Apps
  (Workspace)** to **Microsoft 365**, with pre-flight domain validation, MX record cutovers and
  data staging for **zero email downtime or message loss**.
- Post-migration security: identity protection, **MFA**, and **DLP** in the M365 tenant.

## Gentoo Linux multi-machine deployment (2025 – present, personal / open source)

- Deployed Gentoo Linux across **4 laptops from 3 manufacturers** (Microsoft Surface Pro, MacBook
  Pro, Dell XPS 13, Dell XPS 15) with fully scripted, version-controlled kernel configurations.
- Built custom tooling: hardware profiler, static config validator, template generator and
  kernel config linter. **26-phase build process, 25 documented gotchas, 2 locally maintained
  kernel patches.** Open source: github.com/cdnwetzel/gentoo-machines. See "Gentoo Machines".

## Earlier milestone

- At MBNA America (2004): planned and deployed a **Windows NT → Windows 2000 migration with
  Altiris** to 7 Delaware offices.

## The AI portfolio system itself

- The self-hosted RAG chat at dev.cwetzel.com — owned GPUs, vLLM, Qdrant, a GPU reranker and an
  out-of-band faithfulness verifier. Described in "AI Portfolio System".
