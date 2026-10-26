#!/bin/bash
# Power/utilisation sampler for the T5810 inference box.
#
# WHY: the 2026-09-01 UPS sizing was built from two spot readings and a duty cycle
# inferred from log timestamps. That was enough to establish the box exceeds a 330W
# UPS, but not enough to size runtime properly — this workload is BURSTY (a public
# portfolio chat, ~200-360 generations/day at ~8s each, so roughly 2-3% duty cycle),
# and peak draw and average draw imply very different UPS requirements.
#
# PRIVACY (red-lines.md #2): metadata ONLY. Watts, temperatures, utilisation
# percentages, clock speeds, memory totals. This file records nothing about what was
# asked or answered — it cannot, it never sees a request. Same rule as the rest of
# the stack's telemetry: counts and durations, never content.
#
# Output: CSV, one row per sample, appended. Header written once on file creation.
#   ts_unix,iso8601,gpu0_w,gpu1_w,gpu_total_w,gpu0_util,gpu1_util,gpu0_c,gpu1_c,
#   gpu0_mem_used_mib,gpu1_mem_used_mib,cpu_pkg_w,loadavg1
#
# Usage:
#   power-sample.sh              # one sample, appended to $POWER_LOG
#   POWER_LOG=/tmp/p.csv ./power-sample.sh
#
# Intended cadence: every 30s via cron. That is fine to run continuously — reading
# nvidia-smi and RAPL costs nothing measurable and does not touch the GPUs' compute.
set -uo pipefail

POWER_LOG="${POWER_LOG:-/var/log/power-metrics.csv}"

# CPU package power via Intel RAPL. RAPL exposes a monotonically increasing ENERGY
# counter in microjoules, not instantaneous power, so power = delta_energy / delta_t.
# A short window is enough and keeps the sampler cheap.
cpu_pkg_w() {
    local f=/sys/class/powercap/intel-rapl:0/energy_uj
    [ -r "$f" ] || { echo ""; return; }
    local a b
    a=$(cat "$f" 2>/dev/null) || { echo ""; return; }
    sleep 1
    b=$(cat "$f" 2>/dev/null) || { echo ""; return; }
    # The counter wraps; a negative delta means it rolled over, so skip that sample
    # rather than emit a wild number that would poison any average computed later.
    if [ "$b" -lt "$a" ]; then echo ""; return; fi
    echo $(( (b - a) / 1000000 ))
}

read -r g0w g1w g0u g1u g0c g1c g0m g1m <<<"$(
    nvidia-smi --query-gpu=power.draw,utilization.gpu,temperature.gpu,memory.used \
               --format=csv,noheader,nounits 2>/dev/null \
    | awk -F', *' '{w[NR]=$1; u[NR]=$2; c[NR]=$3; m[NR]=$4}
                   END {printf "%s %s %s %s %s %s %s %s", w[1],w[2],u[1],u[2],c[1],c[2],m[1],m[2]}'
)"
[ -n "${g0w:-}" ] || exit 0   # no GPUs / nvidia-smi unavailable: emit nothing

cpu=$(cpu_pkg_w)
load=$(awk '{print $1}' /proc/loadavg 2>/dev/null)
total=$(awk -v a="$g0w" -v b="$g1w" 'BEGIN{printf "%.1f", a+b}')

if [ ! -f "$POWER_LOG" ]; then
    echo "ts_unix,iso8601,gpu0_w,gpu1_w,gpu_total_w,gpu0_util,gpu1_util,gpu0_c,gpu1_c,gpu0_mem_used_mib,gpu1_mem_used_mib,cpu_pkg_w,loadavg1" > "$POWER_LOG"
    chmod 0644 "$POWER_LOG"
fi

printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
    "$(date +%s)" "$(date -Is)" \
    "$g0w" "$g1w" "$total" "$g0u" "$g1u" "$g0c" "$g1c" "$g0m" "$g1m" \
    "${cpu:-}" "${load:-}" >> "$POWER_LOG"
