# Architecture Overview

## System Design

Your SaaS platform uses a **distributed edge-to-core** architecture optimized for low-latency user interactions and cost-efficient GPU compute.

```
┌─────────────────────────────────────────────────────────────┐
│                     User Internet Traffic                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Cloudflare  │ (DNS + DDoS protection)
                    └──────┬───────┘
                           │
        ┌──────────────────┴──────────────────┐
        │                                     │
   ┌────▼──────┐                      ┌──────▼────────┐
   │   yourdomain.com                 │ app.yourdomain │
   │ (Portfolio Page)                 │ (SaaS Dashboard)
   └────┬──────┘                      └──────┬────────┘
        │                                    │
        │                          ┌─────────▼────────┐
        │                          │   Cloud Ubuntu   │
        │                          │ (Edge Compute)   │
        │                          │                  │
        │                          │ ┌──────────────┐ │
        │                          │ │ React App    │ │
        │                          │ │ (Static)     │ │
        │                          │ └──────┬───────┘ │
        │                          │ ┌──────▼───────┐ │
        │                          │ │ Nginx        │ │
        │                          │ │ Reverse Proxy│ │
        │                          │ └──────┬───────┘ │
        │                          │ ┌──────▼───────┐ │
        │                          │ │ FastAPI      │ │
        │                          │ │ Proxy + Auth │ │
        │                          │ └──────┬───────┘ │
        │                          │ ┌──────▼───────┐ │
        │                          │ │ Redis        │ │
        │                          │ │ (Caching)    │ │
        │                          │ └──────┬───────┘ │
        │                          │        │         │
        │                          └────────┼─────────┘
        │                                   │
        │                      ┌────────────▼────────────┐
        │                      │   WireGuard Tunnel      │
        │                      │  (Encrypted 203.0.113.0/24)
        │                      └────────────┬────────────┘
        │                                   │
        │  (Optional: home fiber)  ┌────────▼─────────┐
        └──────────────────────────┤ Home Gentoo      │
                              ┌─────┤ (Core Compute)   │
                              │     │                  │
                              │     │ ┌──────────────┐ │
                              │     │ │ vLLM         │ │
                              │     │ │ 2x A4500     │ │
                              │     │ │ NVLink       │ │
                              │     │ └──────┬───────┘ │
                              │     │ ┌──────▼───────┐ │
                              │     │ │ Qdrant       │ │
                              │     │ │ Vector DB    │ │
                              │     │ └──────┬───────┘ │
                              │     │ ┌──────▼───────┐ │
                              │     │ │ PostgreSQL   │ │
                              │     │ │ (Multi-tenant)
                              │     │ └──────────────┘ │
                              │     └──────────────────┘
                              │
                         (Optional Direct HTTPS)
```

## Data Flow

### User Chat Interaction

```
1. User sends message in dashboard
   └─> React component → Axios API call

2. Message arrives at Cloud Nginx
   └─> HTTPS terminated
   └─> Routed to /api/chat

3. Cloud FastAPI authenticates request
   └─> Verifies JWT or API key
   └─> Identifies tenant_id from token
   └─> Checks usage limits

4. Cloud FastAPI proxies to Home vLLM server
   └─> Establishes WebSocket via WireGuard tunnel
   └─> Sends prompt + tenant context

5. Home vLLM performs inference
   └─> Retrieves relevant docs from Qdrant (RAG)
   └─> Streams tokens back via WireGuard

6. Cloud receives streamed tokens
   └─> Caches in Redis for repeat queries
   └─> Forwards to user browser via WebSocket

7. Browser renders tokens in real-time
   └─> User sees "typing" effect
   └─> Message history saved to PostgreSQL
```

### GitHub Push → Re-indexing Pipeline

```
1. Developer pushes to GitHub
   └─> GitHub Actions CI/CD workflow triggered

2. GitHub Actions builds frontend + tests backend
   └─> Deploys frontend to /var/www/saas-frontend
   └─> Copies updated backend code

3. GitHub Actions SSHs to Home Gentoo
   └─> Triggers POST /api/reindex endpoint

4. Home FastAPI re-loads data sources
   └─> Fetches latest from GitHub API
   └─> Updates resume, LinkedIn, portfolio
   └─> Re-builds Qdrant vector index

5. Vector DB contains fresh context
   └─> Next user chat uses latest info
```

## Multi-Tenancy Model

Your system supports three tenant types:

