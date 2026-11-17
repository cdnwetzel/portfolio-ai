#!/usr/bin/env bash
# Periodic hands-free canary for the portfolio AI chat — the SECOND, external vantage.
#
# Runs the self-test battery against the LIVE PUBLIC endpoint from the home network, so it
# exercises the full Apache→proxy→tunnel→T5810 path exactly as a visitor would — catching
# public-path breakage (SSL, Apache, DNS) that the VPS-internal aggregator can't see. The
# VPS-side scripts/health_aggregate.py is the primary deep monitor; this is the cheap
# home-side complement.
#
# Install on the T5810 (it has .venv-diag with `websockets`; keeps test deps off the VPS).
#
# On regression it pushes an ntfy alert (same channel as the VPS monitor) AND exits non-zero.
# Set NTFY_URL to your private topic — without it, it only logs + exits non-zero (relying on
# cron MAILTO, which is easy to miss). Config lives in /etc/portfolio-canary.env if present.
#
# Install (cron, every 30 min, on the T5810):
#   */30 * * * * /home/chris/ai/cwdotcom/scripts/selftest-canary.sh >> /var/log/portfolio-selftest.log 2>&1
set -euo pipefail

# Optional config file (NTFY_URL, overrides). Keep it 0600; not in the repo.
[ -f /etc/portfolio-canary.env ] && . /etc/portfolio-canary.env

REPO="${REPO:-/home/chris/ai/cwdotcom}"
PY="${PY:-${REPO}/.venv-diag/bin/python}"
URL="${URL:-wss://dev.cwetzel.com/ws/chat}"
NTFY_URL="${NTFY_URL:-}"
TS="$(date -u +%FT%TZ)"

# Simple flap suppression: only push when state changes (PASS<->FAIL), so a sustained
# outage doesn't ntfy every 30 min. State file records the last outcome.
STATE_FILE="${STATE_FILE:-/tmp/portfolio-canary.state}"
prev="$(cat "${STATE_FILE}" 2>/dev/null || echo unknown)"

notify() {  # title, message, priority, tags
    [ -z "${NTFY_URL}" ] && return 0
    curl -s -H "Title: $1" -H "Priority: $3" -H "Tags: $4" -d "$2" "${NTFY_URL}" >/dev/null || true
}

if "${PY}" "${REPO}/scripts/selftest.py" --url "${URL}"; then
    echo "${TS}  canary PASS"
    if [ "${prev}" = "fail" ]; then
        notify "Portfolio AI canary recovered" "Public endpoint ${URL} is answering again." "default" "white_check_mark"
    fi
    echo pass > "${STATE_FILE}"
else
    echo "${TS}  canary FAIL — portfolio chat regression detected at ${URL}"
    if [ "${prev}" != "fail" ]; then
        notify "Portfolio AI canary FAIL" "Public endpoint ${URL} failed the self-test (grounding regression or outage on the Apache->proxy->tunnel path)." "urgent" "rotating_light"
    fi
    echo fail > "${STATE_FILE}"
    exit 1
fi
