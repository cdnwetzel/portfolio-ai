#!/bin/bash
# bench_quiet.sh — bench-vllm.sh, but INVALIDATED if anything else was in the engine.
#
# WHY. bench-vllm.sh measures SINGLE-STREAM decode. vLLM does continuous batching, so a
# concurrent request does not queue behind the bench -- it shares the step, and the bench's
# per-request rate collapses while AGGREGATE throughput rises. Caught live 2026-09-13:
#
#   13:29:57  gen=16.7 tok/s  running=1
#   13:30:07  gen=37.3 tok/s  running=2     <- a real site query arrived
#   13:30:17  gen=35.7 tok/s  running=3
#   13:30:27  gen=71.9 tok/s  running=2     <- aggregate is FINE; single-stream is not
#
# The bench read 33.4 -> 23.1 -> 20.0 across those three runs. Earlier the same day, three
# readings of 24.3/23.6/25.2 were blamed on "autotune warmup" and later "recovered" to 33.5.
# That story never reproduced on demand. Contention explains all of it, and unlike warmup it
# is directly observable in the engine log. A checkable mechanism replaced a plausible one.
#
# Contenders: real visitors (the site is public), the VPS health aggregator's E2E smoke probe
# (SMOKE_INTERVAL_SEC=1800), and whoever is clicking "test" -- which is exactly what happened.
# Pause the smoke probe for a bench window with:
#   ssh root@cwetzel.com 'systemctl stop portfolio-health.timer'   # ... and start it after
# The Running:N check below catches everything else, including the ones you do not control.
#
# Usage: bench_quiet.sh [runs]   -> prints per-run tok/s and a VALID/INVALID verdict
set -uo pipefail
PORT=8007
RUNS="${1:-3}"
LOG=/var/log/qwen38/writer.log

_before=$(wc -l < "$LOG")
OUT=$( cd /opt/vllm-service && ./bench-vllm.sh "$PORT" "$RUNS" 2>&1 )
_after=$(wc -l < "$LOG")

echo "$OUT" | grep -E '^  run |MEAN'

# Every "Running: N reqs" line the engine emitted during the window. The bench itself is 1.
_max=$(sed -n "$((_before+1)),${_after}p" "$LOG" \
       | grep -aoE 'Running: [0-9]+ reqs' | grep -oE '[0-9]+' | sort -rn | head -1)
_max=${_max:-0}
echo "  peak concurrent requests during window: ${_max}"
if [ "$_max" -gt 1 ]; then
    echo "  *** INVALID: something else shared the engine. Single-stream numbers from this"
    echo "      window measure a queue, not the config. Re-run when peak == 1. ***"
    exit 2
fi
echo "  VALID: single-stream throughout"
