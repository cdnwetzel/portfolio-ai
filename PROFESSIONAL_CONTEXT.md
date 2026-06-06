# Professional Context — Portfolio AI SaaS Foundation

**Based on:** cwetzel.com website review + LinkedIn profile  
**Date:** 2026-06-06  
**Purpose:** Ground the Portfolio AI SaaS in your real professional depth

---

## Your Professional Identity

**Title:** IT Manager + Senior Systems Engineer  
**Experience:** 26 years in enterprise infrastructure  
**Current Role:** IT Manager @ Portnoy Schneck LLC (Law Firm), Hamilton, NJ  
**Email:** cwe@thepslawfirm.com  
**GitHub:** cdnwetzel  

### Core Expertise Areas

#### 1. **Enterprise Infrastructure & Operations** (26 years)
- **Windows & Linux Servers:** 20+ years managing mixed environments (on-premises, Azure, AWS)
- **Virtualization:** VMware implementation, physical-to-virtual (P2V) migrations
- **Storage:** SAN/NAS technologies, disaster recovery, business continuity planning
- **Cloud Platforms:** Azure (AVD), AWS
- **Databases:** MSSQL (reporting, querying, optimization)

#### 2. **Security & Compliance** (Recent Focus)
- **SOC2 Type II Compliance:** Audits, environment hardening, documentation
- **Enterprise Security:** Firewall config, VPN access, encryption, anti-virus/spam
- **Backup & Disaster Recovery:** BDR solutions, tested failover, off-site backup rotation
- **Compliance:** IT policies, procedures, regulatory requirements

#### 3. **Automation & Scripting**
- **PowerShell:** Complex task automation, system administration
- **MSSQL:** Report generation, data-driven decision making
- **Web Technologies:** WordPress, OctoberCMS, PHP/HTML/CSS maintenance

#### 4. **Enterprise Applications**
- **Email Infrastructure:** Microsoft Exchange, Office 365 administration
- **ERP Systems:** SAP Business One (MSSQL-backed), Boyum B1, Produmex WMS
- **VDI:** Azure Virtual Desktop (AVD) environments, 200+ user deployments
- **Project Management:** Planning, implementation, ongoing support

---

## What This Means for Portfolio AI SaaS

### 1. Target Audience: Enterprise IT Leadership

Your ideal customers for this SaaS aren't startups—they're:

**Persona: IT Director/Manager**
- Budget: $500–$5k/month for AI tooling
- Pain Point: Document analysis at scale (compliance, contracts, policies)
- Use Case: Chat with regulatory documents, compliance guides, IT policies
- Example: "Analyze this contract against our SOC2 requirements"

**Persona: Consultant/Freelancer**
- Budget: $29–$99/month
- Pain Point: Rapid document review (contracts, proposals, compliance docs)
- Use Case: Chat with client contracts, policies, requirements
- Example: "Extract risk factors from this SaaS contract"

### 2. Natural Data Sources for RAG Pipeline

Your GitHub repos likely contain:
- Infrastructure as Code (Terraform, Ansible)
- PowerShell automation scripts
- System documentation
- Compliance playbooks
- Disaster recovery procedures

Your professional content should feed into the RAG:
- **Resume:** IT Manager background, 26-year depth
- **Experience:** Real enterprise projects (AVD migrations, SOC2, SAP)
- **Projects:** Specific implementations (SAN/NAS, Azure VDI scaling)
- **Certifications:** Any relevant IT certifications

**RAG Knowledge Base Sections:**
```
Portfolio AI for Chris Wetzel
├── About: IT Manager, 26 years enterprise infrastructure
├── Expertise: Windows/Linux servers, Azure, AWS, VMware, security, compliance
├── Current Role: IT Manager @ Law Firm
│   ├── Staff oversight
│   ├── Budget management
│   ├── IT projects & tech integration
│   ├── Cybersecurity programs
│   ├── Vendor management
│   ├── Policies & compliance
│   ├── MSSQL reporting
│   └── PowerShell automation
├── Projects:
│   ├── SOC2 Type II Compliance (environment hardening)
│   ├── Azure VDI Migration (120→200 users, global)
│   ├── VMware Infrastructure (P2V migrations)
│   ├── SAP Business One Integration (MSSQL backend)
│   ├── Disaster Recovery Planning (BDR, off-site backups)
│   └── Enterprise Email (Exchange, Office 365)
└── Skills: PowerShell, MSSQL, VMware, Azure, AWS, Linux, Windows Server
```

