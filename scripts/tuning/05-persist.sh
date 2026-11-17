#!/bin/bash
# 05-persist.sh — make the measured tuning survive reboot. RUN ONLY AFTER THE SOAK PASSES.
#
# WHAT IT PERSISTS (all measured 2026-08-31, see ~/tuning-logs/):
#   1. GPU power limit + unlocked clocks   29.43 -> 33.43 tok/s (+13.6%)
#   2. CPU governor performance            embed :8005  45 -> 24 ms
#   3. KSM off                             shared 0 pages after 164 scans; pure waste
#
# WHAT IT REPLACES:
#   /etc/local.d/nvidia-mining.start -> /usr/local/bin/mine-tune.sh applied a MINING
#   efficiency profile (-pl 130, -lgc 1200) to an inference box. Measured effect:
#   SM dragged to 705-810 MHz under load at 100% util and only 50C. That file is
#   DISABLED here (renamed .disabled, not deleted) and replaced by gpu-tune.sh,
#   which records why each number was chosen.
#
# Usage:  sudo ./05-persist.sh [watts]     # default 165 (the measured knee)
#         sudo ./05-persist.sh --verify    # assert LIVE state matches intent
#         sudo ./05-persist.sh --rollback  # restore the mining profile + KSM
set -uo pipefail
LOGDIR=/home/chris/tuning-logs; mkdir -p "$LOGDIR"
LOG="$LOGDIR/05-persist-$(date +%Y%m%d-%H%M%S).log"
ln -sfn "$LOG" "$LOGDIR/05-latest.log"
exec > >(tee -a "$LOG") 2>&1
[ "$(id -u)" -eq 0 ] || { echo "must run as root (sudo)"; exit 1; }

BAKDIR=/root/tuning-backups-20260831; mkdir -p "$BAKDIR"

verify() {
    echo "--- LIVE STATE (asserted, not assumed) ---"
    local fail=0
    nvidia-smi --query-gpu=index,power.limit,clocks.max.sm,persistence_mode --format=csv
    local lim; lim=$(nvidia-smi --query-gpu=power.limit --format=csv,noheader,nounits | head -1 | cut -d. -f1)
    [ "$lim" -ge 150 ] || { echo "  FAIL: power limit ${lim}W still low"; fail=1; }
    local gov; gov=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)
    echo "  governor: $gov"; [ "$gov" = performance ] || { echo "  FAIL: governor not performance"; fail=1; }
    grep MHz /proc/cpuinfo | awk '{s+=$4;n++} END{printf "  cpu avg %.0f MHz\n",s/n}'
    local ksm; ksm=$(cat /sys/kernel/mm/ksm/run)
    echo "  KSM run: $ksm"; [ "$ksm" = 0 ] || { echo "  FAIL: KSM still on"; fail=1; }
    echo "  boot hooks:"; ls -1 /etc/local.d/*.start 2>/dev/null | sed 's/^/    /'
    [ "$fail" = 0 ] && echo "  ==> ALL CHECKS PASS" || echo "  ==> CHECKS FAILED"
    return "$fail"
}

rollback() {
    echo ">>> ROLLBACK to pre-tuning state"
    rm -f /etc/local.d/gpu-tune.start /etc/local.d/cpu-governor.start /usr/local/bin/gpu-tune.sh
    [ -f /etc/local.d/nvidia-mining.start.disabled ] && mv /etc/local.d/nvidia-mining.start.disabled /etc/local.d/nvidia-mining.start
    [ -f /etc/local.d/ksm.start.disabled ]           && mv /etc/local.d/ksm.start.disabled           /etc/local.d/ksm.start
    /usr/local/bin/mine-tune.sh 2>/dev/null
    echo 1 > /sys/kernel/mm/ksm/run 2>/dev/null
    for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo userspace > "$g" 2>/dev/null; done
    for s in /sys/devices/system/cpu/cpu*/cpufreq/scaling_setspeed; do echo 1200000 > "$s" 2>/dev/null; done
    echo ">>> restored. backups remain in $BAKDIR"; verify || true
}

case "${1:-}" in
    --verify)   verify; exit $? ;;
    --rollback) rollback; exit 0 ;;
esac
PL="${1:-165}"

echo "=================================================================="
echo " 05 PERSIST — power=${PL}W, clocks unlocked, governor=performance, KSM=off"
echo " $(date)"
echo "=================================================================="

