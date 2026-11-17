#!/usr/bin/env bash
# Install the durable Qdrant OpenRC unit on the T5810 (Gentoo / OpenRC) and clear the
# stale root-owned /snapshots leftover that caused the 2026-06-14 outage.
#
# Qdrant's binary (/usr/local/bin/qdrant) and its config.yaml (with ABSOLUTE storage/
# snapshots/temp paths under /home/chris/qdrant-data) already live on the box — this
# script only manages the OpenRC service unit and the one-time cleanup. It does NOT
# touch the data/collection.
#
# Run from the repo root on a machine with SSH access to the T5810.
# Usage:  ./home/setup-qdrant.sh
# Env:    T5810_HOST (default root@ai.cwetzel.com)
set -euo pipefail

T5810="${T5810_HOST:-root@ai.cwetzel.com}"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "==> Installing /etc/init.d/qdrant"
scp -q "${HERE}/qdrant/qdrant.openrc" "${T5810}:/tmp/qdrant.openrc"
ssh "${T5810}" '
  set -e
  cp /tmp/qdrant.openrc /etc/init.d/qdrant && chmod 755 /etc/init.d/qdrant
  rc-update add qdrant default 2>/dev/null || true

  # One-time cleanup of the stale ROOT-owned /snapshots that latched Qdrant off.
  # With the new unit CWD is /home/chris/qdrant-data, so this can no longer be
  # recreated. Only remove it if it is empty and root-owned (never touch real data).
  if [ -d /snapshots ]; then
    owner=$(stat -c %U /snapshots)
    if [ "$owner" = "root" ] && [ -z "$(find /snapshots -mindepth 1 -print -quit)" ]; then
      echo "  removing stale empty root-owned /snapshots"
      rmdir /snapshots 2>/dev/null || rm -rf /snapshots
    else
      echo "  WARNING: /snapshots exists but is not empty/root-owned (owner=$owner) — leaving it, inspect manually"
    fi
  fi

  echo "  restarting qdrant with the new unit"
  rc-service qdrant stop 2>/dev/null || true
  rc-service qdrant zap 2>/dev/null || true
  rc-service qdrant start
'

echo "==> Verifying"
ssh "${T5810}" '
  sleep 2
  echo -n "  cwd: "; readlink /proc/$(pgrep -x qdrant | head -1)/cwd 2>/dev/null || echo "(qdrant not running)"
  echo -n "  collection: "; curl -sf http://127.0.0.1:6333/collections/documents | head -c 300 || echo UNREACHABLE
  echo
'
echo "==> Done. Qdrant unit installed; expect cwd=/home/chris/qdrant-data and green collection with points_count > 0."
