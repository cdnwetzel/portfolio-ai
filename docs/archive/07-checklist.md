# Launch Preparation Checklist

## Phase 1: Local Development (Week 1)

### Database & Backend
- [ ] Create PostgreSQL database locally (Docker)
- [ ] Initialize Alembic migrations
- [ ] Create initial migration: `alembic revision --autogenerate -m "Initial schema"`
- [ ] Test local database: `psql -h localhost -U saas_user -d saas_prod`
- [ ] Implement all models from `02-backend-setup.md`
- [ ] Create auth endpoints (signup, login)
- [ ] Create chat streaming endpoint
- [ ] Test JWT token generation and verification
- [ ] Implement usage tracking
- [ ] Create health check endpoint

### Frontend
- [ ] Initialize Vite + React project
- [ ] Install Shadcn UI components
- [ ] Create login/signup pages
- [ ] Create dashboard page
- [ ] Connect to local API
- [ ] Test authentication flow
- [ ] Test API calls with TanStack Query
- [ ] Setup routing with React Router

### Local Testing
- [ ] Run `docker-compose up -d` successfully
- [ ] Backend health check returns 200: `curl http://localhost:8000/health`
- [ ] Can sign up new user
- [ ] Can log in with created user
- [ ] Dashboard loads and fetches data
- [ ] No console errors in browser

## Phase 2: Cloud Infrastructure (Week 2)

### Cloud Server Setup (Ubuntu)
- [ ] Rent cloud server ($5/month VPS)
- [ ] Configure UFW firewall (allow 80, 443, 51820)
- [ ] Install Docker and Docker Compose
- [ ] Install Nginx
- [ ] Install Certbot
- [ ] Create deployment user: `sudo useradd -m -s /bin/bash deploy`
- [ ] Setup SSH key auth for deployment

### SSL Certificates
- [ ] Point DNS A record to cloud IP
- [ ] Run Certbot: `sudo certbot certonly --standalone -d app.yourdomain.com`
- [ ] Verify certificate: `sudo certbot certificates`
- [ ] Configure Certbot auto-renewal

### WireGuard Tunnel
- [ ] Generate WireGuard keys (Gentoo)
- [ ] Generate WireGuard keys (Cloud)
- [ ] Configure `/etc/wireguard/wg0.conf` on both servers
- [ ] Enable WireGuard on both servers
- [ ] Test tunnel: `ping 203.0.113.2` from Gentoo, `ping 203.0.113.1` from Cloud
- [ ] Verify tunnel survives reboot

### Nginx Configuration
- [ ] Upload `nginx.conf` to cloud server
- [ ] Test Nginx: `sudo nginx -t`
- [ ] Reload Nginx: `sudo systemctl reload nginx`
- [ ] Create `/var/www/saas-frontend` directory
- [ ] Test serving static files

### Environment Setup
- [ ] Create `.env.prod` on cloud server
- [ ] Set strong passwords for DB, JWT secret
- [ ] Configure Stripe keys in `.env.prod`
- [ ] Configure GitHub token in `.env.prod`

## Phase 3: CI/CD & Automation (Week 2)

### GitHub Repository
- [ ] Create private GitHub repo
- [ ] Initialize with README, .gitignore
- [ ] Push all code to main branch
- [ ] Create `.env.example` file (NO SECRETS)

### GitHub Secrets
- [ ] Add `CLOUD_IP` secret
- [ ] Add `CLOUD_SSH_KEY` secret (deploy private key)
- [ ] Add `STRIPE_SECRET_KEY` secret
- [ ] Add `STRIPE_WEBHOOK_SECRET` secret
- [ ] Add `SLACK_WEBHOOK` secret (optional)

### SSH Keys for CI/CD
- [ ] Generate deployment key: `ssh-keygen -t ed25519 -f ~/.ssh/deploy`
- [ ] Add public key to cloud server authorized_keys
- [ ] Test SSH: `ssh -i ~/.ssh/deploy ubuntu@cloud.ip.address`
- [ ] Add private key to GitHub secrets

### CI/CD Pipeline
- [ ] Create `.github/workflows/deploy.yml`
- [ ] Test workflow locally with `act` (optional)
- [ ] Commit workflow file
- [ ] Watch workflow run on GitHub
- [ ] Verify deployment succeeded

## Phase 4: Features & Testing (Week 3)

### Chat Functionality
- [ ] Implement RAG pipeline (Qdrant + vLLM)
- [ ] Create chat streaming endpoint `/ws/chat`
- [ ] Test WebSocket connection
- [ ] Verify streaming responses
- [ ] Test with actual LLM model
- [ ] Monitor GPU utilization

### Knowledge Base Management
- [ ] Implement document upload
- [ ] Implement document indexing to Qdrant
- [ ] Implement knowledge base CRUD endpoints
- [ ] Test with sample documents
- [ ] Verify retrieval in RAG pipeline

