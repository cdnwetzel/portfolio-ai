#!/usr/bin/env bash
# Periodic hands-free canary for the portfolio AI chat.
#
# Runs the self-test battery against the LIVE public endpoint and exits non-zero
# on regression — so a scheduler (cron / systemd timer) catches grounding outages
# *between* deploys (e.g. a service dying, an index going stale), not just at deploy.
#
# Install on the T5810 (it has .venv-diag with `websockets`; keeps test deps off the
# modest VPS). Targets the public URL, so it exercises the full Apache→proxy→tunnel
# →T5810 path exactly as a visitor would.
#
# Install (cron, every 30 min, on the T5810):
#   */30 * * * * /home/chris/ai/cwdotcom/scripts/selftest-canary.sh >> /var/log/portfolio-selftest.log 2>&1
# A non-zero exit makes cron email MAILTO (or your alerting) on failure.
set -euo pipefail

REPO="${REPO:-/home/chris/ai/cwdotcom}"
PY="${PY:-${REPO}/.venv-diag/bin/python}"
URL="${URL:-wss://dev.cwetzel.com/ws/chat}"
TS="$(date -u +%FT%TZ)"

if "${PY}" "${REPO}/scripts/selftest.py" --url "${URL}"; then
    echo "${TS}  canary PASS"
else
    echo "${TS}  canary FAIL — portfolio chat regression detected at ${URL}"
    exit 1
fi
