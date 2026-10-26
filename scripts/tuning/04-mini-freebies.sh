#!/bin/bash
# 04-mini-freebies.sh — M4 Mac Mini 16 GB (macOS 26.4.1, ollama 0.33.0).
#
# REALITY CHECK FIRST: this box measured 20.1-21.7 tok/s on qwen2.5:7b-instruct.
# M4 base memory bandwidth is ~120 GB/s and a 4.7 GB q4 model reads ~4.7 GB/token,
# so the hard roofline is ~25.5 tok/s. It is already at ~85% of its ceiling.
# Do NOT expect a large throughput win here — there are about 4 tok/s on the table
# in total. The real prize is MEMORY: the box is actively swapping (857 MB used).
#
#   A) OLLAMA_FLASH_ATTENTION=1   (unset today)
#   B) OLLAMA_KV_CACHE_TYPE=q8_0  (unset today; needs A to take effect) - halves KV
#   C) OLLAMA_NUM_PARALLEL=1      (unset today; a default >1 multiplies KV alloc,
#                                  which on a 16 GB box is the swap/no-swap line)
#      (OLLAMA_MAX_LOADED_MODELS=1 is ALREADY set correctly - left alone.)
#   D) OPTIONAL, separate prompt: raise iogpu.wired_limit_mb (Metal wired cap).
#      Currently 0 = default ~75% of RAM ~= 12 GB. Step to 13 GB. NOT persistent.
#
# Also flagged, NOT changed by this script: qwen3-coder:30b is 18 GB on a 16 GB
# machine. It cannot fit and is the likely source of the swap. Consider removing it.
#
# Rollback: ./04-mini-freebies.sh --rollback
set -uo pipefail

LOGDIR="$HOME/tuning-logs"; mkdir -p "$LOGDIR"
LOG="$LOGDIR/04-mini-$(date +%Y%m%d-%H%M%S).log"
ln -sfn "$LOG" "$LOGDIR/04-latest.log"
exec > >(tee -a "$LOG") 2>&1

# MUST NOT run under sudo: launchctl targets gui/$UID, and under sudo that is gui/0,
# not your user's domain - the restart silently no-ops and you measure the OLD process.
if [ "${SUDO_USER:-}" ] || [ "$(id -u)" -eq 0 ]; then
    echo "!! Do NOT run this with sudo. Run as your normal user:  ./04-mini-freebies.sh"
    echo "   (step D will prompt for sudo on its own)"
    exit 1
fi
PLIST="$HOME/Library/LaunchAgents/com.ollama.serve.plist"
BAK="${PLIST}.pre-tuning"
PB=/usr/libexec/PlistBuddy
export PATH=/opt/homebrew/bin:$PATH

bench() {
  echo "  ollama qwen2.5:7b-instruct, 256 tok, temp=0:"
  for _ in 1 2; do
    curl -s --max-time 150 http://127.0.0.1:11434/api/generate \
      -d '{"model":"qwen2.5:7b-instruct","prompt":"Write 200 words about computer networking.","stream":false,"options":{"temperature":0,"num_predict":256}}' \
    | python3 -c '
import sys,json
d=json.load(sys.stdin)
ec=d.get("eval_count",0); ed=d.get("eval_duration",1)/1e9
pc=d.get("prompt_eval_count",0); pd=d.get("prompt_eval_duration",1)/1e9
print(f"    gen {ec} tok in {ed:.2f}s = {ec/ed:.1f} tok/s | prefill {pc} tok in {pd:.2f}s")'
  done
}
state() {
  echo -n "  iogpu.wired_limit_mb: "; sysctl -n iogpu.wired_limit_mb 2>/dev/null
  sysctl vm.swapusage | sed 's/^/  /'
  # Read the LIVE process environment. Printing the plist only proves we wrote a file;
  # it says nothing about whether ollama actually picked the values up.
  local pid; pid=$(pgrep -f "ollama serve" | head -1)
  echo "  running ollama pid=${pid:-none}, env in effect:"
  if [ -n "$pid" ]; then
      ps eww -p "$pid" 2>/dev/null | tr ' ' '\n' | grep -E '^OLLAMA_' | sed 's/^/    /' \
        || echo "    (could not read process env)"
  fi
}
restart_ollama() {
  # macOS 26 prefers bootout/bootstrap; unload/load still works but is deprecated.
  # Try the modern form first, fall back so this works on older releases too.
  local before; before=$(pgrep -f "ollama serve" | head -1)
  launchctl bootout "gui/$(id -u)/com.ollama.serve" 2>/dev/null || launchctl unload "$PLIST" 2>/dev/null
  sleep 3
  launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || launchctl load "$PLIST" 2>/dev/null
  echo "  waiting 15s for ollama..."; sleep 15
  local after; after=$(pgrep -f "ollama serve" | head -1)
  if [ "$before" = "$after" ]; then
      echo "  !! PID unchanged ($after) - ollama did NOT restart. New env is NOT in effect."
      echo "     Everything measured after this point is the OLD process. Aborting."
      exit 4
  fi
  echo "  restarted: pid $before -> $after"
  curl -sf -m 10 http://127.0.0.1:11434/api/tags >/dev/null 2>&1 \
    && echo "  ollama is back" || echo "  !! ollama did NOT come back - check ~/.ollama/logs/ollama.log"
}

