# Infrastructure & Deployment Guide

## Local Development Environment

### docker-compose.yml (Local)

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: saas_prod
      POSTGRES_USER: saas_user
      POSTGRES_PASSWORD: saas_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U saas_user"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  api:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=postgresql+asyncpg://saas_user:saas_password@db:5432/saas_prod
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET_KEY=your-local-secret-key
      - DEBUG=True
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - .:/app
    command: uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

volumes:
  postgres_data:
  redis_data:
```

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Cloud Deployment (Ubuntu)

### Production docker-compose.yml

**cloud/docker-compose.yml**:

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    restart: always
    environment:
      POSTGRES_DB: saas_prod
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - saas_network

  redis:
    image: redis:7-alpine
    restart: always
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    networks:
      - saas_network

  api:
    build:
      context: ..
      dockerfile: Dockerfile
    restart: always
    environment:
      - DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@db:5432/saas_prod
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY}
      - DEBUG=False
      - LOG_LEVEL=INFO
    depends_on:
      - db
      - redis
    networks:
      - saas_network
    expose:
      - "8000"

  nginx:
    image: nginx:alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - /var/www/saas-frontend:/var/www/saas-frontend:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - api
    networks:
      - saas_network

networks:
  saas_network:
    driver: bridge

volumes:
  postgres_data:
  redis_data:
```

### Nginx Configuration

**cloud/nginx.conf**:

```nginx
events {
    worker_connections 1024;
}

http {
    # Upstream API
    upstream api {
        server api:8000;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/s;

    server {
        listen 80;
        server_name app.yourdomain.com;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name app.yourdomain.com;

        ssl_certificate /etc/letsencrypt/live/app.yourdomain.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/app.yourdomain.com/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;

        # Serve React frontend
        location / {
            root /var/www/saas-frontend;
            try_files $uri $uri/ /index.html;
            expires 1d;
            add_header Cache-Control "public, immutable";
        }

        # API proxy
        location /api/ {
            limit_req zone=api_limit burst=200 nodelay;
            
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_buffering off;
            proxy_request_buffering off;
            proxy_http_version 1.1;
        }

        # WebSocket support
        location /ws/ {
            proxy_pass http://api;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_read_timeout 86400;
        }
    }
}
```

## WireGuard Setup

### Home (Gentoo) Configuration

**Create keys**:
```bash
mkdir -p /etc/wireguard
cd /etc/wireguard
wg genkey | tee privatekey | wg pubkey > publickey
chmod 600 privatekey
```

**wg0.conf**:
```ini
[Interface]
PrivateKey = <YOUR_GENTOO_PRIVATEKEY>
Address = 203.0.113.1/24
ListenPort = 51820
DNS = 1.1.1.1

PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -A FORWARD -o wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -D FORWARD -o wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

[Peer]
PublicKey = <YOUR_CLOUD_PUBLICKEY>
AllowedIPs = 203.0.113.2/32
Endpoint = <CLOUD_PUBLIC_IP>:51820
PersistentKeepalive = 25
```

**Enable**:
```bash
sudo rc-service wireguard start
sudo rc-update add wireguard default
```

### Cloud (Ubuntu) Configuration

**wg0.conf**:
```ini
[Interface]
PrivateKey = <YOUR_CLOUD_PRIVATEKEY>
Address = 203.0.113.2/24
ListenPort = 51820
DNS = 1.1.1.1

PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -A FORWARD -o wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -D FORWARD -o wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

[Peer]
PublicKey = <YOUR_GENTOO_PUBLICKEY>
AllowedIPs = 203.0.113.1/32
Endpoint = <YOUR_HOME_FIXED_IP>:51820
PersistentKeepalive = 25
```

**Enable**:
```bash
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0
sudo wg show
```

## SSL Certificate Setup

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Get certificate
sudo certbot certonly --standalone -d app.yourdomain.com

# Auto-renewal
sudo certbot renew --dry-run
```

## Health Checks & Monitoring

**Systemd unit (Gentoo)**:

```ini
[Unit]
Description=Portfolio AI SaaS Backend
After=network.target wireguard.target

[Service]
Type=simple
User=portfolio
WorkingDirectory=/opt/portfolio-saas
EnvironmentFile=/opt/portfolio-saas/.env
ExecStart=/opt/portfolio-saas/venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

## Production Checklist

- [ ] SSL certificates generated via Certbot
- [ ] Nginx configured with rate limiting
- [ ] PostgreSQL backups scheduled (daily to S3)
- [ ] WireGuard tunnel verified stable
- [ ] Health checks returning 200 OK
- [ ] Logs configured with logrotate
- [ ] Fail2Ban installed and configured
- [ ] Firewall (UFW) configured (allow 80, 443, 51820)
- [ ] Database replicas for disaster recovery (optional)
- [ ] Prometheus/Grafana for monitoring (optional)

---

**Next Steps**: Refer to `05-deployment.md` for CI/CD setup.