echo; echo ">>> backing up originals to $BAKDIR"
cp -a /usr/local/bin/mine-tune.sh        "$BAKDIR/" 2>/dev/null
cp -a /etc/local.d/nvidia-mining.start   "$BAKDIR/" 2>/dev/null
cp -a /etc/local.d/ksm.start             "$BAKDIR/" 2>/dev/null
ls -1 "$BAKDIR" | sed 's/^/    /'

echo; echo ">>> writing /usr/local/bin/gpu-tune.sh"
cat > /usr/local/bin/gpu-tune.sh <<EOF
#!/bin/bash
# GPU tuning for the 2x RTX A4500 inference pair (precision-t5810).
#
# REPLACES the old mine-tune.sh, which applied a crypto-MINING efficiency profile
# (-pl 130, -lgc 1200) to a box that serves LLM inference. Under decode load that
# profile dragged the SM clock to 705-810 MHz at 100% util and only ~50C: the
# cards were power-starved, not thermally limited.
#
# Measured 2026-08-31 (bench-vllm.sh, 256 tok, temp=0, single stream, qwen3.8-27b):
#     130W + locked 1200 MHz ... 29.43 tok/s   <- the old mining profile
#     150W + unlocked .......... 32.57 tok/s   67/65 C
#     165W + unlocked .......... 33.43 tok/s   71/70 C   <- CHOSEN (the knee)
#     180W + unlocked .......... 33.87 tok/s   75/73 C
#     200W + unlocked .......... 34.23 tok/s   79/77 C   <- 1C from abort, and SM
#                                                           clocks had ALREADY begun
#                                                           backing off (1845 vs 1860)
# 165W keeps 97.7% of the 200W throughput with an 8C thermal margin instead of 1C.
# Do not raise this without re-running ~/tuning/02c-t5810-soak.sh.
#
# NOTE: power/clock settings cannot cause or prevent VRAM exhaustion. VRAM free
# measured identical (840/842 MiB) at 130/155/165/180/200W. The anti-wedge levers
# are vLLM's --gpu-memory-utilization, --max-model-len, --max-num-seqs and
# cudagraph_capture_sizes -- see /etc/conf.d/vllm-qwen38.
nvidia-smi -pm 1
nvidia-smi -pl ${PL}
nvidia-smi -rgc          # clocks UNLOCKED (was: -lgc 1200)
EOF
chmod +x /usr/local/bin/gpu-tune.sh

echo ">>> writing /etc/local.d/gpu-tune.start"
printf '#!/bin/sh\n# Apply GPU tuning for the A4500 inference pair at boot.\n/usr/local/bin/gpu-tune.sh\n' \
    > /etc/local.d/gpu-tune.start; chmod +x /etc/local.d/gpu-tune.start

echo ">>> writing /etc/local.d/cpu-governor.start"
cat > /etc/local.d/cpu-governor.start <<'EOF'
#!/bin/sh
# CPU governor -> performance. The box shipped with `userspace`, which pins every
# thread at scaling_min (1200 MHz of 2200) forever because nothing ever sets a
# speed. Measured 2026-08-31: embed service :8005 (bge-base, CPU-only, IN the chat
# critical path) went 45 ms -> 24 ms; Qdrant search 2.0 ms -> 1.0 ms.
for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    [ -w "$g" ] && echo performance > "$g"
done
EOF
chmod +x /etc/local.d/cpu-governor.start

echo ">>> disabling the mining profile + KSM boot hooks (renamed, not deleted)"
[ -f /etc/local.d/nvidia-mining.start ] && mv /etc/local.d/nvidia-mining.start /etc/local.d/nvidia-mining.start.disabled && echo "    nvidia-mining.start -> .disabled"
# KSM: measured run=1 with pages_shared=0 after 164 full scans on a 251 GB box
# with no VMs. It scans continuously and shares nothing.
[ -f /etc/local.d/ksm.start ] && mv /etc/local.d/ksm.start /etc/local.d/ksm.start.disabled && echo "    ksm.start -> .disabled"

echo; echo ">>> applying now (so live state matches boot state)"
/usr/local/bin/gpu-tune.sh >/dev/null 2>&1
/etc/local.d/cpu-governor.start
echo 0 > /sys/kernel/mm/ksm/run 2>/dev/null
sleep 3

echo; verify
echo
echo "=================================================================="
echo " PERSISTED. Reboot to confirm, then re-run:  sudo $0 --verify"
echo " Rollback anytime:  sudo $0 --rollback"
echo " Backups: $BAKDIR"
echo "=================================================================="
