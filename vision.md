# Vision: Portfolio AI SaaS

## Problem We're Solving

Recruiters want to understand a candidate's technical depth in **seconds**, not by reading a static resume. Traditional AI portfolio tools outsource inference to expensive APIs (OpenAI $0.30/1k tokens, Anthropic $0.80/1k tokens). This creates a scaling problem for SaaS: high CAC, low margins, vendor lock-in.

**Portfolio AI changes this:** Self-hosted GPU inference + multi-tenant billing = $0.001/1k tokens, with zero API dependency.

---

## Vision Statement

**"Every developer deserves an AI assistant that knows their work, costs almost nothing to run, and proves they understand distributed systems."**

---

## What Success Looks Like

### For You (The Builder)
- Live interview: "Ask my AI about my experience"
- Recruiter: Chats with your resume, GitHub repos, LinkedIn in real-time
- Recruiter observes: GPU inference on your hardware, WireGuard tunnel, edge caching
- Result: 3–5 quality inbound offers from companies impressed by the *architecture*, not just the resume

### For Early Customers (Post-MVP)
- Lawyer: "I uploaded 20 contracts. Your AI reviewed them in 2 minutes."
- Startup founder: "I have a custom RAG system for my product docs, no API costs."
- Data scientist: "I'm demonstrating my fine-tuned model via a live SaaS dashboard."

### For the Business (Revenue)
- 100 Pro tier customers @ $29/month = $2,900 revenue
- Costs: $46/month hardware + 10 hours/week ops = **$2,800+ profit**
- Path to $10k/month: White-label + API licensing

---

## Measurable Success Metrics (MVP - Day 30)

### Performance
| Metric | Target | Method |
|--------|--------|--------|
| **First Token Latency** | < 200ms | Measure p50 + p99 in production |
| **Throughput** | > 100 tok/sec (batched) | vLLM metrics endpoint |
| **GPU Utilization** | 70–85% | nvidia-smi during peak load |
| **WireGuard Latency** | < 50ms ping | ping 10.0.0.1 from cloud |

### Reliability
| Metric | Target | Method |
|--------|--------|--------|
| **API Uptime** | 99.5% first 30 days | Monitoring dashboard |
| **Health Check Success** | 100% | curl /health every 60s |
| **Database Connection Pool** | No drops | PostgreSQL logs |
| **Deployment Success Rate** | 100% | 0 failed GitHub Actions runs |

### Quality
| Metric | Target | Method |
|--------|--------|--------|
| **Test Coverage** | ≥ 80% | pytest --cov |
| **Type Hint Coverage** | ≥ 90% | pyright strict mode |
| **Security Audit** | 0 high-severity findings | OWASP Top 10 manual check |
| **RAG Retrieval Relevance** | ≥ 0.75 | Validation against 50 test queries |

### Business
| Metric | Target | Method |
|--------|--------|--------|
| **Signup Flow Works** | End-to-end | Test signup → pay with Stripe test card → dashboard works |
| **Revenue Tracking** | Accurate | Compare Stripe dashboard to app database usage_metrics |
| **Cost per Inference** | < $0.001 | (Monthly electricity) / (total tokens served) |

---

## Scope Boundaries

### Data
- **Training data:** None (inference only, using open models)
- **User data:** Customers' documents, query history (stored in PostgreSQL)
- **Model weights:** Llama 70B downloaded from HuggingFace (not trained)

### Model
- **Model choice:** Llama 2 70B (open license, good quality)
- **Fine-tuning:** Not in MVP (but architecture supports it)
- **Quantization:** bfloat16 (no quantization pressure on 40GB VRAM)
- **Context window:** 4096 tokens (limited by vLLM page attention)

### Hardware
- **GPU:** 2x NVIDIA A4500 (40GB total VRAM, NVLink)
- **CPU:** Single-threaded inference acceptable
- **Storage:** 500GB for model weights + database
- **Network:** 300 Mbps fiber (symmetric), fixed IP

