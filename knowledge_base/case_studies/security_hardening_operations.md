# Security Hardening & Continuous Testing: Operational Controls

**Role:** Chris Wetzel — designed and ran these security-hardening operations for clients in **regulated industries**: mortgage, title and real estate firms, medical and dental practices (doctors and endodontists), law firms, pharmaceutical companies, and social work and family services organizations — and for RedEye's own SOC 2 Type II program (2022).

This page describes the controls and the testing and corrective-action discipline. It does not record specific incidents, findings or dates.

## Overview

Security hardening is not a one-time configuration. It's an **operational discipline** combining:
- **Proactive configuration hardening** (disable weak protocols, remove defaults)
- **Active patching** (timely updates to close vulnerabilities)
- **Continuous testing** (monthly internal pen tests, external cadence 3-12 months)
- **Corrective action workflows** (find issue → fix → verify → document)
- **Principle of least privilege** (every access, every port, every setting justified)

Chris has supported **compliance audits for NIST (DoD), FINRA, HIPAA, PCI and SOC 2**. The same controls carry across all of them and across the regulated industries above. The requirements overlap; the discipline is the same.

## Core Hardening Controls

### TLS/SSL Encryption

**Control:** All data in transit is encrypted with strong cryptography

**Implementation:**
- **Minimum TLS 1.2**, preferred 1.3
- **Disabled weak protocols:** SSL 3.0, TLS 1.0, TLS 1.1 (legacy systems only with compensating controls)
- **Cipher suite configuration:** Enforce only strong ciphers
  - ✓ Allowed: TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384, TLS_CHACHA20_POLY1305
  - ✗ Blocked: DES, RC4, MD5, anon (anonymous key exchange)
- **Certificate management:**
  - Valid certificate for every domain
  - Certificates renewed before expiration (monitored with alerts at 30 days, 14 days, 7 days)
  - Certificate pinning for sensitive APIs (prevent MITM via compromised CAs)
- **HSTS (HTTP Strict Transport Security):** Enabled on all web applications
  - Header: `Strict-Transport-Security: max-age=31536000; includeSubDomains`
  - Forces browsers to HTTPS-only for 1 year
  - Prevents downgrade attacks

**Evidence auditors check:**
- Current certificate details (validity, issuance, renewal schedule)
- Cipher suite configuration (screenshot/config file)
- TLS version enforcement (SSL Labs test or similar)
- HSTS header presence (browser developer tools)
- Certificate renewal logs (evidence of proactive renewal before expiration)

### Certificate Management & Currency

**Control:** All certificates are valid, current, and monitored