### 3. Demo Talking Points for Recruiters

When recruiters chat with your AI, they'll discover:

**Initial Query:** "What's Chris's experience?"  
**AI Response:** "Chris is an IT Manager with 26 years managing enterprise infrastructure..."

**Probing Query:** "How has he handled large-scale migrations?"  
**AI Response:** "He successfully migrated 120 users globally from datacenter VDI to Azure Virtual Desktop, scaling to 200 users with regional settings and image-based backups..."

**Specific Query:** "Does he know compliance?"  
**AI Response:** "Yes—he performed SOC2 Type II audits, environment hardening, and compliance documentation..."

**Hiring Manager Wow Moment:** Not just "IT Manager" on a resume—they're talking to an AI that *knows* your specific projects, your depth in Azure/AWS, your compliance expertise, your PowerShell skills.

---

## Integration Points with Portfolio AI SaaS

### 1. **Your Own Content → RAG Pipeline**

```
cwetzel.com pages → Markdown export → Qdrant vectors → RAG retrieval
├── Summary (intro + bullet points)
├── Experience (job descriptions, accomplishments)
├── Projects (major implementations, case studies)
├── Education (certifications, training)
└── LinkedIn (profiles, endorsements)

Additional sources:
├── GitHub public repos (code, documentation)
├── Resume (detailed CV)
├── Case studies (big projects broken down)
└── Certifications (IT security, cloud, etc.)
```

### 2. **Revenue Model: Law Firm Use Case**

Since you work at a law firm, you understand:
- Contract review (enterprise SaaS agreements, vendor NDAs)
- Regulatory compliance (GDPR, data privacy, SOC2)
- Document management (secure, auditable)
- Billing (usage tracking, monthly statements)

**SaaS positioning for law firms:**
- "AI-powered contract analysis"
- "Compliance documentation assistant"
- "Vendor agreement reviewer"
- Privacy-first (self-hosted, no external APIs, no data training)

**Your first customers could be:**
- Law firm colleagues (pilot users)
- IT consultants you know (compliance/infrastructure focus)
- Managed service providers (MSPs) who service enterprises

### 3. **Technical Credibility Stack**

Your Portfolio AI SaaS demonstrates:
- ✅ **Infrastructure knowledge** (runs on home GPU, WireGuard tunnel, self-hosted)
- ✅ **Security-first design** (no external APIs, row-level security, encryption)
- ✅ **Compliance-ready** (audit logs, data isolation, SOC2-aligned)
- ✅ **Enterprise-grade** (scalable, monitored, documented, disaster recovery)
- ✅ **AI literacy** (RAG, embeddings, LLM operations, cost optimization)

Recruiters at security-first companies (law firms, financial services, healthcare) will see: **"This engineer understands production infrastructure, compliance, and AI."**

---

## Updated PRD Positioning

### Problem Statement (Refined)
Enterprise IT leaders and lawyers spend hours manually reviewing contracts, policies, and compliance documents. Existing AI solutions use external APIs (privacy risk, cost, audit trail). This platform provides self-hosted, cost-efficient AI analysis for sensitive documents.

### Personas (Based on Your Background)

**Persona 1: IT Manager (Primary)**
- Role: Manages enterprise infrastructure, compliance, vendors
- Pain: Document review at scale (SOC2 audits, vendor contracts, policies)
- Budget: $500–$2k/month
- Success metric: "Reviewed 100 contracts in 10 hours instead of 40 hours"

