#!/usr/bin/env bash
# Pull a backup of the verifier's verdicts.db from the asrock to the T5810.
#
# WHY PULL: the asrock (Gentoo) has no cron daemon, so it can't schedule its own
# backups; the T5810 can. Run from chris's crontab on the T5810:
#   17 6 * * * /home/chris/ai/cwdotcom/scripts/backup_verdicts_pull.sh >> /var/log/verdicts-backup.log 2>&1
#
# verdicts.db is the ONLY durable metrics store (defect ledger #4): judge verdicts,
# faithfulness scores, latencies — the continuous-improvement loop's raw material.
# sqlite .backup runs on the asrock (consistent under the verifier's writes), then
# the snapshot is pulled here. Keeps 30 daily copies.
set -euo pipefail

REMOTE="${VERIFIER_HOST:-asrock}"
REMOTE_DB="/home/chris/verifier/verdicts.db"
LOCAL_DIR="/home/chris/verdicts-backups"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
KEEP=30

mkdir -p "${LOCAL_DIR}"
echo "==> $(date -u +%FT%TZ) snapshotting ${REMOTE}:${REMOTE_DB}"
ssh "${REMOTE}" "sqlite3 ${REMOTE_DB} '.backup /tmp/verdicts-snapshot.db'"
scp -q "${REMOTE}:/tmp/verdicts-snapshot.db" "${LOCAL_DIR}/verdicts-${STAMP}.db"
ssh "${REMOTE}" "rm -f /tmp/verdicts-snapshot.db"

# Monthly restore test (first Sunday): the copy must open and have rows.
if [ "$(date -u +%u)" = "7" ] && [ "$(date -u +%d)" -le 7 ]; then
  ROWS=$(sqlite3 "${LOCAL_DIR}/verdicts-${STAMP}.db" "SELECT COUNT(*) FROM verdicts;")
  echo "==> monthly restore test: ${ROWS} verdict rows"
  [ "${ROWS}" -gt 0 ] || { echo "✗ restore test FAILED: 0 rows"; exit 1; }
fi

ls -1t "${LOCAL_DIR}"/verdicts-*.db | tail -n +$((KEEP + 1)) | xargs -r rm -f
echo "==> done: ${LOCAL_DIR}/verdicts-${STAMP}.db"
