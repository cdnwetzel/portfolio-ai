# Case Study: Azure Virtual Desktop and SAP Business One for a Global Maritime Medical-Supply Distributor

**Role:** Chris Wetzel — **co-led this work with a RedEye colleague** while he was a Senior
Engineer at RedEye, Inc. (MSP), where the client was a RedEye customer.

**Dates:** November 2021 – August 2023: the migration, then documenting, maintaining and scaling
the environment until Chris left RedEye in August 2023.

**One client, two systems.** The Azure Virtual Desktop (AVD) environment and the SAP Business One
system are the **same client**: the AVD environment is what the client's users run SAP Business
One and its warehouse software on. They are not separate engagements.

---

## The client

A **global distributor of medical supplies, pharmaceuticals, medical equipment and telemedicine
services to the maritime and offshore industries**: commercial shipping fleets, cruise lines,
leisure vessels, offshore oil and gas rigs, and humanitarian operations. Its services include
compliance consulting (helping ships meet international maritime health regulations), oxygen
distribution, medical kits, and 24/7 remote health support.

It is **headquartered in New Jersey**. At the time of the project (2021–2023) it ran **6
warehouses on 4 continents**:
- **North America (2):** New York City, Miami
- **Europe (2):** London, Athens
- **Asia (1):** Singapore
- **Oceania (1):** Sydney

That spread is why its users were around the globe, and why latency mattered.

The client is not named here.

---

## What was done

**The migration.** Moved **about 120 end users globally** off a **datacenter-hosted Citrix VDI
environment built on Windows Server 2012** and onto a modern **Azure Virtual Desktop environment
built on Windows Server 2019 and Windows 10**.

**The design.**
- **Multiple pooled AVD host pools**, set up to suit the needs of different groups of users,
  including **regional settings** for users in different countries.
- **Backups in two places:** both **Azure** backups and **offsite image-based backups**, to
  ensure continuity.

**How it was rolled out.** The migration itself took **about 4 months**, moving users over in
waves rather than all at once, so problems surfaced with a small group before they could affect
everyone.

**After the migration (to August 2023).** Continued to document, maintain and scale the
environment, from about 120 to **200 end users located around the globe**.

## What the environment runs

The AVD environment is the client's scalable, global platform for its line-of-business systems:

- **SAP Business One**, on an **MSSQL** back end
- **Boyum B1 Usability Package** (an add-on for SAP Business One)
- **Produmex WMS** (warehouse management for SAP Business One)

It serves **user desktops and laptops, as well as handheld devices**.

## Results

- **99.5%+ uptime**
- **Under 100 ms latency** for users around the world
- **Cost and payback:** the project cost about **$200k**. Against the old Citrix environment it
  saved about **$155 per user per month**, so it **paid for itself in about 6 months**.

## The SAP Business One project — and Chris's part in it

**Chris was not the SAP consultant.** The SAP Business One work itself was done by the client's SAP
consultant. Chris's part was the platform: he **deployed SAP Business One into the Azure Virtual
Desktop environment, including its add-ons (Boyum B1 Usability Package, Produmex WMS) and the
handheld scanners**.

Results of the SAP Business One + Produmex WMS project as a whole:
- **About 8 months**, from planning through stabilization
- Scaled from **50 to 200+ concurrent users**
- **95%+ improvement in query performance**
- **99%+ inventory accuracy**
- About **$229.5k per year** saved, **paying back in about 10.5 months**

## One SAP system for every location

Before AVD, latency kept the client's **Australian operation on a second, freestanding SAP
Business One instance**, with inventory synced to the main system on a best-effort basis. Running
SAP Business One inside the Azure Virtual Desktop environment **brought all global locations into
the same system** — one SAP instance, one inventory, and no more best-effort syncing between two.

## Why it matters

A distributor with warehouses on four continents needs its ERP and warehouse system
to behave the same everywhere. Putting SAP Business One, Boyum and Produmex behind one Azure
Virtual Desktop environment gives every site the same desktop and the same systems, backed up in
two places, and it grew from about 120 to 200 users while Chris and his colleague ran it.

---

**Not documented here:** the names of the Azure regions used. If you are asked for those, say they are not documented rather
than estimating.