**Persona 2: Consultant (Secondary)**
- Role: Advises clients on infrastructure, compliance, security
- Pain: Rapid analysis of client documents (contracts, RFPs, compliance docs)
- Budget: $29–$99/month
- Success metric: "Extracted risk factors from 50-page SaaS contract in 5 minutes"

**Persona 3: Law Firm Associate (Stretch)**
- Role: Contract review, due diligence
- Pain: Tedious document analysis, highlight key clauses
- Budget: $49–$199/month
- Success metric: "Identified red flags in contract before partner review"

### Use Cases (From Your Experience)

1. **Compliance Document Analysis**
   - "Chat with this SOC2 audit guide—what remediation steps apply to us?"
   - "Extract all GDPR requirements from this privacy policy"

2. **Contract Review**
   - "What are the penalties in this vendor agreement?"
   - "Does this SaaS contract include IP ownership of our data?"

3. **Infrastructure Knowledge Base**
   - "What's the process for migrating to Azure Virtual Desktop?"
   - "How do we plan disaster recovery for a 200-user VDI environment?"

4. **Policy Documentation**
   - "Chat with our IT policies—what's the process for approving new software?"
   - "What are our backup and retention requirements?"

---

## Knowledge Base Content Strategy

### Phase 1: Your Portfolio (MVP)
- Resume (detailed)
- All cwetzel.com pages (markdown)
- LinkedIn profile summary
- 3–5 case studies (SOC2, AVD migration, SAP integration)

### Phase 2: Supporting Content (Post-Launch)
- GitHub repos (code examples, documentation)
- Published articles/blogs (if any)
- Certifications and training materials
- Webinar/presentation content

### Phase 3: Enterprise Content (White-label)
- Generic compliance templates (SOC2, GDPR, etc.)
- Infrastructure design guides
- Disaster recovery playbooks
- Vendor evaluation criteria

---

## Why This Matters for the SaaS

Your background makes this **credible and useful:**

1. **You know the pain** — 26 years dealing with document overload
2. **You know the solution space** — Enterprise infrastructure, compliance, databases
3. **You know the buyer** — IT leaders, law firms, consultants
4. **You know the constraints** — Security, audit trails, cost, self-hosting
5. **You understand ROI** — Time saved = money saved (enterprise metric)

When a prospect sees "AI for compliance/contract analysis" + "built by IT Manager with 26 years experience" + "self-hosted, no API dependency," they *believe* it's built for them.

---

## Recommended Updates to Project Documents

### Update to `vision.md`
- Add: "For enterprise IT leaders and legal professionals managing documents"
- Add: "Self-hosted AI with SOC2-aligned security (no external APIs)"

### Update to `prd.md`
- Replace generic personas with IT Manager + Consultant + Lawyer
- Add use cases from your experience (compliance, contracts, infrastructure)
- Define success metrics that resonate with enterprise buyers

### Update to `architecture.md`
- Highlight: Row-level security (tenant isolation)
- Highlight: Audit logging (compliance requirement)
- Highlight: Self-hosted, no external API calls (security advantage)

### Update to `.cursorrules`
- Add: "Document every compliance-relevant decision"
- Add: "Treat security as feature-parity with functionality"
- Add: "Assume users are handling sensitive enterprise data"

---

## Next Steps for GATE 1 Planning

**When creating `prd.md`, include:**
1. Executive summary with IT Manager positioning
2. Real personas (from this analysis)
3. Real use cases (contracts, compliance, infrastructure)
4. Enterprise-grade success metrics

**When creating `architecture.md`, emphasize:**
1. Row-level security for multi-tenant isolation
2. Audit logging (compliance requirement)
3. Self-hosted, no external API dependency
4. Encryption in transit + at rest

**When creating `test-plan.md`, add:**
1. Security tests (RLS enforcement, data isolation)
2. Compliance tests (audit logs, retention)
3. Performance under compliance scenarios (large document indexing)

---

**This document should be referenced when creating GATE 1 planning documents to ensure they reflect your real professional depth and target the right buyers.**

---

**Current Status:** Professional context captured, ready for PRD/architecture refinement  
**Last Updated:** 2026-06-06
