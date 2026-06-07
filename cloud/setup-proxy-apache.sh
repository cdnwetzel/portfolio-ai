#!/bin/bash
set -e

echo "=== cwetzel.com FastAPI Proxy Setup (Apache) ==="

# Install Python deps
pip3 install fastapi uvicorn httpx --no-cache-dir 2>/dev/null || true

# Create directories
mkdir -p /var/www/dev.cwetzel.com
mkdir -p /opt/api-proxy
mkdir -p /var/log/api-proxy

# Create service user
useradd -m -s /bin/bash -d /home/apiproxy apiproxy 2>/dev/null || true
chown apiproxy:apiproxy /opt/api-proxy /var/log/api-proxy

# Copy API proxy
cp api-proxy.py /opt/api-proxy/main.py
chown apiproxy:apiproxy /opt/api-proxy/main.py

# Setup hostname resolution for ai.cwetzel.com
if ! grep -q "ai.cwetzel.com" /etc/hosts; then
    echo "127.0.0.1 ai.cwetzel.com" >> /etc/hosts
fi

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
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 127.0.0.1 --port 8000 --log-level info

Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=api-proxy

[Install]
WantedBy=multi-user.target
EOF

# === Issue SSL Certificate ===
echo "=== SSL Setup ==="
if [ ! -f /etc/letsencrypt/live/dev.cwetzel.com/fullchain.pem ]; then
    echo "Issuing SSL cert for dev.cwetzel.com..."
    certbot certonly --standalone -d dev.cwetzel.com --non-interactive --agree-tos -m cwe@thepslawfirm.com --no-eff-email
else
    echo "SSL cert already exists"
fi

# === Apache VHost Config ===
cat > /etc/apache2/sites-available/dev.cwetzel.com.conf <<'EOF'
<VirtualHost *:80>
    ServerName dev.cwetzel.com
    Redirect permanent / https://dev.cwetzel.com/
</VirtualHost>

<VirtualHost *:443>
    ServerName dev.cwetzel.com
    DocumentRoot /var/www/dev.cwetzel.com

    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/dev.cwetzel.com/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/dev.cwetzel.com/privkey.pem
    SSLProtocol TLSv1.2 TLSv1.3
    SSLCipherSuite HIGH:!aNULL:!MD5

    # Security Headers
    Header set Strict-Transport-Security "max-age=31536000; includeSubDomains"
    Header set X-Content-Type-Options "nosniff"
    Header set X-Frame-Options "SAMEORIGIN"
    Header set X-XSS-Protection "1; mode=block"

    # Enable proxy modules
    <IfModule mod_proxy.c>
        ProxyPreserveHost On
        ProxyRequests Off

        # API proxy
        <Location /api/>
            ProxyPass http://127.0.0.1:8000/api/
            ProxyPassReverse http://127.0.0.1:8000/api/
        </Location>

        # WebSocket proxy
        <Location /ws/>
            ProxyPass ws://127.0.0.1:8000/ws/
            ProxyPassReverse ws://127.0.0.1:8000/ws/
        </Location>
    </IfModule>

    # React static files
    <IfModule mod_expires.c>
        ExpiresActive On
        ExpiresByType text/html "access plus 1 hour"
        ExpiresByType application/javascript "access plus 1 year"
        ExpiresByType text/css "access plus 1 year"
        ExpiresByType image/* "access plus 1 year"
    </IfModule>

    # SPA routing: all non-API requests go to index.html
    <IfModule mod_rewrite.c>
        RewriteEngine On
        RewriteBase /
        RewriteRule ^index\.html$ - [L]
        RewriteCond %{REQUEST_FILENAME} !-f
        RewriteCond %{REQUEST_FILENAME} !-d
        RewriteRule . /index.html [L]
    </IfModule>

    # Health check
    <Location /_health>
        SetHandler default-handler
    </Location>

    # Logs
    ErrorLog ${APACHE_LOG_DIR}/dev.cwetzel.com-error.log
    CustomLog ${APACHE_LOG_DIR}/dev.cwetzel.com-access.log combined
</VirtualHost>
EOF

# Enable modules
a2enmod proxy proxy_http proxy_wstunnel rewrite headers expires ssl > /dev/null 2>&1

# Enable site
a2ensite dev.cwetzel.com > /dev/null 2>&1

# Test Apache config
apache2ctl configtest

# Enable and start API proxy
systemctl daemon-reload
systemctl enable api-proxy.service
systemctl restart api-proxy.service

# Reload Apache
systemctl reload apache2

echo "=== Service Status ==="
systemctl status api-proxy.service --no-pager || true

echo ""
echo "=== Port Status ==="
netstat -tlnp 2>/dev/null | grep -E ':(80|443|8000)' || ss -tlnp 2>/dev/null | grep -E ':(80|443|8000)' || echo "Checking..."

echo ""
echo "✓ Apache proxy setup complete"
echo "  Frontend: https://dev.cwetzel.com (serve React here)"
echo "  API: /api/* → localhost:8000 → ai.cwetzel.com (via SSH tunnel)"
echo "  WebSocket: /ws/* → ws://localhost:8000 (via SSH tunnel)"
