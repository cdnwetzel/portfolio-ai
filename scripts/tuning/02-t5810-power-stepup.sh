#!/bin/bash
# T5810 A4500 power step-up — 130W -> 155W -> 200W -> unlocked clocks.
#
# WHY: /usr/local/bin/mine-tune.sh (run at boot by /etc/local.d/nvidia-mining.start)
# applies a MINING efficiency profile to an INFERENCE box:
#     nvidia-smi -pl 130    # card default is 200W
#     nvidia-smi -lgc 1200  # max SM clock is 2100 MHz
# Measured under 100% decode load: SM 705-810 MHz, power pinned ~126W against the
# 130W cap, temp only 48-52C. The card is power-starved, not thermally limited.
#
# NOTE: power/clock caps CANNOT cause or prevent VRAM exhaustion. The anti-wedge
# levers are --gpu-memory-utilization 0.93, --max-model-len 32768, --max-num-seqs 4,
# and cudagraph_capture_sizes [1,2,4,8]. All are already in force and UNCHANGED here.
#
# Steps 1-2 keep the 1200 MHz lock so POWER is the only variable. Step 3 then
# unlocks clocks. One variable at a time.
#
# NOTHING HERE IS PERSISTENT. A reboot re-runs mine-tune.sh and restores 130W/1200MHz.
# To roll back immediately:  sudo "$0" --rollback
#
# Usage:  sudo ./t5810-power-stepup.sh          # run all steps, prompting between
#         sudo ./t5810-power-stepup.sh --rollback
set -uo pipefail

PORT=8007
RUNS=3
BENCH=/opt/vllm-service/bench-vllm.sh
LOGDIR=/home/chris/tuning-logs; mkdir -p "$LOGDIR"
LOG="$LOGDIR/02-t5810-power-$(date +%Y%m%d-%H%M%S).log"
ln -sfn "$LOG" "$LOGDIR/02-latest.log"

MAX_TEMP=80          # abort above this
MIN_FREE_MIB=500     # abort if VRAM headroom collapses

say() { echo -e "$*" | tee -a "$LOG"; }

rollback() {
    say "\n>>> ROLLBACK: restoring mine-tune.sh state (130W, SM locked 1200 MHz)"
    nvidia-smi -pl 130   >/dev/null 2>&1
    nvidia-smi -lgc 1200 >/dev/null 2>&1
    nvidia-smi --query-gpu=index,power.limit,clocks.max.sm --format=csv | tee -a "$LOG"
    say ">>> rolled back."
}

[ "${1:-}" = "--rollback" ] && { rollback; exit 0; }
[ "$(id -u)" -eq 0 ] || { echo "must run as root (sudo)"; exit 1; }
[ -x "$BENCH" ] || { echo "missing $BENCH"; exit 1; }

trap 'say "\n!! interrupted"; rollback; exit 130' INT TERM

# Sample GPU telemetry for N seconds in the background, report peaks.
sample() {
    local secs="$1" out; out=$(mktemp)
    ( for _ in $(seq 1 $((secs * 2))); do
        nvidia-smi --query-gpu=index,clocks.sm,power.draw,temperature.gpu,memory.free \
                   --format=csv,noheader,nounits >> "$out"; sleep 0.5
      done ) &
    SAMPLER=$!; SAMPLE_FILE="$out"
}
report_peaks() {
    wait "$SAMPLER" 2>/dev/null
    awk -F', ' '{sm[$1]=($2>sm[$1]?$2:sm[$1]); pw[$1]=($3>pw[$1]?$3:pw[$1]);
                 tp[$1]=($4>tp[$1]?$4:tp[$1]);
                 if(mf[$1]==""||$5<mf[$1]) mf[$1]=$5}
        END{for(g in sm) printf "    GPU%s peak_sm=%s MHz peak_pw=%.0f W peak_temp=%s C min_free=%s MiB\n",
                                g, sm[g], pw[g], tp[g], mf[g]}' "$SAMPLE_FILE" | tee -a "$LOG"
    MAXTEMP=$(awk -F', ' 'BEGIN{m=0}{if($4>m)m=$4}END{print m}' "$SAMPLE_FILE")
    MINFREE=$(awk -F', ' 'BEGIN{m=99999}{if($5<m)m=$5}END{print m}' "$SAMPLE_FILE")
    rm -f "$SAMPLE_FILE"
}

check_abort() {
    if [ "${MAXTEMP:-0}" -ge "$MAX_TEMP" ]; then
        say "!! ABORT: temp ${MAXTEMP}C >= ${MAX_TEMP}C"; rollback; exit 2
    fi
    if [ "${MINFREE:-9999}" -lt "$MIN_FREE_MIB" ]; then
        say "!! ABORT: VRAM free ${MINFREE} MiB < ${MIN_FREE_MIB} MiB"; rollback; exit 2
    fi
    if dmesg 2>/dev/null | tail -50 | grep -qiE "xid|gpu has fallen"; then
        say "!! ABORT: GPU fault in dmesg"; rollback; exit 2
    fi
}

step() {
    local label="$1" pl="$2" clk="$3"
    say "\n=================================================================="
    say ">>> $label   (power=${pl}W, clocks=${clk})"
    say "=================================================================="
    nvidia-smi -pl "$pl" >/dev/null 2>&1 || { say "!! failed to set -pl $pl"; rollback; exit 3; }
    if [ "$clk" = "unlocked" ]; then nvidia-smi -rgc >/dev/null 2>&1
    else nvidia-smi -lgc "$clk" >/dev/null 2>&1; fi
    sleep 2
    sample 30
    "$BENCH" "$PORT" "$RUNS" 2>&1 | grep -E "run |ok:|WARN" | tee -a "$LOG"
    report_peaks
    check_abort
    say "    [ok] no abort condition tripped"
}

say "T5810 A4500 power step-up — $(date)"
say "log: $LOG"
say "\n--- pre-change state ---"
nvidia-smi --query-gpu=index,power.limit,power.draw,clocks.sm,clocks.max.sm,temperature.gpu,memory.free \
           --format=csv | tee -a "$LOG"

step "STEP 0 / baseline (unchanged)"      130 1200
read -rp $'\nStep 0 done. Continue to STEP 1 (155W)? [y/N] ' a; [ "$a" = y ] || { rollback; exit 0; }
step "STEP 1 / +25W, clock lock held"     155 1200
read -rp $'\nStep 1 done. Continue to STEP 2 (200W)? [y/N] ' a; [ "$a" = y ] || { rollback; exit 0; }
step "STEP 2 / stock 200W, clock lock held" 200 1200
read -rp $'\nStep 2 done. Continue to STEP 3 (200W + clocks unlocked)? [y/N] ' a; [ "$a" = y ] || { rollback; exit 0; }
step "STEP 3 / stock 200W, clocks unlocked" 200 unlocked

say "\n=================================================================="
say "ALL STEPS COMPLETE. Results in $LOG"
say "Current state is NOT persistent — reboot restores 130W/1200MHz via mine-tune.sh."
say "To revert now:  sudo $0 --rollback"
say "=================================================================="
