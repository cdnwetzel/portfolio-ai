# Portfolio AI Knowledge Base

**Status:** Day 30 MVP (Ready for GATE 2 Indexing into Qdrant)  
**Last Updated:** 2026-06-06  
**Purpose:** Foundation for AI chat trained on Chris Wetzel's professional background, published expertise, and infrastructure projects

---

## Structure

```
src/data/knowledge_base/
├── INDEX.md                    (this file)
├── POSTS_METADATA.json         (ranking + engagement metrics)
├── RESUME.md                   (comprehensive CV + projects)
├── posts/                      (published LinkedIn posts)
│   ├── horror_story_salary_spreadsheet.md    (42,902 imp)
│   ├── copilot_permissions_leaking.md        (18,841 imp)
│   ├── leadership_access_control.md          (15,104 imp)
│   ├── microsoft_anthropic_infrastructure_war.md (3,927 imp)
│   ├── copilot_dlp_bug_cw1226324.md         (3,853 imp)
│   └── ... 15 more published posts
├── case_studies/               (detailed project write-ups) — TBD
│   ├── soc2_type_ii_compliance.md
│   ├── avd_migration_200_users.md
│   ├── sap_business_one_integration.md
│   ├── disaster_recovery_planning.md
│   └── vmware_p2v_infrastructure.md
├── infrastructure/             (Gentoo machines, system config) — TBD
│   └── gentoo_machines_repo_summary.md
└── resume_experience/          (structured experience breakdown) — TBD
```

---

## Content Inventory

### 1. Published Posts (6 Files, 28 Total on LinkedIn)
**Source:** /Users/cwetzel/ai/content_creator/posts/  
**Status:** ✅ Copied (6 published posts captured)  
**Missing:** Select top ~10 of remaining posts from LinkedIn content_creator drafts  
**Metrics:** Ranked by impressions (highest first)

**Top 5 Posts (67% of total impressions):**
1. Horror Story (42,902 impressions, 283 reactions)
2. Copilot Permissions (18,841 impressions, 119 reactions)
3. Leadership Problem (15,104 impressions, 89 reactions)
4. Microsoft/Anthropic Strategy (3,927 impressions, 14 reactions)
5. DLP Bug (3,853 impressions, 24 reactions)

**Usage:** When user asks about governance, permissions, or compliance, AI retrieves top posts first (validated by 42k+ impressions).

### 2. Resume (1 File)
**Status:** ✅ Created  
**Content:**
- Current role: IT Manager @ Law Firm
- 26 years enterprise infrastructure
- Detailed work history (2 employers, 13+ years each)
- 5 major projects (SOC2, AVD, SAP, DR, VMware)
- Skills inventory (servers, cloud, databases, scripting)
- Philosophy (tech problems are people problems)

**Usage:** Foundation for "Tell me about yourself" queries. Cites specific projects, metrics, outcomes.

### 3. Case Studies (5 Files) — **TO CREATE**
**What's Missing:** Detailed 1-2 page write-ups for:
- SOC2 Type II Compliance (audit process, gaps, remediation)
- Azure VDI Migration (120→200 users, regional, failover)
- SAP Business One Integration (global, WMS, performance)
- Disaster Recovery Planning (BDR, backup strategy, testing)
- VMware P2V Infrastructure (consolidation, cost savings)

**Why:** Resume mentions these; case studies show depth. When AI retrieves "SAP" or "compliance," case study context is richer than resume bullets.

### 4. Infrastructure (1 File) — **TO CREATE**
**What's Missing:**
- Summary of gentoo-machines GitHub repo
- Kernel config approach (version-controlled)
- System administration philosophy
- Public infrastructure projects

**Why:** Portfolio shows IT depth beyond corporate work. DIY infrastructure = credibility.

### 5. LinkedIn Profile Summary (1 File) — **TO CREATE**
**What's Missing:**
- Cleaned profile text (About, Experience section)
- Top endorsements + recommendations (if available)
- Follower demographics + engagement patterns

**Why:** Validates audience (1,948 followers, 114k impressions). When AI cites "reached 42,000 IT professionals," context shows it's real.

---

## GATE 2 Implementation (Days 4-20)

### Phase 1: Index into Qdrant (Day 4-5)
**Action:**
1. Load all .md files from knowledge_base/
2. Chunk by document (or adaptive 512-token chunks)
3. Generate embeddings (BAAI/bge-small-en-v1.5)
4. Index into Qdrant:6333 on T5810

**Expected:** ~200 documents (50+ LinkedIn posts + resume + projects + infrastructure + 3-5 case studies)