### 1. Demo Tenant (Your Portfolio)
- **slug**: `demo`
- **tier**: Free (unlimited, since it's your showcase)
- **data sources**: Your resume, GitHub repos, LinkedIn
- **URL**: `yourdomain.com/chat`

### 2. Free Tier Customers
- **max_monthly_tokens**: 100,000
- **max_concurrent_requests**: 5
- **knowledge_bases**: 1
- **pricing**: $0/month
- **access_method**: JWT from signup

### 3. Pro Tier Customers
- **max_monthly_tokens**: 1,000,000
- **max_concurrent_requests**: 50
- **knowledge_bases**: 10
- **pricing**: $29/month
- **access_method**: JWT + Stripe subscription

### 4. Enterprise Tier
- **max_monthly_tokens**: Unlimited
- **pricing**: Custom
- **access_method**: API keys + webhook integration

## Database Schema

### Core Tables

**tenants**
```
├─ id (UUID)
├─ name (String)
├─ slug (String, unique)
├─ tier (Enum: free|pro|enterprise)
├─ stripe_customer_id (String, nullable)
├─ max_monthly_tokens (Integer)
├─ max_concurrent_requests (Integer)
└─ created_at (DateTime)
```

**users**
```
├─ id (UUID)
├─ tenant_id (FK → tenants.id)
├─ email (String, unique)
├─ password_hash (String)
├─ role (Enum: admin|user|readonly)
└─ created_at (DateTime)
```

**api_keys**
```
├─ id (UUID)
├─ tenant_id (FK → tenants.id)
├─ key (String, unique) [Format: sk_live_xxxxx]
├─ secret_hash (String)
└─ last_used (DateTime, nullable)
```

**knowledge_bases**
```
├─ id (UUID)
├─ tenant_id (FK → tenants.id)
├─ name (String)
├─ storage_type (Enum: local|s3|github)
├─ doc_count (Integer)
├─ index_status (Enum: pending|indexing|ready|error)
└─ last_indexed (DateTime, nullable)
```

**chat_sessions**
```
├─ id (UUID)
├─ tenant_id (FK → tenants.id)
├─ knowledge_base_id (FK → knowledge_bases.id)
├─ title (String)
├─ total_tokens_used (Integer)
└─ created_at (DateTime)
```

**chat_messages**
```
├─ id (UUID)
├─ session_id (FK → chat_sessions.id)
├─ role (String: user|assistant)
├─ content (Text)
├─ prompt_tokens (Integer)
├─ completion_tokens (Integer)
├─ sources (JSON array)
└─ created_at (DateTime)
```

**usage_metrics**
```
├─ id (UUID)
├─ tenant_id (FK → tenants.id)
├─ date (DateTime)
├─ chat_sessions (Integer)
├─ total_prompt_tokens (Integer)
├─ total_completion_tokens (Integer)
└─ gpu_seconds_used (Float)
```

**invoices**
```
├─ id (UUID)
├─ tenant_id (FK → tenants.id)
├─ stripe_invoice_id (String)
├─ period_start (DateTime)
├─ period_end (DateTime)
├─ base_tier_cost (Float)
├─ overage_tokens (Integer)
├─ overage_cost (Float)
└─ total_amount (Float)
```

## Security Model

### Row-Level Security (RLS)
PostgreSQL enforces tenant isolation at the database level:

```sql
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON chat_sessions
USING (tenant_id = current_setting('app.current_tenant_id'));
```

### Authentication Layers

```
Layer 1: JWT Token (Web Dashboard)
├─ Issued by /api/auth/login
├─ Stored in localStorage
├─ Injected in every API request header
├─ Verified via jwt.decode(token, secret)
└─ Expires after 24 hours

Layer 2: API Key (Programmatic Access)
├─ Format: sk_live_xxxxx
├─ Issued by /api/api-keys
├─ Hashed in database (never stored plaintext)
├─ Verified via constant-time hash comparison
└─ No expiration (revoked manually)

Layer 3: Webhook Signature (External Events)
├─ GitHub: HMAC-SHA256 signature in X-Hub-Signature-256
├─ Stripe: HMAC signature in Stripe-Signature header
└─ Verified before processing any event
```

### Encryption
- **SSL/TLS**: All internet traffic encrypted (Nginx SSL termination)
- **WireGuard**: Private tunnel between cloud and home (kernel-level VPN)
- **Password**: Bcrypt with salt (never stored plaintext)
- **API Keys**: SHA256 hash in database (irreversible)

## Scalability Considerations

### Current Limits (Your Hardware)
- **GPU Memory**: 40GB (2x A4500)
- **Model Size**: Llama 70B with tensor parallelism
- **Concurrent Users**: ~32-64 with batching
- **Throughput**: ~100-150 tokens/second
- **Latency**: 50-150ms to first token

### Future Scaling Paths

**Vertical Scaling**
- Add more A100/H100 GPUs to home server
- Increase cloud instance specs (vCPU, RAM)
- Upgrade cloud storage (S3 for document backups)

**Horizontal Scaling**
- Deploy multiple GPU servers (one per customer tier)
- Use load balancer (Nginx or HAProxy) across API instances
- Replicate PostgreSQL (primary/replica setup)
- Distribute Redis across multiple nodes (Redis Cluster)

**Geographic Distribution**
- Edge servers in multiple regions (Cloudflare, Fastly)
- Regional databases (read replicas)
- Local Qdrant instances per region

## Cost Model

### Monthly Operating Costs
```
Home (Gentoo) Server:
  └─ Electricity: ~$40/month (2x A4500 at 300W each)

Cloud (Ubuntu) Server:
  └─ Compute: $5/month ($0.15/day on Hetzner or similar)

Domain + DNS:
  └─ Domain: ~$15/year (~$1.25/month)
  └─ Fixed IP Fiber: ~$100/month (existing)

Total: ~$146/month vs. $500+/month for equivalent cloud GPUs
```

### Revenue Model
```
Free Tier:
  └─ 100k tokens/month
  └─ Unlimited users (attract product-market fit)

Pro Tier:
  └─ $29/month
  └─ 1M tokens/month (~33k/day)
  └─ 10 knowledge bases
  └─ Email support

Enterprise:
  └─ Custom pricing
  └─ Unlimited tokens
  └─ 99.9% SLA
  └─ Dedicated support
  └─ White-label options
```

### Profitability Threshold
- Break-even at **5 Pro tier customers** (5 × $29 = $145/month)
- Profitable at **10+ Pro tier customers**
- Low CAC (Content Marketing + Developer Advocacy)

---

**Next Steps**: Refer to `02-backend-setup.md` for implementation details.
