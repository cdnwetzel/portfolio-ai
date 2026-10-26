# Deployment & CI/CD Guide

## Deployment Script

**cloud/deploy.sh** (Make executable: `chmod +x`):

```bash
#!/bin/bash
set -e

echo "🚀 Starting deployment to production..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
CLOUD_USER=${CLOUD_USER:-ubuntu}
CLOUD_HOST=${CLOUD_HOST:-app.yourdomain.com}
CLOUD_IP=${CLOUD_IP:-your.cloud.ip.address}
SSH_KEY=${SSH_KEY:-~/.ssh/deploy}

# 1. Build Frontend
echo -e "${YELLOW}📦 Building React frontend...${NC}"
cd frontend && npm run build && cd ..

# 2. Sync Frontend to Cloud
echo -e "${YELLOW}📤 Syncing frontend to cloud...${NC}"
rsync -avz --delete \
    -e "ssh -i ${SSH_KEY}" \
    frontend/dist/ \
    ${CLOUD_USER}@${CLOUD_IP}:/var/www/saas-frontend/

# 3. Sync Backend Code
echo -e "${YELLOW}📤 Syncing backend code...${NC}"
rsync -avz \
    -e "ssh -i ${SSH_KEY}" \
    src/ requirements.txt Dockerfile .env.prod \
    ${CLOUD_USER}@${CLOUD_IP}:/opt/portfolio-saas/

# 4. Remote Operations
echo -e "${YELLOW}⚙️ Running remote deployment...${NC}"
ssh -i ${SSH_KEY} ${CLOUD_USER}@${CLOUD_IP} << 'REMOTE_EOF'
    set -e
    
    cd /opt/portfolio-saas
    
    # Copy environment
    cp .env.prod .env
    
    # Build and start containers
    echo "Starting Docker containers..."
    docker-compose up -d --build
    
    # Wait for services
    sleep 5
    
    # Run migrations
    echo "Running database migrations..."
    docker-compose exec -T api alembic upgrade head
    
    # Clean up
    docker image prune -f
    
    echo "Deployment complete!"
REMOTE_EOF

echo -e "${GREEN}✅ Deployment successful!${NC}"
echo -e "${GREEN}Check https://app.yourdomain.com${NC}"
```

## GitHub Actions CI/CD

**.github/workflows/deploy.yml**:

```yaml
name: Deploy SaaS Platform

on:
  push:
    branches: [ main ]
    paths:
      - 'src/**'
      - 'frontend/**'
      - 'requirements.txt'
      - '.github/workflows/deploy.yml'
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_DB: saas_test
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        cache: 'pip'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-asyncio
    
    - name: Run tests
      env:
        DATABASE_URL: postgresql+asyncpg://postgres:test@localhost/saas_test
      run: pytest tests/ -v

  build-frontend:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Setup Node
      uses: actions/setup-node@v4
      with:
        node-version: '18'
        cache: 'npm'
        cache-dependency-path: 'frontend/package-lock.json'
    
    - name: Install dependencies
      run: cd frontend && npm ci
    
    - name: Build
      run: cd frontend && npm run build
    
    - name: Upload artifact
      uses: actions/upload-artifact@v3
      with:
        name: frontend-dist
        path: frontend/dist/

  deploy:
    needs: [test, build-frontend]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Download frontend
      uses: actions/download-artifact@v3
      with:
        name: frontend-dist
        path: frontend-dist/
    
    - name: Setup SSH
      run: |
        mkdir -p ~/.ssh
        echo "${{ secrets.CLOUD_SSH_KEY }}" > ~/.ssh/deploy
        chmod 600 ~/.ssh/deploy
        ssh-keyscan -H ${{ secrets.CLOUD_IP }} >> ~/.ssh/known_hosts
    
    - name: Deploy frontend
      run: |
        rsync -avz --delete \
          -e "ssh -i ~/.ssh/deploy" \
          frontend-dist/ \
          ubuntu@${{ secrets.CLOUD_IP }}:/var/www/saas-frontend/
    
    - name: Deploy backend
      run: |
        rsync -avz \
          -e "ssh -i ~/.ssh/deploy" \
          src/ requirements.txt Dockerfile \
          ubuntu@${{ secrets.CLOUD_IP }}:/opt/portfolio-saas/
    
    - name: Restart services
      run: |
        ssh -i ~/.ssh/deploy ubuntu@${{ secrets.CLOUD_IP }} << 'EOF'
          cd /opt/portfolio-saas
          docker-compose up -d --build
          docker-compose exec -T api alembic upgrade head
        EOF
    
    - name: Health check
      run: |
        ssh -i ~/.ssh/deploy ubuntu@${{ secrets.CLOUD_IP }} \
          'curl -s https://app.yourdomain.com/health | jq .'
    
    - name: Notify Slack
      if: always()
      uses: 8398a7/action-slack@v3
      with:
        status: ${{ job.status }}
        text: 'Deployment ${{ job.status }}'
        webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

## GitHub Secrets Setup

In your GitHub repo: **Settings → Secrets and Variables → Actions**

Add these secrets:

| Name | Value |
|------|-------|
| `CLOUD_IP` | Your cloud server public IP |
| `CLOUD_SSH_KEY` | Contents of `~/.ssh/deploy` (private key) |
| `STRIPE_SECRET_KEY` | Your Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Your Stripe webhook secret |
| `SLACK_WEBHOOK` | (Optional) Slack webhook for notifications |

## SSH Key Generation for CI/CD

```bash
# Generate deployment key
ssh-keygen -t ed25519 -f ~/.ssh/deploy -N "" -C "github-actions"

