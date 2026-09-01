#!/bin/bash
# 08-mini-models-to-internal.sh — move the ollama model store off the USB drive.
#
# WHY (measured 2026-08-31):
#   external /Volumes/MiniExt1TB  = 768 MB/s   (USB 3.2 Gen 2 — NOT USB4; the
#                                               Thunderbolt 40 Gb/s ports are empty)
#   internal NVMe                 = ~3000 MB/s
# Model load is ~4x slower from the USB drive, and on sparse use the model is
# evicted between sessions so that cost is paid repeatedly:
#   4.7 GB model -> 6.3 s external vs 1.6 s internal
#   9.0 GB model -> 12.0 s external vs 3.1 s internal
# The 22 GB Photos library stays on the external drive ON PURPOSE — it is cold
# archival data that does not care about throughput. Splitting them also ends the
# bus contention: photoanalysisd scanning 22 GB of images currently saturates the
# same 768 MB/s link the models load over.
#
# SAFE BY DESIGN: copies (does not move). The external copy is left intact until
# you delete it yourself. Rollback is a plist restore + restart.
#
# Run as your normal user on the Mini. NO sudo — sudo breaks launchctl's user domain.
#   ./08-mini-models-to-internal.sh
#   ./08-mini-models-to-internal.sh --rollback
set -uo pipefail
export PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin

SRC=/Volumes/MiniExt1TB/AI/ollama/models
DST="$HOME/.ollama/models"
PLIST="$HOME/Library/LaunchAgents/com.ollama.serve.plist"
BAK="${PLIST}.pre-internal-move"
PB=/usr/libexec/PlistBuddy
LOGDIR="$HOME/tuning-logs"; mkdir -p "$LOGDIR"
LOG="$LOGDIR/08-mini-move-$(date +%Y%m%d-%H%M%S).log"
ln -sfn "$LOG" "$LOGDIR/08-latest.log"
exec > >(tee -a "$LOG") 2>&1

if [ "${SUDO_USER:-}" ] || [ "$(id -u)" -eq 0 ]; then
    echo "!! Do NOT run with sudo — launchctl would target gui/0, not your session."; exit 1
fi

live_env() { local p; p=$(pgrep -f "ollama serve" | head -1); echo "  pid=${p:-none}"
    [ -n "$p" ] && ps eww -p "$p" 2>/dev/null | tr ' ' '\n' | grep -E '^OLLAMA_' | sed 's/^/    /'; }

restart_ollama() {
    local before after
    before=$(pgrep -f "ollama serve" | head -1)
    launchctl bootout "gui/$(id -u)/com.ollama.serve" 2>/dev/null || launchctl unload "$PLIST" 2>/dev/null
    sleep 3
    launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || launchctl load "$PLIST" 2>/dev/null
    sleep 12
    after=$(pgrep -f "ollama serve" | head -1)
    if [ "$before" = "$after" ]; then
        echo "  !! PID unchanged ($after) — ollama did NOT restart. Aborting."; return 1
    fi
    echo "  restarted: pid $before -> $after"
}

loadtest() {  # forced-cold load timing: unload, then time a 1-token generate
    local m="$1"
    curl -s -m 60 http://127.0.0.1:11434/api/generate \
        -d "{\"model\":\"$m\",\"prompt\":\"x\",\"keep_alive\":0,\"options\":{\"num_predict\":1}}" -o /dev/null
    sleep 4
    curl -s -m 300 http://127.0.0.1:11434/api/generate \
        -d "{\"model\":\"$m\",\"prompt\":\"Say hello.\",\"stream\":false,\"options\":{\"num_predict\":8}}" \
    | python3 -c '
import json,sys
d=json.load(sys.stdin)
print("    load_duration %.2f s | eval %.2f s" % (d.get("load_duration",0)/1e9, d.get("eval_duration",0)/1e9))'
}

rollback() {
    echo ">>> ROLLBACK: repointing ollama back at the external drive"
    [ -f "$BAK" ] && cp "$BAK" "$PLIST" && echo "  plist restored from $BAK"
    # Restore the original layout: ~/.ollama/models was a symlink to the external store.
    if [ ! -d "$SRC" ]; then
        echo "  !! the external copy at $SRC no longer exists (it was reclaimed)."
        echo "     Rollback would create a DANGLING symlink and break ollama. Refusing."
        echo "     To go back to external storage, re-download the models there instead."
        return 1
    fi
    if [ -d "$DST" ] && [ ! -L "$DST" ]; then
        mv "$DST" "${DST}.internal-copy-$(date +%Y%m%d-%H%M%S)"
        ln -s "$SRC" "$DST"
        echo "  symlink restored: $DST -> $SRC"
        echo "  (internal copy preserved alongside; delete it manually if unwanted)"
    fi
    restart_ollama
    live_env
    echo ">>> done. Internal copy at $DST left in place; delete it manually if unwanted."
}
[ "${1:-}" = "--rollback" ] && { rollback; exit 0; }