### Phase 2: Test Retrieval (Day 6-7)
**Test queries:**
- "Tell me about your governance experience" → Should retrieve top posts + SOC2 case study
- "What's your Azure background?" → Should retrieve AVD case study + resume
- "What compliance frameworks have you worked with?" → Should retrieve SOC2 + DLP posts
- "Your infrastructure philosophy?" → Should retrieve Gentoo summary + resume

### Phase 3: Integrate with FastAPI (Day 8-10)
**Action:**
1. FastAPI on cwetzel.com queries Qdrant via SSH tunnel (localhost:6333)
2. Retrieve top-5 documents for user query
3. Build context prompt with retrieved content
4. Send to vLLM:8001 via tunnel

### Phase 4: Test End-to-End (Day 11-15)
**Flow:**
1. User browser → cwetzel.com (landing page + chat UI)
2. User types query → cwetzel.com FastAPI
3. FastAPI queries Qdrant (via SSH tunnel)
4. FastAPI forwards to vLLM (via SSH tunnel)
5. vLLM streams response back
6. Browser displays streaming response

**Example response:**
> "I've worked extensively with compliance frameworks, particularly SOC2 Type II. One post on this topic reached 42,000 IT professionals. The pattern I've seen: most organizations don't fail compliance because of tools—they fail because nobody answered the foundational question: who should actually have access to what, and why?..."

---

## Content to Create (GATE 2, Days 1-3)

**~4 hours of work needed:**

1. **Case Studies (2 hours)**
   - SOC2 audit process write-up
   - AVD migration scale-up story
   - SAP integration challenges/solutions
   - DR testing/validation process
   - VMware consolidation metrics

2. **Gentoo Machines Summary (30 minutes)**
   - Repo overview
   - Kernel versioning approach
   - System admin philosophy

3. **LinkedIn Profile Summary (30 minutes)**
   - Copy profile text (About section)
   - Endorsements/recommendations

4. **Infrastructure Notes (1 hour)**
   - cwetzel.com history
   - T5810 setup philosophy
   - Why self-hosted (privacy, control, cost)

---

## Metadata File Format

**POSTS_METADATA.json:**
- Ranked by impressions (highest first)
- Includes: impressions, reactions, comments, followers-from-post
- Themes tagged for semantic grouping
- Engagement rate calculated (reactions + comments / impressions)

**Usage:** When Qdrant retrieves posts, it scores based on:
1. Semantic similarity to query (embedding distance)
2. Engagement rank (impressions + reactions)
3. Recency (if applicable)

---

## Day 30 MVP Scope

**What's included:**
- ✅ Resume + work history
- ✅ 6+ published LinkedIn posts (highest impact)
- ⏳ 5 case studies (detailed projects)
- ⏳ Infrastructure philosophy (Gentoo setup)
- ⏳ LinkedIn profile summary

**What's NOT included (60-90 day expansion):**
- 🔲 Draft posts (pre-published content)
- 🔲 Newsletter issues (archived, can add if valuable)
- 🔲 Full LinkedIn connection/engagement data (tracked separately)
- 🔲 Video content (YouTube, HeyGen videos)
- 🔲 Speaking slides or webinar transcripts

---

## Retrieval Ranking Logic (Qdrant)

When user queries ("Tell me about your governance experience"):

1. **Semantic Search:** Find top-5 documents by embedding similarity
2. **Rank by Impact:** Rerank by impressions/engagement (posts that reached more people first)
3. **Return to FastAPI:** Context-build from top-3 documents

**Example:**
- Query: "governance"
- Qdrant retrieves:
  1. Horror Story (42,902 imp) — 0.92 similarity
  2. Copilot Permissions (18,841 imp) — 0.88 similarity
  3. SOC2 Case Study (not ranked by impressions, but highest quality) — 0.87 similarity
  4. Resume SOC2 section — 0.85 similarity
  5. Post 4 Leadership (15,104 imp) — 0.83 similarity
- FastAPI uses top-3 for context
- LLM generates response citing: "Post on permissions (42k impressions) + SOC2 audit experience (case study) + leadership thinking"

---

## Next Steps (GATE 2, Day 1)

1. **Create case studies** (2h) — Turn resume bullets into 1-2 page narratives
2. **Gentoo summary** (30m) — What's the GitHub repo about? Why public?
3. **LinkedIn profile** (30m) — Copy the About section + endorsements
4. **Commit to git** (15m) — All files staged and committed
5. **Prepare for Qdrant** (1h) — Document indexing strategy for T5810

---

**Status:** Knowledge base scaffolding complete. Ready for GATE 2 implementation.  
**Dependency:** Day 1-3: Create missing case studies + summaries.  
**Timeline:** Days 4-7 integrate into Qdrant + test retrieval.
