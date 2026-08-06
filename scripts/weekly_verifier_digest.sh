#!/usr/bin/env bash
# Weekly continuous-improvement digest (convergence doc, Task 6 alerting).
# Runs on the asrock as chris (no root needed) — but asrock has no cron daemon,
# so schedule it from the T5810: 23 7 * * 1 ssh asrock /path/to/weekly_verifier_digest.sh
#
# Reads verdicts.db (metadata only — red-line #2 safe: scores, counts, never content)
# and reports the three signals that matter for the improvement loop:
#   1. flagged-rate (7-day + all-time) — judge strictness drift
#   2. judge latency (7-day mean/max) — vs the 25s UI window
#   3. silence — zero verdicts in 48h on an otherwise-idle-but-visited site was the
#      2026-08-01→05 invisible-outage signature (VERIFIER_URL/VERIFIER_HOST break)
# Sends to ntfy if NTFY_URL is set (in /etc/portfolio-canary.env or env), else prints.
set -euo pipefail

DB="${DB_PATH:-$HOME/verifier/verdicts.db}"
[ -f /etc/portfolio-canary.env ] && . /etc/portfolio-canary.env
NTFY_URL="${NTFY_URL:-}"

read -r TOTAL F_RATE L_AVG L_MAX LAST_TS <<<"$(sqlite3 -separator ' ' "${DB}" "
  SELECT COUNT(*), ROUND(AVG(flagged),3), ROUND(AVG(latency_s),1), ROUND(MAX(latency_s),1),
         MAX(ts) FROM verdicts
  WHERE ts > datetime('now','-7 days') AND verdict_type='judged';")"

read -r ALL_TOTAL ALL_FRATE <<<"$(sqlite3 -separator ' ' "${DB}" "
  SELECT COUNT(*), ROUND(AVG(flagged),3) FROM verdicts WHERE verdict_type='judged';")"

DAYS_SINCE=$(python3 -c "
from datetime import datetime, timezone
last = datetime.fromisoformat('${LAST_TS:-2000-01-01}').replace(tzinfo=timezone.utc)
print(round((datetime.now(timezone.utc) - last).total_seconds() / 86400, 1))")

MSG="verifier digest (7d): ${TOTAL:-0} verdicts, flagged ${F_RATE:-n/a} (all-time ${ALL_FRATE:-n/a}/${ALL_TOTAL:-0})
judge latency: mean ${L_AVG:-n/a}s, max ${L_MAX:-n/a}s (UI window 25s)
last verdict: ${DAYS_SINCE} days ago"

WARN=""
[ "${DAYS_SINCE%.*}" -ge 2 ] && WARN="${WARN}\n⚠ silence: no verdicts in ${DAYS_SINCE}d — check VERIFIER_URL / tunnel 8007"
[ "${TOTAL:-0}" -ge 20 ] && python3 -c "exit(0 if ${F_RATE:-0} <= 0.35 else 1)" || true
if [ "${TOTAL:-0}" -ge 20 ] && ! python3 -c "exit(0 if ${F_RATE:-0} <= 0.35 else 1)"; then
  WARN="${WARN}\n⚠ flagged-rate ${F_RATE} > 0.35 at n=${TOTAL} — spot-check 10 flagged answers"
fi

echo -e "${MSG}${WARN}"
if [ -n "${NTFY_URL}" ]; then
  curl -s -X POST "${NTFY_URL}" -H "Title: verifier weekly digest" --data-binary "$(echo -e "${MSG}${WARN}")" >/dev/null
fi
