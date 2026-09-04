#!/bin/sh
# Continuously verify the A4500 power cap is actually applied.
#
# Exists because on 2026-09-03 the cap was found sitting at the 200 W driver default after a
# boot, while every document said it was "set at boot". Nothing noticed, because nothing
# checked. The gpu-tune service now fails loudly if it cannot apply the cap, but a service
# that fails at 03:00 is only useful if something reads it.
#
# At the 200 W default these cards run 79 C -- 1 C from thermal abort per the tuning notes --
# and draw ~70 W more than the figure the UPS budget was measured against. Worth a line a
# minute to know.
LOG=/var/log/gpu-cap-check.log
LIMITS=$(nvidia-smi --query-gpu=power.limit --format=csv,noheader,nounits 2>/dev/null | tr -d " " | paste -sd, -)
case "$LIMITS" in
    165*165*) exit 0 ;;                       # expected: quiet
    "")  echo "$(date -Iseconds) WARN nvidia-smi unavailable" >> "$LOG" ;;
    *)   echo "$(date -Iseconds) DRIFT power.limit=${LIMITS} expected 165,165 — reapplying" >> "$LOG"
         /usr/local/bin/gpu-tune.sh >> "$LOG" 2>&1
         echo "$(date -Iseconds) after reapply: $(nvidia-smi --query-gpu=power.limit --format=csv,noheader,nounits | tr -d " " | paste -sd, -)" >> "$LOG" ;;
esac