### Billing Integration
- [ ] Create Stripe account and products
- [ ] Get Stripe API keys
- [ ] Implement checkout session creation
- [ ] Implement webhook handler
- [ ] Test with Stripe test keys
- [ ] Verify usage tracking works
- [ ] Create billing page in frontend

### GitHub Integration
- [ ] Create GitHub webhook in your repo settings
- [ ] Implement webhook receiver endpoint
- [ ] Test with sample push event
- [ ] Verify re-indexing triggers on commit

## Phase 5: Pre-Launch (Week 4)

### Security Hardening
- [ ] Enable HTTPS on all endpoints
- [ ] Configure HSTS header in Nginx
- [ ] Enable rate limiting in Nginx
- [ ] Install Fail2Ban on cloud server
- [ ] Test password hashing (bcrypt)
- [ ] Verify API key hashing
- [ ] Test RLS in PostgreSQL
- [ ] Verify no secrets in git history

### Testing & QA
- [ ] Unit tests for auth
- [ ] Unit tests for billing calculations
- [ ] Integration tests for chat flow
- [ ] Load test with concurrent users
- [ ] Test error handling
- [ ] Test rollback procedure
- [ ] Test database backup/restore
- [ ] Test WireGuard tunnel failover

### Documentation
- [ ] Update README with setup instructions
- [ ] Document API endpoints (Swagger UI)
- [ ] Create user onboarding guide
- [ ] Create deployment runbook
- [ ] Document monitoring procedures

### Monitoring & Logging
- [ ] Setup log rotation (logrotate)
- [ ] Configure health checks
- [ ] Setup error tracking (Sentry, optional)
- [ ] Create alerting (Slack, email)
- [ ] Test alert delivery

### Backups
- [ ] Configure daily database backups
- [ ] Test backup restore procedure
- [ ] Store backups in S3 (optional)
- [ ] Document backup retention policy

## Phase 6: Launch! 🚀

### Final Checks
- [ ] All tests passing
- [ ] No pending migrations
- [ ] SSL certificate valid
- [ ] WireGuard tunnel stable
- [ ] Database backups working
- [ ] Monitoring active
- [ ] Health checks passing

### Soft Launch (Closed Beta)
- [ ] Deploy to production
- [ ] Invite beta users (friends, colleagues)
- [ ] Monitor for 24 hours
- [ ] Fix any issues found
- [ ] Collect feedback

### Public Launch
- [ ] Announce on Twitter/LinkedIn
- [ ] Add to relevant directories
- [ ] Create landing page
- [ ] Start content marketing
- [ ] Monitor metrics (signups, usage)

## Post-Launch

### Week 1
- [ ] Monitor error logs daily
- [ ] Respond to user feedback quickly
- [ ] Fix any bugs found
- [ ] Optimize slow endpoints

### Week 2-4
- [ ] Iterate on features based on feedback
- [ ] Add new models or capabilities
- [ ] Improve onboarding
- [ ] Implement feature requests

### Month 2+
- [ ] Scale based on usage
- [ ] Add white-label features
- [ ] Explore partnerships
- [ ] Optimize costs

## Resource Tracker

### Monthly Costs
```
Cloud Ubuntu Server:  $5
Stripe Processing:    ~2-3% per transaction
Domain/DNS:           ~$1
Gentoo Electricity:   ~$40
Total:                ~$50-60/month
```

### Break-Even Analysis
```
Revenue at 10 Pro users: 10 × $29 = $290/month
Costs:                   ~$60/month
Profit:                  ~$230/month

ROI Positive after:      5 Pro users
```

## Quick Reference Commands

```bash
# Deploy to production
./cloud/deploy.sh

# View logs
docker logs -f portfolio-saas-api-1

# Database shell
docker exec -it portfolio-saas-db-1 psql -U saas_user -d saas_prod

# Run migrations
docker-compose exec api alembic upgrade head

# Health check
curl https://app.yourdomain.com/health

# WireGuard status
sudo wg show

# SSL certificate expiry
sudo certbot certificates

# Backup database
docker exec portfolio-saas-db-1 pg_dump -U saas_user saas_prod > backup.sql
```

## Troubleshooting Quick Links

- Database issues → See `02-backend-setup.md`
- Frontend issues → See `03-frontend-setup.md`
- Infrastructure issues → See `04-infrastructure.md`
- Deployment issues → See `05-deployment.md`
- Billing issues → See `06-billing.md`

## Success Metrics

Track these metrics post-launch:

```
- Signups per week
- Active users per week
- Chats per user (engagement)
- API rate limit hits (scale indicator)
- Error rate (aim for <0.1%)
- Average response latency (aim for <200ms)
- GPU utilization (aim for 50-80%)
- Revenue MRR
```

---

**You're ready to launch!** Follow this checklist week by week, and you'll have a production-grade SaaS platform running.

Good luck! 🚀
