#!/bin/bash
# 02b-t5810-find-knee.sh — clocks UNLOCKED, sweep the power cap to find the
# efficiency knee. Step 3 proved 200W/unlocked = 34.6 tok/s, but step 1 showed
# 155W (clock-locked) already gave 32.5. Most of the win was cheap; this finds
# where the curve flattens so we don't pay +140W continuous for the last ~2 tok/s.
#
# Read-only w.r.t. config: sets only the power limit, clocks stay unlocked.
# Rollback: sudo ./02-t5810-power-stepup.sh --rollback   (restores 130W/1200MHz)
set -uo pipefail
LOGDIR=/home/chris/tuning-logs; mkdir -p "$LOGDIR"
LOG="$LOGDIR/02b-knee-$(date +%Y%m%d-%H%M%S).log"
ln -sfn "$LOG" "$LOGDIR/02b-latest.log"
exec > >(tee -a "$LOG") 2>&1
[ "$(id -u)" -eq 0 ] || { echo "must run as root (sudo)"; exit 1; }

BENCH=/opt/vllm-service/bench-vllm.sh
nvidia-smi -rgc >/dev/null 2>&1   # clocks unlocked for the whole sweep

echo "=================================================================="
echo " 02b KNEE SWEEP (clocks unlocked) — $(date)"
echo " reference: 130W/locked=29.43   200W/unlocked=34.57 tok/s"
echo "=================================================================="

for PL in 150 165 180 200; do
    echo; echo ">>> power limit ${PL}W (clocks unlocked)"
    nvidia-smi -pl "$PL" >/dev/null 2>&1 || { echo "!! failed -pl $PL"; continue; }
    sleep 2
    S=$(mktemp)
    ( for _ in $(seq 1 44); do
        nvidia-smi --query-gpu=index,clocks.sm,power.draw,temperature.gpu \
                   --format=csv,noheader,nounits >> "$S"; sleep 0.5; done ) &
    SP=$!
    "$BENCH" 8007 3 2>&1 | grep -E "^  run " | tee /dev/stderr \
        | awk '{for(i=1;i<=NF;i++) if($i ~ /^tok\/s=/){split($i,a,"=");s+=a[2];n++}}
               END{printf "    MEAN %.2f tok/s\n", s/n}'
    wait $SP 2>/dev/null
    awk -F', ' '{sm[$1]=($2>sm[$1]?$2:sm[$1]); pw[$1]=($3>pw[$1]?$3:pw[$1]); tp[$1]=($4>tp[$1]?$4:tp[$1])}
        END{for(g in sm) printf "    GPU%s peak_sm=%s MHz peak_pw=%.0f W peak_temp=%s C\n",g,sm[g],pw[g],tp[g]}' "$S"
    rm -f "$S"
    T=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader | sort -rn | head -1)
    [ "$T" -ge 80 ] && { echo "!! ABORT temp ${T}C"; nvidia-smi -pl 130; nvidia-smi -lgc 1200; exit 2; }
done

echo
echo "=================================================================="
echo "Pick the lowest wattage within ~1 tok/s of the 200W number."
echo "Still NOT persistent — reboot restores 130W/1200MHz via mine-tune.sh."
echo "Revert now: sudo /home/chris/tuning/02-t5810-power-stepup.sh --rollback"
echo "=================================================================="
