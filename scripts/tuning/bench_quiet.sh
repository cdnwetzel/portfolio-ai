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

# Acceptance FROM THIS WINDOW ONLY. The harness previously parsed the last N SpecDecoding
# windows, which the probes dominate because they run AFTER the bench -- so the acceptance
# figure described a different workload than the tok/s it was divided into. ms/step is
# tok/s / acceptance, so mixing windows corrupts the one axis the whole cost model rests on.
# Co-locating them here makes both describe the same 256-token bench prompt.
sed -n "$((_before+1)),${_after}p" "$LOG" | grep -a 'SpecDecoding metrics' > /tmp/.spec.$$ || true
if [ -s /tmp/.spec.$$ ]; then
  python3 - /tmp/.spec.$$ <<'PY'
import re, sys
rows=[]
for l in open(sys.argv[1]):
    try:
        rows.append((int(re.search(r'Accepted: (\d+) tokens',l).group(1)),
                     int(re.search(r'Drafted: (\d+) tokens',l).group(1)),
                     [float(x) for x in re.search(r'Per-position acceptance rate: ([\d., ]+?), Avg',l).group(1).split(', ')]))
    except Exception: pass
if rows:
    A=sum(r[0] for r in rows); D=sum(r[1] for r in rows); k=len(rows[-1][2]); steps=D/k
    acc=1+A/steps
    print(f"  acceptance (BENCH WINDOW ONLY): {acc:.2f} tokens/step  "
          f"[{len(rows)} windows, {A}/{D} = {100*A/D:.1f}% draft acceptance]")
    for i in range(k):
        v=[r[2][i] for r in rows if len(r[2])>i]
        print(f"    pos {i+1}: {sum(v)/len(v):.3f}")
PY
else
  echo "  (no SpecDecoding metrics in window — non-speculative config)"
fi
rm -f /tmp/.spec.$$
