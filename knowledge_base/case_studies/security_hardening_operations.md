# Security Hardening & Continuous Testing: Operational Controls

**Role:** Chris Wetzel — designed and ran these security-hardening operations.

## Overview

Security hardening is not a one-time configuration. It's an **operational discipline** combining:
- **Proactive configuration hardening** (disable weak protocols, remove defaults)
- **Active patching** (timely updates to close vulnerabilities)
- **Continuous testing** (monthly internal pen tests, external cadence 3-12 months)
- **Corrective action workflows** (find issue → fix → verify → document)
- **Principle of least privilege** (every access, every port, every setting justified)

This framework applies across compliance regimes: SOC2 Type II, PCI DSS 4.0, HIPAA, NIST 171, FINRA. The controls overlap; the philosophy is unified.

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

**Common finding in testing:**
```
Vulnerability: TLS 1.0 still enabled on legacy system
Root cause: System was installed in 2015, not updated
Corrective action:
  1. Assessed risk: Is this system exposed to untrusted networks? (Yes)
  2. Evaluated options: Upgrade OS? Disable TLS 1.0 and require external access via proxy?
  3. Decision: Deploy reverse proxy (nginx) in front of legacy system
  4. Proxy terminates TLS 1.2, forwards to legacy system on internal network
  5. Tested: External scan shows TLS 1.2 only, internal communication unaffected
  6. Verified: In next month's pen test, no weak TLS detected
```

### Certificate Management & Currency

**Control:** All certificates are valid, current, and monitored

