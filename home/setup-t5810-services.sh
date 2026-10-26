#!/usr/bin/env bash
# Provision the Portfolio AI CPU services on the T5810 (Gentoo / OpenRC) from this repo:
#   - embed-service  (BAAI/bge-base-en-v1.5, 768-d, port 8005)
#   - rerank-service (bge-reranker-base, port 8006)
# Both run as the service user via supervise-daemon. Models download from HuggingFace
# on first start (or use the existing ~/.cache if present).
#
# NOT managed here (separate concerns, their own OpenRC services on the T5810):
#   - pscode-vllm (8004)  — the Qwen2.5-Coder-14B + pscode-prod LoRA server
#   - Qdrant (6333)       — vector DB
#
# Run from the repo root on a machine with SSH access to the T5810.
# Usage:  ./home/setup-t5810-services.sh
# Env:    T5810_HOST (required; set it in .deploy.env)
set -euo pipefail
# Operator-local host names and the service user (.deploy.env, gitignored; see .deploy.env.example)
ENVF="$(cd "$(dirname "$0")/.." && pwd)/.deploy.env"; [ -f "$ENVF" ] && . "$ENVF"

T5810="${T5810_HOST:?set T5810_HOST (see .deploy.env.example)}"
SVC_USER="${SVC_USER:-user}"
# The units name a generic `user`; install them for the real service user.
localize() { SVC_USER="$SVC_USER" perl -pe 's#/home/user(?=/|\b)#/home/$ENV{SVC_USER}#g; s#\buser:user\b#$ENV{SVC_USER}:$ENV{SVC_USER}#g; s#(_USER:=)user\}#$1$ENV{SVC_USER}}#g' "$1"; }
HERE="$(cd "$(dirname "$0")" && pwd)"

install_service() {
  local name="$1" src="$2" pyfile="$3" initfile="$4" optdir="$5"
  echo "==> Installing ${name} -> ${optdir}"
  ssh "${T5810}" "mkdir -p ${optdir}"
  localize "${src}/${pyfile}"   | ssh "${T5810}" "cat > ${optdir}/${pyfile}"
  localize "${src}/${initfile}" | ssh "${T5810}" "cat > /tmp/${name}.openrc"
  ssh "${T5810}" "
    set -e
    chown -R ${SVC_USER}:${SVC_USER} ${optdir} && chmod +x ${optdir}/${pyfile}
    cp /tmp/${name}.openrc /etc/init.d/${name} && chmod 755 /etc/init.d/${name}
    rc-update add ${name} default 2>/dev/null || true
    rc-service ${name} restart 2>/dev/null || rc-service ${name} start
  "
}

install_service embed-service  "${HERE}/embed-service"  embed.py  embed-service.openrc  /opt/embed-service
install_service rerank-service "${HERE}/rerank-service" rerank.py rerank-service.openrc /opt/rerank-service

echo "==> Verifying health"
ssh "${T5810}" 'for p in 8005 8006; do printf "  port %s: " "$p"; curl -sf http://127.0.0.1:$p/health && echo || echo UNREACHABLE; done'
echo "==> Done. embed-service (8005) + rerank-service (8006) provisioned."
