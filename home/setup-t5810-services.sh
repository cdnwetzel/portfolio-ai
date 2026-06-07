#!/bin/bash
set -e

echo "=== T5810 vLLM + Qdrant Setup ==="

# Setup hostname resolution for ai.cwetzel.com (self-reference)
if ! grep -q "ai.cwetzel.com" /etc/hosts; then
    echo "127.0.0.1 ai.cwetzel.com" >> /etc/hosts
fi

# Create service user
useradd -m -s /bin/bash -d /home/vllm vllm 2>/dev/null || true

# Create directories
mkdir -p /opt/vllm /opt/qdrant /var/log/vllm /var/log/qdrant
chown vllm:vllm /opt/vllm /opt/qdrant /var/log/vllm /var/log/qdrant

# Install Python deps (if not already installed)
pip install vllm torch transformers --no-cache-dir 2>/dev/null || true

# === vLLM Service ===
cat > /etc/systemd/system/vllm-qwen.service <<'EOF'
[Unit]
Description=vLLM Qwen 14B Inference Server
After=network.target
StartLimitInterval=200
StartLimitBurst=5

[Service]
Type=simple
User=vllm
Group=vllm
WorkingDirectory=/opt/vllm
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
Environment="CUDA_VISIBLE_DEVICES=0,1"
Environment="VLLM_TENSOR_PARALLEL_SIZE=2"
ExecStart=/usr/local/bin/python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-14B \
  --port 8001 \
  --dtype bfloat16 \
  --max-model-len 8192 \
  --tensor-parallel-size 2 \
  --gpu-memory-utilization 0.85

Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=vllm

[Install]
WantedBy=multi-user.target
EOF

# === Qdrant Service ===
cat > /etc/systemd/system/qdrant.service <<'EOF'
[Unit]
Description=Qdrant Vector Database
After=network.target
StartLimitInterval=200
StartLimitBurst=5

[Service]
Type=simple
User=vllm
Group=vllm
WorkingDirectory=/opt/qdrant
ExecStart=/usr/local/bin/qdrant --listen-addr 0.0.0.0:6333 --storage-path /opt/qdrant/storage

Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=qdrant

[Install]
WantedBy=multi-user.target
EOF

# Reload and enable services
systemctl daemon-reload
systemctl enable vllm-qwen.service qdrant.service
systemctl restart vllm-qwen.service qdrant.service

echo "Waiting for services to start..."
sleep 5

echo "=== Service Status ==="
systemctl status vllm-qwen.service --no-pager || true
systemctl status qdrant.service --no-pager || true

echo "=== Port Status ==="
netstat -tlnp 2>/dev/null | grep -E ':(8001|6333)' || ss -tlnp 2>/dev/null | grep -E ':(8001|6333)' || echo "Ports not yet listening (services starting)"

echo "✓ Setup complete. vLLM on :8001, Qdrant on :6333"