### Timeline
- **MVP (Launch):** 30 days (June → July 6)
- **Soft launch (Closed beta):** Friends + early customers, 1–2 weeks
- **Public launch:** Post-feedback iteration
- **Post-launch ops:** Ongoing, minimal time

### Known Constraints
- **Regulatory:** Data handling complies with GDPR (privacy by design)
- **Privacy:** No customer data used for model training
- **Licensing:** All open-source (no proprietary model dependencies)
- **Compliance:** Stripe handles PCI-DSS, we handle application security

---

## Scope: NOT Included

### Out of Scope (Do Not Build)
- ❌ Custom model training (requires 10k+ labeled examples, 2–3 weeks)
- ❌ Real-time model updates (requires redeployment, breaks versioning)
- ❌ Multi-model support (too many deployment variables)
- ❌ Voice/video (requires additional infrastructure, different SLA)
- ❌ Mobile app (web-first, can add later)
- ❌ Advanced analytics (basic usage tracking only)
- ❌ White-label support (post-MVP, requires branding config)

### Deferred (Post-Launch Roadmap)
- 🔄 Fine-tuning workflow (add in month 2)
- 🔄 Custom embeddings (add in month 2)
- 🔄 API rate-limiting tiers (add in month 3)
- 🔄 Multi-region deployment (add in month 4)

---

## Success Announcement (What We'd Publish)

```markdown
## We Launched Portfolio AI — Your GitHub as Your Resume

Tired of static resumes? We built a self-hosted AI that knows your work.

### How It Works
1. Connect your GitHub (public repos auto-indexed via webhook)
2. Upload your resume + LinkedIn
3. Visitors ask your AI anything about your experience
4. You get notified of interesting conversations

### The Twist
It runs on our own GPU cluster. No API costs. No vendor lock-in.

### Technical Breakdown
- Llama 70B inference on dual A4500s (40GB NVLink)
- WireGuard tunnel from cloud edge to home GPU (< 50ms latency)
- Real-time streaming responses (100+ tok/sec throughput)
- RAG pipeline (Qdrant vector DB + semantic search)
- Multi-tenant SaaS ($29/month Pro tier, or white-label your own)

### Early Traction
- [Launch day numbers]
- [Customer testimonials]
- [Infrastructure metrics]

### Available Now
- Personal demo: portfolio.chris.cwetzel.com
- GitHub: github.com/cdnwetzel/portfolio-ai-saas (open source components)
- Early access signup: Apply for Pro tier

*Built to prove you understand distributed systems.*
```

---

## Why This Matters (For Interviews)

When you interview, you're not just saying "I know distributed systems." You're **running** a distributed system that candidates use in real-time. That's a top-percentile engineer signal.

---

## Risk Factors & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| WireGuard tunnel down | Inference unavailable | Health checks + automated rollback to cloud-only mode |
| Model accuracy issues | Bad user experience | RAG retrieval + content sampling reduces hallucinations to <1% |
| Stripe webhook failures | Revenue tracking broken | Implement message queue + dead-letter handling |
| GitHub API limits | Indexing blocks | Implement caching + exponential backoff |
| Home internet outage | Complete service down | Document manual failover, monitor fiber status |

---

## Target Audiences

### Primary (MVP)
- **Recruiters/hiring managers:** Interactive portfolio demo
- **Early SaaS customers:** Lawyers, consultants, data scientists with custom data

### Secondary (Post-Launch)
- **Developers:** Self-hosted AI inference alternative to cloud APIs
- **Enterprises:** Private RAG + compliance-compliant LLM inference

---

## Key Differentiators

1. **Cost:** $50/month vs. $500+ cloud GPUs (10x cheaper)
2. **Privacy:** Data stays on your infrastructure (no API logs)
3. **Control:** Run locally, modify code, fine-tune models
4. **Infrastructure Demo:** WireGuard + vLLM + Qdrant in production
5. **Revenue:** Multi-tenant SaaS (not just a portfolio site)

---

**Current Status:** GATE 0 (Vision defined, awaiting Planning approval)  
**Last Updated:** 2026-06-06
