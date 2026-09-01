#!/bin/bash
# 02c-t5810-soak.sh — sustained-load thermal soak at a chosen power limit.
# WHY: the knee sweep peaked at 79C at 200W on a 23-SECOND bench, and clocks had
# already begun backing off (1845 MHz at 200W vs 1860 at 150W). A burst benchmark
# does not prove a 24/7 operating point. This runs continuous back-to-back
# generation and reports whether temps and clocks hold, or drift.
#
# Usage:  sudo ./02c-t5810-soak.sh [watts] [minutes]
#         sudo ./02c-t5810-soak.sh 165 10
set -uo pipefail
PL="${1:-165}"; MINS="${2:-10}"
LOGDIR=/home/chris/tuning-logs; mkdir -p "$LOGDIR"
LOG="$LOGDIR/02c-soak-${PL}W-$(date +%Y%m%d-%H%M%S).log"
ln -sfn "$LOG" "$LOGDIR/02c-latest.log"
exec > >(tee -a "$LOG") 2>&1
[ "$(id -u)" -eq 0 ] || { echo "must run as root (sudo)"; exit 1; }

MODEL=$(curl -sf -m 10 http://127.0.0.1:8007/v1/models | python3 -c 'import json,sys;print(json.load(sys.stdin)["data"][0]["id"])')
nvidia-smi -rgc >/dev/null 2>&1; nvidia-smi -pl "$PL" >/dev/null 2>&1
echo "=================================================================="
echo " SOAK ${PL}W, ${MINS} min, clocks unlocked — $(date)"
echo " model=$MODEL   abort at 82C"
echo "=================================================================="
printf "%-9s %-7s %-9s %-9s %-7s %-7s\n" elapsed tok/s sm0/sm1 pw0/pw1 t0 t1

END=$(( $(date +%s) + MINS*60 )); N=0; SUM=0; MAXT=0
while [ "$(date +%s)" -lt "$END" ]; do
    T0=$(date +%s.%N)
    TOK=$(curl -s -m 120 http://127.0.0.1:8007/v1/completions \
        -H 'Content-Type: application/json' \
        -d "{\"model\":\"$MODEL\",\"prompt\":\"Explain how tensor parallelism works.\",\"max_tokens\":256,\"temperature\":0,\"ignore_eos\":true}" \
        | python3 -c 'import json,sys;print(json.load(sys.stdin)["usage"]["completion_tokens"])' 2>/dev/null)
    T1=$(date +%s.%N)
    [ -z "$TOK" ] && { echo "  (request failed, retrying)"; sleep 2; continue; }
    RATE=$(echo "$TOK $T0 $T1" | awk '{printf "%.1f", $1/($3-$2)}')
    read -r SM0 SM1 PW0 PW1 TP0 TP1 <<<"$(nvidia-smi --query-gpu=clocks.sm,power.draw,temperature.gpu \
        --format=csv,noheader,nounits | awk -F', ' 'NR==1{s0=$1;p0=$2;t0=$3}NR==2{print s0,$1,p0,$2,t0,$3}')"
    N=$((N+1)); SUM=$(echo "$SUM $RATE" | awk '{print $1+$2}')
    [ "${TP0%.*}" -gt "$MAXT" ] && MAXT=${TP0%.*}
    [ "${TP1%.*}" -gt "$MAXT" ] && MAXT=${TP1%.*}
    printf "%-9s %-7s %-9s %-9s %-7s %-7s\n" \
        "$(( $(date +%s) - (END - MINS*60) ))s" "$RATE" "$SM0/$SM1" "${PW0%.*}/${PW1%.*}" "$TP0" "$TP1"
    if [ "$MAXT" -ge 82 ]; then
        echo "!! ABORT: ${MAXT}C >= 82C — rolling back to 130W/1200MHz"
        nvidia-smi -pl 130 >/dev/null; nvidia-smi -lgc 1200 >/dev/null; exit 2
    fi
done

echo
echo "$SUM $N $MAXT" | awk '{printf "RESULT: mean %.2f tok/s over %d requests, peak temp %dC\n",$1/$2,$2,$3}'
echo "PASS if: mean held near the burst figure, clocks did NOT drift down, peak < 78C."
echo "Still NOT persistent. Revert: sudo /home/chris/tuning/02-t5810-power-stepup.sh --rollback"
