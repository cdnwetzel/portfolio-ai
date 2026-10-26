#!/bin/bash
# Throughput check for a vLLM backend slot — run BEFORE and AFTER any restart.
#
# WHY THIS EXISTS
# The T5810's speed is not a default. It is the result of measured tuning
# (../psaios/docs/t5810-vllm-cudagraph-tuning-2026-08-19.md), and three flags
# have to survive together or it collapses to roughly a quarter of the rate:
#   1. CUDA graphs ON        (i.e. NO --enforce-eager)
#   2. --disable-custom-all-reduce   custom AR breaks graph capture on this
#                                    2x A4500 NVLink pair
#   3. --compilation-config {"cudagraph_capture_sizes":[1,2,4,8]}
#                                    vLLM captures ~70 sizes by default and
#                                    capture memory scales with the count
# Lose any one and the loss is silent — the server still answers, just slowly.
# Nothing in the health check or the self-test would notice. This would.
#
# Methodology deliberately matches psaios/tools/t5810-vllm/bench.sh: a 256-token
# completion at temperature 0, single stream. ignore_eos forces the full 256 so
# the number is a steady-state decode rate rather than mostly prefill.
#
# Usage:  ./bench-vllm.sh [port] [runs]
#         ./bench-vllm.sh 8007 3
#
# REFERENCE NUMBERS
#   qwen3.8-27b on T5810, 2026-08-30 (pre-cutover):  29.6 / 29.3 / 29.3 tok/s
#   Historical, 14B on 0.14.0 (tuning doc):
#     eager .............. 6.2, 6.3
#     CUDA graphs on ..... 27.7, 28.1, 27.3, 26.5   <- the 4.4x
# A result near ~6-7 tok/s means the graph tuning was lost, NOT that the box is
# busy. Check the argv for the three flags above before anything else.
set -uo pipefail

PORT="${1:-8007}"
RUNS="${2:-3}"
BASE="http://127.0.0.1:${PORT}"

MODEL="$(curl -sf -m 10 "${BASE}/v1/models" | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"][0]["id"])' 2>/dev/null || true)"
[ -n "${MODEL}" ] || { echo "FATAL: no model served on :${PORT}" >&2; exit 1; }
echo "benchmarking '${MODEL}' on :${PORT}  (${RUNS} runs, 256 tok, temp=0, single stream)"

# Report the tuning flags alongside the number, so a slow result is immediately
# diagnosable instead of merely alarming.
CMD="$(ps -eo args | grep -F 'bin/vllm serve' | grep -v grep | head -1 || true)"
if [ -n "${CMD}" ]; then
    case "${CMD}" in *--enforce-eager*) echo "  WARN: --enforce-eager present -> CUDA graphs OFF" ;; *) echo "  ok: CUDA graphs on (no --enforce-eager)" ;; esac
    case "${CMD}" in *--disable-custom-all-reduce*) echo "  ok: --disable-custom-all-reduce" ;; *) echo "  WARN: custom all-reduce NOT disabled -> graph capture likely broken" ;; esac
    case "${CMD}" in *cudagraph_capture_sizes*) echo "  ok: capture sizes capped" ;; *) echo "  WARN: capture sizes not capped -> OOM or fallback risk" ;; esac
fi

for i in $(seq 1 "${RUNS}"); do
    start="$(date +%s.%N)"
    resp="$(curl -sf -m 300 "${BASE}/v1/completions" -H 'Content-Type: application/json' \
        -d "{\"model\":\"${MODEL}\",\"prompt\":\"Write a Python function that reverses a singly linked list in place.\",\"max_tokens\":256,\"temperature\":0,\"ignore_eos\":true}" || true)"
    end="$(date +%s.%N)"
    [ -n "${resp}" ] || { echo "  run ${i}: REQUEST FAILED"; continue; }
    START="${start}" END="${end}" RUN="${i}" python3 -c '
import json, os, sys
d = json.load(sys.stdin)
ct = d.get("usage", {}).get("completion_tokens", 0)
el = float(os.environ["END"]) - float(os.environ["START"])
run = os.environ["RUN"]
rate = ct / el if el > 0 else 0.0
print(f"  run {run}: tokens={ct} elapsed={el:.2f}s tok/s={rate:.1f}")
' <<< "${resp}"
done