rollback() {
  echo; echo ">>> ROLLBACK"
  if [ -f "$BAK" ]; then cp "$BAK" "$PLIST"; echo "  restored plist from $BAK"; restart_ollama; fi
  sudo sysctl -w iogpu.wired_limit_mb=0 2>/dev/null && echo "  iogpu.wired_limit_mb reset to 0 (default)"
  state; echo ">>> rolled back."
}
[ "${1:-}" = "--rollback" ] && { rollback; exit 0; }

echo "=================================================================="; echo " 04 MAC MINI FREEBIES — $(date)"; echo "=================================================================="
# A busy Mac invalidates every number. On 2026-08-31 photolibraryd at 181% CPU dragged
# this box from 21.6 to 14 tok/s, which looked like a regression and was not.
LOAD=$(uptime | sed 's/.*load averages*: *//' | awk '{print int($1)}')
if [ "${LOAD:-0}" -ge 2 ]; then
    echo "!! load average is ${LOAD} - this machine is BUSY. Top consumers:"
    ps -Ao pcpu,comm -r | head -5 | sed 's/^/     /'
    echo "   Measurements taken now are not comparable. Wait for it to settle."
    read -rp "   Continue anyway? [y/N] " c; [ "$c" = y ] || exit 1
fi

echo; echo "--- BEFORE ---"; state; bench

echo; echo ">>> A/B/C) ollama flash-attn + q8_0 KV + num_parallel=1"
[ -f "$BAK" ] || cp "$PLIST" "$BAK"
echo "  backup: $BAK"
for kv in OLLAMA_FLASH_ATTENTION:1 OLLAMA_KV_CACHE_TYPE:q8_0 OLLAMA_NUM_PARALLEL:1; do
  k="${kv%%:*}"; v="${kv##*:}"
  $PB -c "Delete :EnvironmentVariables:$k" "$PLIST" 2>/dev/null
  $PB -c "Add :EnvironmentVariables:$k string $v" "$PLIST"
done
plutil -lint "$PLIST" || { echo "!! plist invalid, restoring"; cp "$BAK" "$PLIST"; exit 3; }
restart_ollama

echo; echo "--- AFTER (env only) ---"; state; bench

echo
read -rp "Also raise Metal wired limit 12GB -> 13GB (step D)? [y/N] " a
if [ "$a" = y ]; then
  sudo sysctl -w iogpu.wired_limit_mb=13312
  echo "  set. NOT persistent - a reboot restores the default."
  sleep 2; state; bench
fi

echo
echo "GO/NO-GO: keep if tok/s held or improved AND swap used did not grow."
echo "  rollback: $0 --rollback"
echo "  NOTE: plist change PERSISTS across reboot; iogpu.wired_limit_mb does NOT."
echo "log: $LOG"
