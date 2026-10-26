# Product Requirements Document (PRD)

**Project:** Portfolio AI SaaS  
**Version:** GATE 1 (Day 30 MVP)  
**Date:** 2026-06-06  
**Scope:** Website launch with AI assistant demo  
**Timeline:** Days 1–30 (GATE 0→5)

---

## Executive Summary

Launch a public portfolio website for Chris Wetzel (IT Manager, 26 years enterprise infrastructure) with an embedded AI assistant that answers questions about his background, expertise, and experience. The AI will be trained on Chris's resume, website content, LinkedIn profile, and case studies. This is a **marketing + demo tool**, not yet a SaaS product.

**Day 30 Deliverable:** `https://cwetzel.com` → AI chat interface showcasing Chris's expertise  
**Post-Launch (60-90 days):** Multi-tenant SaaS platform, knowledge base management, billing  

---

## Problem Statement

Chris's professional background (26 years enterprise IT, 1,948 LinkedIn followers, posts reaching 60,000+ professionals) deserves an interactive showcase. A static website and LinkedIn profile don't convey depth. An AI assistant that can discuss his experience, answer questions, and demonstrate knowledge builds credibility and engagement.

**Audience:** IT managers, consultants, security professionals, recruiters, potential customers  
**Use Case:** "Tell me about Chris's experience with Azure migrations" → AI summarizes his AVD work with specific metrics  

---

## Goals & Success Metrics

### Primary Goals (Day 30)
1. ✅ Website publicly accessible on cwetzel.com
2. ✅ AI assistant responding to questions about Chris's background
3. ✅ Latency < 500ms (first token) on 90th percentile
4. ✅ Uptime 99%+ during soft launch (24h monitoring)
5. ✅ Demo is shareable (link someone can click and chat)

### Success Metrics (Measurable)
- **Availability:** Uptime ≥ 99% (measured across soft launch week)
- **Performance:** p90 latency < 500ms, throughput > 50 tok/sec
- **Accuracy:** AI correctly answers >90% of questions about Chris's experience
- **Hallucination rate:** <1% (AI makes up facts <1% of time)
- **User feedback:** Positive response from beta testers (friends, colleagues)

---

## User Stories & Use Cases

### Persona: Recruiter
**Story:** "I want to understand Chris's experience before reaching out"  
**Journey:**
1. Visit cwetzel.com
2. See brief intro + chat interface
3. Ask: "What's Chris's experience with Azure?"
4. AI responds with specific projects, timelines, outcomes
5. Recruiter impressed, sends message on LinkedIn

**Success:** Recruiter gets credible summary in <2 minutes

### Persona: IT Manager (Potential Customer)
**Story:** "I want to see if Chris understands our compliance challenges"  
**Journey:**
1. Find link to cwetzel.com from LinkedIn post
2. Chat: "Tell me about your SOC2 Type II experience"
3. AI describes audit process, gaps Chris found, remediation steps
4. Manager bookmarks for later (potential 60-90 day SaaS customer)

**Success:** Demonstrates expertise without sales pitch

### Persona: Friend/Beta Tester
**Story:** "I want to chat with an AI trained on my friend's background"  
**Journey:**
1. Receive link: "Check out what I built"
2. Ask playful questions: "What's Chris's most embarrassing infrastructure failure?"
3. Chat works, responses are coherent
4. Share with other IT people they know

**Success:** Demo is polished enough to share

---

## Functional Requirements (Day 30 MVP)

### Core Features

#### 1. Website Landing Page
- **URL:** `https://cwetzel.com/` (or subdomain)
- **Content:**
  - Hero section: "26 Years in IT. Now AI-Powered."
  - Brief bio (2-3 sentences)
  - Call-to-action: "Chat with AI trained on my experience"
  - Link to chat interface
- **Design:** Matches cwetzel.com branding (simple, professional)
- **Responsive:** Mobile, tablet, desktop

#### 2. Chat Interface
- **URL:** `https://cwetzel.com/chat` (or embedded on homepage)
- **Features:**
  - Text input box ("Ask me anything about my experience")
  - Stream responses in real-time (show tokens as they arrive)
  - Chat history in session (cleared on refresh)
  - "Clear chat" button
  - Simple, clean UI (no complex features)
- **Behavior:**
  - User sends query → AI streams response
  - Context: Chris's resume, experience, expertise (from RAG)
  - Tone: Professional, conversational
  - Max response length: 2000 tokens (~1500 words)

