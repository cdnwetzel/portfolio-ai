#!/bin/bash
# 06-ttft-bench.sh — TTFT is the metric that matters for a bursty, mostly-single-turn
# workload. Decode tok/s is what we optimised so far; it is the LEAST representative
# number for short requests.
#
# Three things this answers:
#   1. How does TTFT scale with prompt size? (a real RAG turn is ~2-4k tokens)
#   2. What does a COLD card cost? Bursty traffic means most requests hit an idle GPU
#      that has dropped to a low P-state and must ramp.
#   3. Did the power/clock change help PREFILL more than it helped decode? Prefill is
#      COMPUTE-bound; decode is memory-BANDWIDTH-bound. The +13.6% we measured on
#      decode is a floor, not a ceiling, for what TTFT may have gained.
#
# Usage:  ./06-ttft-bench.sh              # phases 1+2, no root needed
#         sudo ./06-ttft-bench.sh --ab    # + phase 3: A/B vs the old 130W/1200 profile
set -uo pipefail
LOGDIR=/home/chris/tuning-logs; mkdir -p "$LOGDIR"
LOG="$LOGDIR/06-ttft-$(date +%Y%m%d-%H%M%S).log"
ln -sfn "$LOG" "$LOGDIR/06-latest.log"
exec > >(tee -a "$LOG") 2>&1
PROBE=/home/chris/tuning/ttft_probe.py


# Block until BOTH GPUs cool below $1 C (or $2 seconds elapse). Bursty production
# traffic hits an idle, cool card; measuring hot understates prefill AND biases any
# A/B toward whichever arm ran first. GPU Boost lowers clocks as temperature rises
# well before any thermal flag trips, so temperature is a confound, not a detail.
cool_to() {
    local target="${1:-50}" maxwait="${2:-900}" t0 hot
    t0=$(date +%s)
    printf "  cooling to <=%sC " "$target"
    while :; do
        hot=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader | sort -rn | head -1)
        [ "$hot" -le "$target" ] && { printf " reached %sC after %ss\n" "$hot" "$(( $(date +%s) - t0 ))"; return 0; }
        [ $(( $(date +%s) - t0 )) -ge "$maxwait" ] && { printf " TIMEOUT at %sC after %ss\n" "$hot" "$maxwait"; return 0; }
        printf "."; sleep 15
    done
}

gpu() { nvidia-smi --query-gpu=index,power.limit,clocks.sm,temperature.gpu --format=csv,noheader | sed 's/^/    /'; }

echo "=================================================================="
echo " 06 TTFT BENCH — $(date)"
echo "=================================================================="

echo; echo "--- PHASE 1: TTFT vs prompt size (current config) ---"
cool_to 50
gpu
python3 "$PROBE" 256 1024 2048 4096

echo; echo "--- PHASE 2: COLD-CARD cost (the real bursty pattern) ---"
echo "  idling until genuinely cool (bursty traffic hits an idle card)..."
cool_to 48
echo "  idle state:"; gpu
echo "  first request after idle (cold), then immediately again (warm):"
python3 - <<'PY'
import sys; sys.path.insert(0,"/home/chris/tuning")
from ttft_probe import make_prompt, ttft, ntokens
p = make_prompt(2048); n = ntokens(p)
cold = ttft(p, 8)[0]*1000
warm = [ttft(p, 8)[0]*1000 for _ in range(3)]
w = sum(warm)/len(warm)
print(f"    prompt ~{n} tok")
print(f"    COLD first request : {cold:7.0f} ms")
print(f"    WARM (mean of 3)   : {w:7.0f} ms")
print(f"    cold-start penalty : {cold-w:7.0f} ms  ({(cold/w-1)*100:.0f}% slower)")
PY
echo "  state right after:"; gpu

if [ "${1:-}" = "--ab" ]; then
    [ "$(id -u)" -eq 0 ] || { echo "!! --ab needs root"; exit 1; }
    echo; echo "--- PHASE 3: A/B vs the OLD mining profile (130W, SM locked 1200) ---"
    nvidia-smi -pl 130 >/dev/null 2>&1; nvidia-smi -lgc 1200 >/dev/null 2>&1; sleep 3
    cool_to 50
    echo "  OLD profile:"; gpu
    python3 "$PROBE" 1024 2048 4096
    echo; echo "  restoring 165W / unlocked..."
    nvidia-smi -pl 165 >/dev/null 2>&1; nvidia-smi -rgc >/dev/null 2>&1; sleep 3
    cool_to 50
    echo "  NEW profile:"; gpu
    python3 "$PROBE" 1024 2048 4096
fi

echo
echo "=================================================================="
echo " Read: ms/1k-prefill is the number to compare across configs."
echo " A large cold-start penalty argues for a CLOCK FLOOR (nvidia-smi -lgc MIN,MAX)"
echo " so a bursty first request does not wait on a P-state ramp."
echo " log: $LOG"
echo "=================================================================="