# Copy public key to cloud server
ssh-copy-id -i ~/.ssh/deploy.pub ubuntu@your.cloud.ip.address

# Verify
ssh -i ~/.ssh/deploy ubuntu@your.cloud.ip.address 'echo Connected'

# View private key (for GitHub secrets)
cat ~/.ssh/deploy
```

## Production Environment File

**cloud/.env.prod** (Create on server, NOT in git):

```
# Database
DATABASE_URL=postgresql+asyncpg://saas_user:STRONG_PASSWORD@db:5432/saas_prod
REDIS_URL=redis://redis:6379/0

# JWT
JWT_SECRET_KEY=your-super-secret-production-key-change-this
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Stripe
STRIPE_SECRET_KEY=sk_live_xxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxx

# GitHub
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_WEBHOOK_SECRET=your_webhook_secret

# Application
DEBUG=False
LOG_LEVEL=INFO
FRONTEND_URL=https://app.yourdomain.com
```

## Deployment Checklist

### Pre-Deployment
- [ ] All tests passing locally
- [ ] Frontend builds without errors
- [ ] `.env.prod` created on cloud server
- [ ] SSL certificate valid (check expiry)
- [ ] Database backup taken
- [ ] GitHub secrets configured

### Deployment
- [ ] Run `./cloud/deploy.sh` or push to main
- [ ] Monitor logs: `docker logs -f portfolio-saas-api-1`
- [ ] Check health: `curl https://app.yourdomain.com/health`
- [ ] Test login flow
- [ ] Verify WebSocket chat works
- [ ] Check Stripe webhook (test event)

### Post-Deployment
- [ ] Monitor error logs for 10 minutes
- [ ] Test key user flows
- [ ] Verify database migrations applied
- [ ] Check WireGuard tunnel stability
- [ ] Test rate limiting

## Rollback Procedure

If deployment fails:

```bash
# SSH to cloud server
ssh ubuntu@your.cloud.ip.address

# Check logs
docker-compose logs api

# Rollback to previous image
docker-compose down
git checkout HEAD~1
docker-compose up -d --build

# Or manually revert frontend
rsync -avz git@github.com:youruser/portfolio-saas.git/dist/ /var/www/saas-frontend/
```

## Monitoring & Logging

**View API logs**:
```bash
docker logs -f portfolio-saas-api-1

# Or via SSH
ssh ubuntu@your.cloud.ip.address 'docker logs -f portfolio-saas-api-1'
```

**View database logs**:
```bash
docker logs -f portfolio-saas-db-1
```

**View Nginx logs**:
```bash
docker logs -f portfolio-saas-nginx-1
```

## Scheduled Tasks (Cron)

**Database backup** (On cloud server):
```bash
# /etc/cron.d/backup-saas
0 2 * * * root docker-compose -f /opt/portfolio-saas/docker-compose.yml exec -T db pg_dump -U saas_user saas_prod | gzip > /backup/saas_$(date +\%Y\%m\%d).sql.gz
```

**SSL renewal** (Automatic via Certbot):
```bash
# Certbot runs automatically via systemd timer
sudo systemctl list-timers certbot
```

---

**Next Steps**: Refer to `06-billing.md` for Stripe integration.