#### 3. RAG Knowledge Base (Day 30 Content)
**Single knowledge base: Chris Wetzel's Background**

*Sources included:*
- Resume (detailed, all jobs, skills, certifications)
- cwetzel.com pages (About, Experience, Projects, Education)
- LinkedIn profile (summary, experience section, recommendations)
- Case studies (5 detailed write-ups):
  - SOC2 Type II Compliance (audit process, gaps, remediation)
  - Azure Virtual Desktop Migration (120→200 users, regional, scaling)
  - SAP Business One Integration (MSSQL backend, WMS, global)
  - Disaster Recovery Planning (BDR, off-site, failover testing)
  - VMware Virtualization (P2V strategy, infrastructure design)

*Not included day 30:*
- Custom documents (users upload own content) — 60-90 day feature
- Multiple knowledge bases — 60-90 day feature
- Dynamic content updates — 60-90 day feature

#### 4. Basic Infrastructure
- **Cloud:** Ubuntu VPS ($5/mo) with nginx + FastAPI
- **Home:** Gentoo + vLLM (2x A4500 GPUs)
- **Connection:** WireGuard tunnel (203.0.113.0/24)
- **Database:** PostgreSQL for chat history (optional, can use session storage)
- **Caching:** Redis for rate limiting
- **No:** User signup, authentication, billing, payments

---

## Non-Functional Requirements

### Performance
- **Latency (First Token):** p50 < 100ms, p90 < 500ms
- **Throughput:** > 50 tokens/sec (single-user acceptable, dual GPU available for scaling)
- **Availability:** 99%+ uptime during soft launch week
- **Response Time (Full):** < 10 seconds for 1000-token response

### Security
- ✅ HTTPS/TLS only (no plaintext over internet)
- ✅ Rate limiting (100 requests/minute per IP, via Redis)
- ✅ No user data persistence (chat history clears on refresh OR cleared daily)
- ✅ Input validation (reject oversized/malformed requests)
- ✅ No secrets hardcoded (env vars for API keys, model path, etc.)
- 🚫 No authentication required (day 30; added in SaaS phase)
- 🚫 No data storage (keep it stateless for MVP)