echo "=================================================================="; echo " 08 MINI: models USB -> internal NVMe — $(date)"; echo "=================================================================="

echo; echo "--- pre-flight ---"
[ -d "$SRC" ] || { echo "!! source missing: $SRC"; exit 1; }
NEED=$(du -sk "$SRC" | awk '{print $1}')
FREE=$(df -k / | tail -1 | awk '{print $4}')
awk -v n="$NEED" -v f="$FREE" 'BEGIN{printf "  need %.1f GB, free %.1f GB\n", n/1048576, f/1048576}'
[ "$FREE" -gt $((NEED + 10485760)) ] || { echo "!! not enough internal space (want 10 GB slack)"; exit 1; }
echo "  source blobs: $(ls "$SRC/blobs" | wc -l | tr -d ' ')"
live_env

echo; echo "--- BASELINE: cold load from the USB drive ---"
loadtest qwen2.5:7b-instruct

echo; echo "--- resolving the destination BEFORE copying ---"
# ~/.ollama/models ships as a SYMLINK to the external drive. If we rsync into it we
# copy the directory into itself, and a src-vs-dst blob-count check PASSES because
# they are the same directory. Replace the symlink with a real directory first.
if [ -L "$DST" ]; then
    echo "  $DST is a symlink -> $(readlink "$DST")"
    rm "$DST"
    echo "  symlink removed (the external data it pointed at is untouched)"
fi
mkdir -p "$DST"
SRC_R=$(cd "$SRC" && pwd -P); DST_R=$(cd "$DST" && pwd -P)
echo "  src resolves to: $SRC_R"
echo "  dst resolves to: $DST_R"
if [ "$SRC_R" = "$DST_R" ]; then
    echo "!! src and dst are the SAME directory — refusing to copy into itself."; exit 2
fi

echo; echo "--- copying (external copy is NOT deleted) ---"
rsync -a "$SRC/" "$DST/" || { echo "!! rsync failed"; exit 2; }
echo "  copied."

echo; echo "--- verify ---"
SB=$(ls "$SRC/blobs" | wc -l | tr -d ' '); DB=$(ls "$DST/blobs" | wc -l | tr -d ' ')
SS=$(du -sk "$SRC" | awk '{print $1}');   DS=$(du -sk "$DST" | awk '{print $1}')
echo "  blobs  src=$SB  dst=$DB"
awk -v a="$SS" -v b="$DS" 'BEGIN{printf "  size   src=%.1f GB  dst=%.1f GB\n", a/1048576, b/1048576}'
[ "$SB" = "$DB" ] || { echo "!! blob count mismatch — NOT repointing ollama"; exit 3; }
[ -L "$DST" ] && { echo "!! dst is still a symlink — aborting"; exit 3; }
[ "$SS" -gt 0 ] && [ "$DS" -gt 0 ] || { echo "!! zero-size copy — aborting"; exit 3; }
echo "  ok: blob counts match, dst is a real directory on internal storage"

echo; echo "--- repoint OLLAMA_MODELS -> $DST ---"
[ -f "$BAK" ] || cp "$PLIST" "$BAK"
echo "  backup: $BAK"
$PB -c "Delete :EnvironmentVariables:OLLAMA_MODELS" "$PLIST" 2>/dev/null
$PB -c "Add :EnvironmentVariables:OLLAMA_MODELS string $DST" "$PLIST"
plutil -lint "$PLIST" >/dev/null || { echo "!! plist invalid, restoring"; cp "$BAK" "$PLIST"; exit 4; }
restart_ollama || { echo "!! restart failed — rolling back"; cp "$BAK" "$PLIST"; restart_ollama; exit 5; }

echo; echo "--- confirm the LIVE process uses the new path ---"
live_env
pgrep -f "ollama serve" >/dev/null && \
  ps eww -p "$(pgrep -f 'ollama serve' | head -1)" | tr ' ' '\n' | grep -q "OLLAMA_MODELS=$DST" \
  && echo "  ok: live process points at internal" \
  || { echo "  !! live process does NOT point at internal — rolling back"; rollback; exit 6; }

echo; echo "--- models visible after the move ---"
ollama list 2>&1 | sed 's/^/  /'

echo; echo "--- AFTER: cold load from internal NVMe ---"
loadtest qwen2.5:7b-instruct

echo
echo "=================================================================="
echo " Compare the two load_duration figures above."
echo " The external copy is UNTOUCHED at:"
echo "   $SRC"
echo " Reclaim ~39 GB once you are satisfied:  rm -rf \"$SRC\""
echo " Roll back anytime:  $0 --rollback"
echo " log: $LOG"
echo "=================================================================="
