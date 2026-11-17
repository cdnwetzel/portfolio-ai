#!/usr/bin/env bash
# Provision the faithfulness verifier-service on the spare Ryzen / RTX 3060 Ti box
# (verifier-faithfulness-layer.md §6.6). Mirrors home/setup-t5810-services.sh.
#
# Prereqs on the target box:
#   - Python at the path below (override with PYBIN)
#   - A judge model reachable at JUDGE_URL. Default = local Ollama:
#       ollama pull qwen2.5:7b-instruct-q4_K_M     (~5.5-6 GB on the 3060 Ti)
#   - pip install -r home/verifier-service/requirements.txt into that python
#
# This is a SEPARATE box from the T5810 — set VERIFIER_HOST to its SSH target.
# Usage:  VERIFIER_HOST=chris@<RYZEN_LAN_IP> ./home/setup-verifier.sh
#
# VERIFIER_BIND (optional): the address uvicorn binds to on the box. Default 127.0.0.1
# (localhost-only). Set it to the box's LAN IP so the T5810 tunnel (-L 8007:<ip>:8007)
# can reach it while nothing else on the LAN can — recommended over the old 0.0.0.0 bind.
#   Usage:  VERIFIER_HOST=chris@<asrock-lan-ip> VERIFIER_BIND=<asrock-lan-ip> ./home/setup-verifier.sh
set -euo pipefail

VHOST="${VERIFIER_HOST:?set VERIFIER_HOST=chris@<RYZEN_LAN_IP> (the spare box, not the T5810)}"
VBIND="${VERIFIER_BIND:-127.0.0.1}"
PYBIN="${PYBIN:-/home/chris/miniforge3/bin/python3}"
OPTDIR="/opt/verifier-service"
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${HERE}/verifier-service"

echo "==> Installing verifier-service -> ${VHOST}:${OPTDIR}"
ssh "${VHOST}" "mkdir -p ${OPTDIR}"
scp -q "${SRC}/verifier.py"      "${VHOST}:${OPTDIR}/verifier.py"
scp -q "${SRC}/verifier_core.py" "${VHOST}:${OPTDIR}/verifier_core.py"
scp -q "${SRC}/requirements.txt" "${VHOST}:${OPTDIR}/requirements.txt"
scp -q "${SRC}/verifier-service.openrc" "${VHOST}:/tmp/verifier-service.openrc"

echo "==> Installing deps + OpenRC unit (assumes Gentoo/OpenRC; see README for systemd)"
ssh "${VHOST}" "
  set -e
  chown -R chris:chris ${OPTDIR} && chmod +x ${OPTDIR}/verifier.py
  ${PYBIN} -m pip install -q -r ${OPTDIR}/requirements.txt
  # Persist the bind address so uvicorn listens on the intended interface across restarts.
  touch /etc/conf.d/verifier-service
  sed -i '/^export VERIFIER_BIND=/d' /etc/conf.d/verifier-service
  echo 'export VERIFIER_BIND=${VBIND}' >> /etc/conf.d/verifier-service
  if [ -d /etc/init.d ] && command -v rc-update >/dev/null 2>&1; then
    cp /tmp/verifier-service.openrc /etc/init.d/verifier-service && chmod 755 /etc/init.d/verifier-service
    rc-update add verifier-service default 2>/dev/null || true
    rc-service verifier-service restart 2>/dev/null || rc-service verifier-service start
  else
    echo 'NOTE: not an OpenRC box — start manually or install a systemd unit (see README).'
  fi
"

echo "==> Verifying health (on the configured bind address: ${VBIND})"
ssh "${VHOST}" "curl -sf http://${VBIND}:8007/health && echo || echo UNREACHABLE"
echo "==> Done. verifier-service on :8007. Run judge-accuracy: python3 home/verifier-service/run_fixtures.py --url http://<box>:8007"
