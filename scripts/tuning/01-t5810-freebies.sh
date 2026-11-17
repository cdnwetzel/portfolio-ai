#!/bin/bash
# 01-t5810-freebies.sh — zero-risk, instantly reversible, NO service restart.
#   A) KSM off   — measured: run=1, pages_shared=0 after 164 full scans on a 251 GB
#                  box with no VMs. It is scanning memory and sharing nothing.
#                  Set at boot by /etc/local.d/ksm.start.
#   B) CPU governor userspace -> performance
#                  measured: all 44 threads pinned flat at ~1199 MHz against a
#                  2200 MHz scaling_max. `userspace` with no setter daemon never
#                  ramps. This throttles the bge-base embedder (:8005, CPU-only,
#                  IN the chat critical path), Qdrant, labrouter, and vLLM's
#                  per-decode-step Python scheduler/detokenizer.
#
# Acceptance metric: embed :8005 latency (baseline measured 2026-08-31 = ~40 ms).
# Rollback: sudo ./01-t5810-freebies.sh --rollback   (also undone by a reboot)
set -uo pipefail

LOGDIR=/home/chris/tuning-logs; mkdir -p "$LOGDIR"
LOG="$LOGDIR/01-t5810-freebies-$(date +%Y%m%d-%H%M%S).log"
ln -sfn "$LOG" "$LOGDIR/01-latest.log"
exec > >(tee -a "$LOG") 2>&1

[ "$(id -u)" -eq 0 ] || { echo "must run as root (sudo)"; exit 1; }

embed_bench() {
    local n=10 t
    echo -n "  embed :8005 x$n -> "
    for _ in $(seq 1 $n); do
        curl -s -o /dev/null -w "%{time_total}\n" --max-time 15 -X POST http://127.0.0.1:8005/embed \
          -H 'Content-Type: application/json' \
          -d '{"text":"what infrastructure does chris run at home"}'
    done | awk '{s+=$1; if($1>mx)mx=$1; if(mn==0||$1<mn)mn=$1; n++}
                END{printf "mean %.1f ms  (min %.1f  max %.1f)\n", s/n*1000, mn*1000, mx*1000}'
}

cpu_state() {
    echo -n "  governor: "; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
    grep MHz /proc/cpuinfo | awk '{s+=$4;n++} END{printf "  cpu avg %.0f MHz over %d threads\n",s/n,n}'
    echo -n "  KSM run=";        cat /sys/kernel/mm/ksm/run
    echo -n "  KSM pages_shared="; cat /sys/kernel/mm/ksm/pages_shared
}

rollback() {
    echo; echo ">>> ROLLBACK"
    echo 1 > /sys/kernel/mm/ksm/run 2>/dev/null
    for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo userspace > "$g" 2>/dev/null; done
    for s in /sys/devices/system/cpu/cpu*/cpufreq/scaling_setspeed; do echo 1200000 > "$s" 2>/dev/null; done
    sleep 1; cpu_state
    echo ">>> restored: KSM on, governor userspace @1200 MHz"
}

[ "${1:-}" = "--rollback" ] && { rollback; exit 0; }

echo "=================================================================="
echo " 01 T5810 FREEBIES — $(date)"
echo "=================================================================="
echo; echo "--- BEFORE ---"; cpu_state; embed_bench

echo; echo ">>> A) disabling KSM (frees CPU; it shares 0 pages)"
echo 0 > /sys/kernel/mm/ksm/run
echo ">>> B) governor userspace -> performance on all 44 threads"
for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo performance > "$g"; done
sleep 3

echo; echo "--- AFTER ---"; cpu_state; embed_bench

echo
echo "GO/NO-GO: keep if embed mean dropped materially and nothing else regressed."
echo "  rollback:  sudo $0 --rollback"
echo "  persist :  see 05-persist.sh (only after a soak)"
echo "  NOTE: a reboot reverts BOTH (ksm.start re-enables KSM; governor resets)."
echo "log: $LOG"