**Process:**
- Inventory of all certificates (where they're used, when they expire)
- Monitoring: automated alerts at 30 days, 14 days, 7 days before expiration
- Renewal: initiated before expiration (usually 60-90 days out)
- Verification: new certificate tested in staging before production deployment
- Documentation: renewal logs showing old cert → new cert transition

**Example timeline:**
```
Certificate for api.example.com
Issued: 2024-01-15, Expires: 2025-01-14 (1-year validity)

2024-10-15 (90 days before expiration): Automated alert "cert expires in 90 days"
  → Check: Renewal policy allows 60 days, so we're in window
  → Renewal requested from CA

2024-12-15 (30 days before expiration): Alert "cert expires in 30 days"
  → Verify: New certificate received? Yes
  → Test: New cert deployed to staging, validated with SSL Labs
  → Schedule: Production deployment for 2024-12-20 (off-peak window)

2024-12-20: Production certificate update
  → Deploy new certificate to load balancer
  → Verify: Traffic flows without SSL errors
  → Confirm: Certificate chain is complete and valid
  → Log: "Certificate updated: api.example.com, old cert 2024-01-15, new cert 2025-01-14"

2025-01-15: Old certificate expires (no impact, already replaced)
```

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

**Example finding:**
```
Vulnerability: VMware ESXi management interface (port 443) exposed to internet
- Port 443 is accessible from any IP
- Default credentials tested (not changed from installation)
- Vulnerable version 6.5 (exploit available)

Corrective action:
  1. Updated ESXi to version 7.0 (out of support, tested first)
  2. Changed default administrator password to 25-character random
  3. Added firewall rule: Allow port 443 only from an internal bastion host
  4. Disabled all other admin services (SSH, etc.) on internet side
  5. Enabled vCenter audit logging for all admin access
  6. Tested: External scan shows port 443 closed from internet, admin access only from bastion

Ongoing: Monthly scan of management interfaces from external perspective
```

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

**Example ACL audit:**
```
Firewall review, Q2 2024

Rule: Allow <external IP> (external) → <internal host> (internal) port 3389 (RDP)
Purpose: Support client XYZ remote access (VPN tunnel)
Status: Client updated to use VPN → remove rule? 
Investigation: Client still has legacy RDP access configured, not in use
Decision: Remove rule (client should use VPN)
Approval: manager@msp.com
Documented: ACL audit log, change ticket CHG-3847

Before cleanup: 214 rules (many redundant, some conflicting)
After audit: 127 rules (rules with clear purpose, less management overhead)
Benefit: Faster rulebase evaluation, fewer conflicts, clearer security posture
```

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

**Example:**
```
System: Windows Domain Controller
Default account: Administrator (username "Administrator")
Action: Account remains (required for domain), password changed
Old password: [default per Windows]
New password: 7K#mP9$rL@vQ2xW8nB4&zC1*jF6yHt5
Changed by: security@msp.com
Changed date: 2024-03-15
Verified: Attempted login with default password → "Access Denied"
Stored in: Credential vault (HashiCorp Vault, encrypted)
Access to vault: 5 admins (principle of least privilege)
Vault access logged: All retrievals tracked and audited
```

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

**Example logging architecture:**
```
Source systems → syslog/rsyslog → Central ELK Stack → Alerting → SOC review

1. Web server logs HTTP requests → syslog → ELK
   ELK parses and indexes: timestamp, user, action, resource, result
   Alert: 10 failed logins from same IP in 5 minutes → block IP + notify security

2. Firewall logs dropped packets → syslog → ELK
   ELK correlates: Is this a port scan? Is this a known attacker?
   Alert: 100+ packets dropped to port 22 from external IP → review, possibly block

3. Vulnerability scanner finds issue → logged in scanner + ELK
   Alert: Critical vulnerability detected on server X → create ticket, assign to ops

4. Monthly review: Security team searches logs for:
   - Brute force attempts (failed logins from same IP)
   - Insider threats (unusual access patterns)
   - Unpatched systems (requests to deprecated TLS versions)
   - Compliance violations (access without approval)
```

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

**Example:**
```
Support technician (user: support1@msp.com) needs access to:
- Read support tickets for their assigned clients
- View client configuration details (to help troubleshoot)
- Reset user passwords (with client approval)
- NOT access: Billing, other clients' data, financial records

Role: "Support Tech - Limited"
Permissions:
  - Ticketing system: Read-only on assigned tickets
  - Knowledge base: Read-only
  - Client portal: View assigned client systems
  - AD: Can reset password in own domain only
  - Database: No direct access (uses web portal)
  - SSH: No access

Review (quarterly):
  Q2 2024: Support1 still assigned 3 clients? Yes, permissions correct
  Q3 2024: Support1 reassigned to 5 clients → role adjusted, test access
  Q4 2024: Support1 promoted to senior support → move to "Support Tech - Full" role

If someone needs temporary elevated access:
  - Ticket: "Need to access client ABC database to debug connection issue"
  - Approval: Manager approves, scope limited to "client ABC database, read-only, 4 hours"
  - Grant: Temporary elevated access via PAM system, logged with timestamp
  - Verify: Can access? Yes, log shows "admin access: 2024-06-20 14:00-18:00"
  - Revoke: Automatic after 4 hours, logged
```

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

**Example findings:**

```
Month 1 (Application Layer):
Finding: SQL injection in customer search form
Impact: Attacker can read all customer data
Severity: CRITICAL
Corrective action: 
  - Parameterized queries for all database access
  - Input validation on all forms
  - Rate limiting on search endpoint
Deadline: 2 weeks
Verification: Month 2 test confirms vulnerability patched

Month 2 (Network Layer):
Finding: Port 8080 open on web server (debug HTTP server)
Impact: Exposed internals if compromised
Severity: MEDIUM
Corrective action:
  - Disabled debug HTTP server in production
  - Closed port 8080 in firewall
  - Verified in staging that application works without it
Deadline: 1 week
Verification: Port scan shows 8080 closed

Month 3 (Infrastructure):
Finding: Weak SSH cipher suite allows weak key exchange
Impact: Potential eavesdropping on SSH sessions
Severity: HIGH
Corrective action:
  - Disabled weak ciphers on all SSH servers
  - Enabled only curve25519 (modern, strong)
  - Tested SSH access from client machines (confirmed working)
Deadline: 1 week
Verification: SSH scan shows no weak ciphers

Month 4 (Access Controls):
Finding: User account in deactivated state but still has firewall access
Impact: Former employee could potentially regain network access if password recovered
Severity: MEDIUM
Corrective action:
  - Automated off-boarding process: disable account, remove from all groups, close firewall rules
  - Quarterly review of deactivated accounts vs firewall rules
  - Revoked any orphaned rules
Deadline: 1 week
Verification: Quarterly review includes this check going forward
```

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
   - Finding entered in tracking system with unique ID (VULN-2847)
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
   - If fixed, mark VULN-2847 as resolved

6. **Closeout & Learning**
   - Document: What was the vulnerability? Why did it happen?
   - Process improvement: Can we prevent this in future? (e.g., automated scanning, code review)
   - Log for audit: Evidence that vulnerability was detected and corrected within required timeframe

Example timeline:
  VULN-2847 (Weak TLS cipher) detected: 2024-06-15
  Assigned to: network admin, deadline 2024-06-22 (HIGH severity, 1 week)
  Root cause: Server installed in 2019, TLS config never updated
  Fix: Disabled weak ciphers, enabled TLS 1.3
  Tested: 2024-06-21 in staging
  Deployed: 2024-06-21 22:00 UTC (change window)
  Verified: 2024-07-15 (next month's test confirmed fixed)
  Resolved: 2024-07-15, audit log shows "corrected within SLA"
```

## Why This Matters

Security hardening + continuous testing + corrective action workflow = **provable, sustained security posture**

This approach:
- **Detects vulnerabilities early** (before customer impact)
- **Documents compliance** (logs prove testing happened, issues were fixed)
- **Scales with organization** (automated where possible, disciplined manual processes where not)
- **Builds customer trust** ("We have regular testing and corrective procedures")
- **Meets regulatory requirements** (SOC2, HIPAA, PCI DSS, NIST 171 all require this)

---

*This document synthesizes operational security practices: hardening controls (TLS, certificates, ACLs, defaults), active patching, continuous internal testing, external testing cadence, and corrective action workflows. Applies across SOC2 Type II, PCI DSS, HIPAA, NIST 171, and FINRA compliance frameworks.*