### Scalability
- **Concurrent users:** 5–10 during soft launch (not enterprise-scale)
- **Queuing:** Simple queue (10 max pending requests, drop if full)
- **Graceful degradation:** If GPU fails, return error (don't hang)
- **Monitoring:** Health check `/health` returns uptime, token usage, GPU util

### Accuracy & Reliability
- **Hallucination rate:** <1% (AI makes up facts < 1% of time)
- **RAG relevance:** Top-5 retrieved documents include answer 90%+ of time
- **Answer coherence:** Responses are grammatical, on-topic, not repetitive
- **Prompt injection:** User cannot manipulate system prompt with input

---

## Out of Scope (Day 30)

🔲 **Not included; these are 60-90 day features:**

- [ ] User signup/login (no accounts)
- [ ] Knowledge base management (no document uploads)
- [ ] Billing/Stripe integration (no payments)
- [ ] Multi-tenant support (one knowledge base)
- [ ] Admin dashboard (no user management)
- [ ] Analytics (no usage tracking)
- [ ] API rate limiting per user (simple IP-based only)
- [ ] Chat history persistence (optional, session-only)
- [ ] Advanced RAG (semantic search, re-ranking, chunk optimization)
- [ ] Model fine-tuning (standard Llama 70B only)
- [ ] Custom system prompts (fixed prompt, no variation)
- [ ] Feedback loops (no thumbs up/down, no corrections)

---

## Acceptance Criteria

### Feature Completeness
- [ ] Website landing page deployed and accessible
- [ ] Chat interface accessible at `/chat` endpoint
- [ ] AI responds to questions about Chris's experience
- [ ] Responses are grammatically correct and on-topic
- [ ] Chat works on mobile, tablet, desktop
- [ ] No hardcoded secrets in code/config

### Performance
- [ ] p90 latency measured < 500ms (first token)
- [ ] Throughput > 50 tok/sec (measured under load)
- [ ] Health check endpoint `/health` returns 200 OK
- [ ] Docker build completes without warnings

### Testing
- [ ] Chat endpoint tested with 10+ sample queries
- [ ] Latency measured (p50, p90, p99)
- [ ] Concurrent user test (5 simultaneous, no errors)
- [ ] Edge cases tested (empty input, very long input, special characters)

### Deployment
- [ ] Website deployed to cloud VPS
- [ ] WireGuard tunnel stable (monitored 24h)
- [ ] HTTPS working (SSL certificate valid)
- [ ] Monitoring configured (health checks every 5 min)

### Documentation
- [ ] README.md written (how to run locally, deploy)
- [ ] Architecture documented (high-level diagram)
- [ ] Deployment runbook written (how to troubleshoot)

### Soft Launch
- [ ] Link shared with 5–10 beta testers (friends, colleagues)
- [ ] Feedback collected (works? responses good? interface clear?)
- [ ] Uptime monitored for 24h (≥ 99%)
- [ ] No critical bugs found in soft launch

---

## Timeline (30 Days)

### Days 1–3: GATE 1 Planning
- [ ] Finalize GATE 1 documents (prd, architecture, test-plan, .cursorrules)
- [ ] Lock design decisions (no changes after)

### Days 4–20: GATE 2 Development
- [ ] Build website landing page + chat UI (React)
- [ ] Implement chat endpoint (`/api/chat` WebSocket or SSE)
- [ ] Set up RAG pipeline (load Chris's content into Qdrant)
- [ ] Set up inference (vLLM streaming)
- [ ] Docker build for cloud deployment
- [ ] Write tests (endpoint tests, latency tests)

### Days 21–25: GATE 3 Testing
- [ ] Latency & performance testing (measure p50, p90, p99)
- [ ] Concurrency testing (5 users simultaneously)
- [ ] Security audit (HTTPS, input validation, rate limiting)
- [ ] 10+ manual chat tests (quality, accuracy, hallucination)

### Days 26–27: GATE 4 Deployment
- [ ] Deploy to cloud VPS
- [ ] Configure WireGuard tunnel
- [ ] Set up SSL certificate (Certbot)
- [ ] Configure monitoring + health checks
- [ ] Test rollback procedure

### Days 28–30: GATE 5 Soft Launch
- [ ] Share link with beta testers
- [ ] Monitor for 24h (uptime, errors, latency)
- [ ] Collect feedback
- [ ] Document lessons learned
- [ ] **Go/No-Go decision:** Ready for public? Or hold for fixes?

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| WireGuard tunnel unstable | Medium | High | Monitor continuously, failover to cloud-only mode |
| vLLM inference slow (>500ms) | Medium | High | Optimize batching, reduce context window if needed |
| RAG missing important content | Medium | Medium | Manually test 20+ queries before launch |
| Website styling issues | Low | Low | Test on 3 browsers (Chrome, Safari, Firefox) |
| Domain/DNS issues | Low | High | Test DNS resolution, SSL cert before launch |
| GPU out of memory | Low | High | Set max concurrent requests = 3, queue rest |

---

## Success Definition (Day 30)

✅ **Success:** Website public, AI demo working, shareable with others, no critical bugs during 24h soft launch  
❌ **Failure:** Website not accessible, AI doesn't respond, latency > 1s, crashes during testing

---

## Future Phases (60-90 Days)

These are explicitly **out of scope for day 30**, but planned for phase 2:

### GATE 1 (Planning Phase 2)
- [ ] Design multi-tenant architecture
- [ ] Define SaaS pricing tiers
- [ ] Design knowledge base management UI
- [ ] Plan Stripe integration

### GATE 2 (Development Phase 2)
- [ ] User signup/login system
- [ ] Knowledge base CRUD (upload, index, delete documents)
- [ ] Stripe payment integration
- [ ] Usage tracking (tokens, requests, cost)
- [ ] Admin dashboard (user management)

### GATE 3 (Testing Phase 2)
- [ ] Multi-tenant testing (tenant A cannot see tenant B's data)
- [ ] Billing testing (free tier, paid tier, overage charges)
- [ ] Load testing (50 concurrent users)

### GATE 4-5 (Release & Launch)
- [ ] Production deployment
- [ ] Customer onboarding (first paid customers)
- [ ] Monitoring & incident response

---

## Questions for Approval

Before GATE 1 sign-off:

1. ✅ Is day-30 scope correct? (Website + demo AI only, no SaaS)
2. ✅ Are RAG sources complete? (Resume, cwetzel.com, LinkedIn, 5 case studies?)
3. ✅ Is response length OK (2000 tokens max)?
4. ✅ Is beta tester list locked? (5-10 friends/colleagues?)
5. ✅ Is cwetzel.com domain ready to point to cloud VPS?

---

**Status:** GATE 1 Ready for Review  
**Next:** Approval → GATE 2 Development  
**Owner:** Chris Wetzel  
**Last Updated:** 2026-06-06