**Process:**
- Inventory of all certificates (where they're used, when they expire)
- Monitoring: automated alerts at 30 days, 14 days, 7 days before expiration
- Renewal: initiated before expiration (usually 60-90 days out)
- Verification: new certificate tested in staging before production deployment
- Documentation: renewal logs showing old cert → new cert transition

### Exposed Management Interfaces

**Control:** Administrative interfaces are not exposed to the internet

**What "exposed" means:**
- Accessible from untrusted networks without authentication
- Default credentials still enabled
- On standard ports (8080, 8000, 3000, 3389, 22)
- Running outdated/vulnerable versions

**Corrective actions:**
1. **Disable on internet-facing systems:** If a system doesn't need web interface, disable it entirely
2. **Restrict to internal networks:** Use firewall rules to allow only from admin VPNs/bastion hosts
3. **Move to non-standard ports:** Change from 8080 → 18523 (less discoverable)
4. **Require authentication:** All interfaces require MFA-enabled credentials
5. **Use reverse proxy:** Put admin interfaces behind a proxy that adds additional authentication layer

### Access Control Lists (ACLs) & Network Address Translation (NAT)

**Control:** Network traffic flows only where intended, not to "default allow"

**Problem with defaults:**
- Many firewalls/routers ship with "allow all" as default
- NAT rules forward ports without documentation
- Port mappings accumulate over years (legacy, unused, forgotten)

**Hardening approach:**
1. **Whitelist model:** Default deny, explicitly allow only needed traffic
2. **ACL audit:** Quarterly review of all firewall rules
   - Does this rule still serve a purpose?
   - Is the destination still in use?
   - Could this be more restrictive?
3. **Port cleanup:** Remove unused port mappings
4. **Documentation:** Every rule has a "why" (client ID, service, approval date)

### Default Credentials Removal

**Control:** No default passwords remain in any system

**Scope:**
- Network devices (routers, switches, firewalls)
- Servers (local admin accounts, SQL sa, etc.)
- Applications (WordPress admin, database tools, monitoring dashboards)
- Service accounts (backup software, monitoring agents)

**Process:**
1. **Inventory:** List all systems and their default accounts
2. **Disable/Remove:** Delete or disable default accounts where possible
3. **Change:** For accounts that can't be disabled, change password to 25-character random
4. **Verification:** Attempt login with default credential (should fail)
5. **Documentation:** Maintain list of changed accounts (for troubleshooting, resets)

### HSTS (HTTP Strict Transport Security)

**Control:** Browsers enforce HTTPS-only communication

**How it works:**
1. Server sends header: `Strict-Transport-Security: max-age=31536000; includeSubDomains`
2. Browser receives header, records it for 1 year
3. For next 365 days, browser will:
   - Automatically convert http://example.com → https://example.com
   - Block access if certificate is invalid (even if user clicks "proceed")
   - Prevent any unencrypted communication

**Benefits:**
- Prevents accidental http:// connections
- Prevents MITM attacks via downgrade (attacker can't force http://)
- Protects against SSL stripping attacks

**Implementation:**
- Add header to all web applications (web servers, proxies, load balancers)
- Test with browser (HSTS Labs, etc.)
- Start with short max-age (days) during testing, increase to 31536000 (1 year) after verification

**Evidence auditors check:**
- HSTS header present on all HTTPS responses
- max-age value set appropriately
- includeSubDomains enabled
- Browser testing confirms HSTS enforcement

### Logging Enabled & Logs Consumed

**Control:** All security events are recorded and actively analyzed

**What gets logged:**
- Authentication events (logins, failures, MFA challenges)
- Authorization events (permission grants, denials, privilege escalations)
- Configuration changes (any modification to settings or access rules)
- Data access (who accessed sensitive information, when, why)
- Administrative actions (backups, deletions, account changes)
- Security events (failed updates, antivirus alerts, intrusion attempts)

**"Logs consumed" means:**
- Not just written to disk and forgotten
- Actively parsed, analyzed, alerted on
- Reviewed by humans regularly
- Integrated with incident response

### Principle of Least Privilege

**Control:** Every access is the minimum necessary to do the job

**Applies to:**
- User permissions (file, database, application access)
- Network access (ports, protocols, destinations)
- System resources (CPU, memory, disk quotas)
- Administrative rights (who can change what)

**Implementation:**
1. **Define roles:** What permissions do these job functions need?
   - Support Tech: read-only to customer tickets, reset passwords (limited scope)
   - Network Admin: firewall configuration, but not database access
   - DBA: database administration, but not application code access
2. **Implement RBAC:** Assign users to roles, roles to permissions
3. **Regular review:** Quarterly verification that each user's access matches their role
4. **Just-in-Time (JIT) access:** For sensitive operations, grant temporary elevated access
   - Example: DBA needs to modify production database
   - Request via ticket system, approval required, access granted for 1 hour, logged, access revoked

## Continuous Testing Framework

### Monthly Internal Penetration Testing

**Purpose:** Detect vulnerabilities before external attackers do

**Scope:** Varies each month (rotation through systems)
- Week 1: Application layer (web apps, APIs)
- Week 2: Network layer (firewall, NAT, exposed services)
- Week 3: Infrastructure layer (servers, databases, storage)
- Week 4: Access controls (privilege escalation, lateral movement)

**Process:**
1. **Tester given clean environment** (or minimal information like external IP)
2. **Tester attempts to exploit:** All known attack vectors
3. **Findings documented:** Screenshot, steps to reproduce, impact
4. **Results reviewed:** Security team assigns severity (critical, high, medium, low)
5. **Corrective actions assigned:** Who fixes what, by when?
6. **Remediation verified:** Next month's test checks if issue is fixed

### External Penetration Testing Cadence

**Frequency varies by industry and risk profile:**
- **Startup, internal-only systems:** Annually (12 months)
- **Small business, minimal customer data:** Semi-annually (6 months)
- **Growing MSP, customer data in scope:** Quarterly (3 months)
- **Regulated industry (HIPAA, PCI):** Monthly or continuous (3-12 months)

**Our MSP approach (25 people, customer infrastructure access):**
- External pen test every 3-4 months (4x/year)
- Includes both network and application testing
- Post-assessment report with findings
- Follow-up verification test (re-test critical findings)

**Cost/benefit:**
- Annual cost: ~$8,000-12,000 (for 4 tests at $2-3k each)
- Benefit: Credibility with customers ("We have regular third-party testing")
- Compliance: Meets SOC2 Type II testing requirements

## Corrective Action Workflow

When a vulnerability is found (internal or external test):

```
1. **Detection & Documentation**
   - Tester reports finding (screenshot, steps, proof of vulnerability)
   - Finding entered in a tracking system with a unique ID
   - Severity assigned (critical, high, medium, low)

2. **Triage & Assignment**
   - Security team reviews finding
   - Is this a false positive? Can we dismiss it?
   - Who owns the fix? (network admin for network issue, dev for code issue)
   - Assigned to owner with deadline based on severity:
     - Critical: 48 hours
     - High: 1 week
     - Medium: 2 weeks
     - Low: 1 month

3. **Root Cause Analysis**
   - Owner investigates: Why does this vulnerability exist?
   - Is it a misconfiguration? Outdated software? Design flaw?
   - How widespread is it? Does it affect other systems?

4. **Remediation Implementation**
   - Owner implements fix (config change, patch, code change)
   - Tested in non-production environment first
   - Change request created, approval obtained
   - Deployed to production in approved change window
   - Tested post-deployment to confirm fix

5. **Verification**
   - Tester re-tests vulnerability in next test cycle
   - Confirms: Vulnerability is gone? Attack vector no longer works?
   - If not fixed, escalate and re-assign
   - If fixed, mark the finding resolved

6. **Closeout & Learning**
   - Document: What was the vulnerability? Why did it happen?
   - Process improvement: Can we prevent this in future? (e.g., automated scanning, code review)
   - Log for audit: Evidence that vulnerability was detected and corrected within required timeframe

```

## Why This Matters

Security hardening + continuous testing + corrective action workflow = **provable, sustained security posture**

This approach:
- **Detects vulnerabilities early** (before customer impact)
- **Documents compliance** (logs prove testing happened, issues were fixed)
- **Scales with organization** (automated where possible, disciplined manual processes where not)
- **Builds customer trust** ("We have regular testing and corrective procedures")
- **Meets regulatory requirements** (NIST/DoD, FINRA, HIPAA, PCI and SOC 2 all require evidence of this)

---

*This document synthesizes operational security practices: hardening controls (TLS, certificates, ACLs, defaults), active patching, continuous internal testing, external testing cadence, and corrective action workflows. Applied for clients in regulated industries, in audits for NIST (DoD), FINRA, HIPAA, PCI and SOC 2.*
