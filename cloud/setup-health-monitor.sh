#!/usr/bin/env bash
# Provision the Portfolio AI health monitor on the VPS (cwetzel.com, Ubuntu/systemd).
#
# Deploys the deep aggregator + its two reused scripts to /opt/portfolio-health, installs
# the systemd probe/heartbeat/alert units, and enables the timers. Alerting config
# (ntfy topic + optional healthchecks.io URL) lives in /etc/default/portfolio-health,
# which this script creates from a template on first run (edit it, then re-run or
# `systemctl start portfolio-health.service`).
#
# The E2E smoke uses the `websockets` client already present on the VPS (v16.0).
#
# Run from the repo root on a machine with SSH access to the VPS.
# Usage:  ./cloud/setup-health-monitor.sh
# Env:    CLOUD_HOST (default root@cwetzel.com)
set -euo pipefail

CLOUD="${CLOUD_HOST:-root@cwetzel.com}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "${HERE}/.." && pwd)"
DIR="/opt/portfolio-health"

echo "==> Deploying monitor scripts -> ${CLOUD}:${DIR}"
ssh "${CLOUD}" "mkdir -p ${DIR} /var/lib/portfolio-health"
scp -q "${REPO}/scripts/health_aggregate.py"       "${CLOUD}:${DIR}/health_aggregate.py"
scp -q "${REPO}/scripts/selftest.py"               "${CLOUD}:${DIR}/selftest.py"
scp -q "${REPO}/scripts/run_diagnostic_battery.py" "${CLOUD}:${DIR}/run_diagnostic_battery.py"

echo "==> Installing systemd units"
for u in portfolio-health.service portfolio-health.timer \
         portfolio-health-heartbeat.service portfolio-health-heartbeat.timer \
         portfolio-health-alert.service; do
  scp -q "${HERE}/systemd/${u}" "${CLOUD}:/etc/systemd/system/${u}"
done

echo "==> Seeding /etc/default/portfolio-health (if absent)"
ssh "${CLOUD}" '
  set -e
  if [ ! -f /etc/default/portfolio-health ]; then
    cat > /etc/default/portfolio-health <<EOF
# Portfolio AI health monitor config. EDIT THESE, then:
#   systemctl restart portfolio-health.timer
# ntfy topic to page (create a private, unguessable topic name):
NTFY_URL=https://ntfy.sh/CHANGE-ME-portfolio-ai-XXXX
# Optional healthchecks.io dead-man'"'"'s switch (alerts you if the VPS/monitor dies):
HEALTHCHECKS_URL=
EOF
    chmod 600 /etc/default/portfolio-health
    echo "  created /etc/default/portfolio-health — EDIT NTFY_URL before relying on alerts"
  else
    echo "  keeping existing /etc/default/portfolio-health"
  fi
  systemctl daemon-reload
  systemctl enable --now portfolio-health.timer portfolio-health-heartbeat.timer
'

echo "==> One probe run now (should print per-service status)"
ssh "${CLOUD}" 'systemctl start portfolio-health.service; sleep 1; journalctl -u portfolio-health.service -n 12 --no-pager'
echo "==> Done. Timers: portfolio-health (5min), portfolio-health-heartbeat (daily 12:00 UTC)."
echo "    Remember to set NTFY_URL in /etc/default/portfolio-health if you haven't."
