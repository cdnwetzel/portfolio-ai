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
set -euo pipefail

VHOST="${VERIFIER_HOST:?set VERIFIER_HOST=chris@<RYZEN_LAN_IP> (the spare box, not the T5810)}"
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
  if [ -d /etc/init.d ] && command -v rc-update >/dev/null 2>&1; then
    cp /tmp/verifier-service.openrc /etc/init.d/verifier-service && chmod 755 /etc/init.d/verifier-service
    rc-update add verifier-service default 2>/dev/null || true
    rc-service verifier-service restart 2>/dev/null || rc-service verifier-service start
  else
    echo 'NOTE: not an OpenRC box — start manually or install a systemd unit (see README).'
  fi
"

echo "==> Verifying health"
ssh "${VHOST}" 'curl -sf http://127.0.0.1:8007/health && echo || echo UNREACHABLE'
echo "==> Done. verifier-service on :8007. Run judge-accuracy: python3 home/verifier-service/run_fixtures.py --url http://<box>:8007"
