#!/bin/bash
set -e

echo "=== cwetzel.com FastAPI Proxy Setup ==="

# Install dependencies
apt-get update -qq
apt-get install -y nginx python3 python3-pip certbot python3-certbot-nginx > /dev/null 2>&1

# Create directories
mkdir -p /var/www/dev.cwetzel.com
mkdir -p /opt/api-proxy
mkdir -p /var/log/api-proxy

# Setup DNS for ai.cwetzel.com (resolve to SSH tunnel endpoint)
if ! grep -q "ai.cwetzel.com" /etc/hosts; then
    echo "127.0.0.1 ai.cwetzel.com" >> /etc/hosts
fi

# Create service user
useradd -m -s /bin/bash -d /home/apiproxy apiproxy 2>/dev/null || true
chown apiproxy:apiproxy /opt/api-proxy /var/log/api-proxy

# Install Python deps
pip install fastapi uvicorn httpx --no-cache-dir 2>/dev/null || true

# Copy API proxy
cp api-proxy.py /opt/api-proxy/main.py
chown apiproxy:apiproxy /opt/api-proxy/main.py

# === FastAPI Systemd Service ===
cat > /etc/systemd/system/api-proxy.service <<'EOF'
[Unit]
Description=Portfolio AI API Proxy
After=network.target

[Service]
Type=simple
User=apiproxy
Group=apiproxy
WorkingDirectory=/opt/api-proxy
ExecStart=/usr/local/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000 --log-level info

Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=api-proxy

[Install]
WantedBy=multi-user.target
EOF

# === Nginx Config ===
mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled
cp nginx-dev.cwetzel.com.conf /etc/nginx/sites-available/dev.cwetzel.com
ln -sf /etc/nginx/sites-available/dev.cwetzel.com /etc/nginx/sites-enabled/dev.cwetzel.com

# Test and reload Nginx
nginx -t
systemctl reload nginx

# Enable and start API proxy
systemctl daemon-reload
systemctl enable api-proxy.service
systemctl restart api-proxy.service

# Setup SSL with Let's Encrypt
echo "=== SSL Setup ==="
if [ ! -f /etc/letsencrypt/live/dev.cwetzel.com/fullchain.pem ]; then
    echo "Setting up SSL for dev.cwetzel.com..."
    certbot certonly --nginx -d dev.cwetzel.com --non-interactive --agree-tos -m cwe@thepslawfirm.com --no-eff-email
else
    echo "SSL cert already exists"
fi

systemctl reload nginx

echo "=== Service Status ==="
systemctl status api-proxy.service --no-pager || true

echo "=== Port Status ==="
netstat -tlnp 2>/dev/null | grep -E ':(80|443|8000)' || ss -tlnp 2>/dev/null | grep -E ':(80|443|8000)' || echo "Checking..."

echo "✓ Proxy setup complete"
echo "  Frontend: https://dev.cwetzel.com (serve React here)"
echo "  API: /api/* → localhost:8000 → T5810"
