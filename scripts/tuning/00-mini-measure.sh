#!/bin/bash
# 00-mini-measure.sh — before/after suite for the M4 Mac Mini. Read-only, no sudo.
# Run on the Mini itself:  ./00-mini-measure.sh baseline
#
# CONTEXT: this box is NOT in cwdotcom's serving path — it holds a tunnel to the
# T5810 and runs its own ollama. Tuning it is a separate concern from the site.
#
# CEILING: M4 (base) is ~120 GB/s memory bandwidth. A 4.7 GB q4 7B reads ~4.7 GB
# per token, so the hard roofline is ~25.5 tok/s. Measured 21.6 = ~85% of it.
# There are about 4 tok/s available in TOTAL. Do not expect a throughput win here;
# the real prize is MEMORY (858 MB of active swap measured 2026-08-31).
set -uo pipefail
LABEL="${1:-run}"
LOGDIR="$HOME/tuning-logs"; mkdir -p "$LOGDIR"
LOG="$LOGDIR/mini-measure-${LABEL}-$(date +%Y%m%d-%H%M%S).log"
ln -sfn "$LOG" "$LOGDIR/mini-measure-latest.log"
exec > >(tee -a "$LOG") 2>&1
export PATH=/opt/homebrew/bin:$PATH

MODEL="${MODEL:-qwen2.5:7b-instruct}"
echo "=================================================================="
echo " MINI MEASURE — label=$LABEL  $(date)"
echo "=================================================================="

echo; echo "--- machine load (a busy Mac invalidates every number below) ---"
uptime | sed 's/^/  /'
ps -Ao pcpu,comm -r | head -4 | sed 's/^/  /'

echo; echo "--- hardware / memory ---"
sysctl -n hw.model; sysctl -n machdep.cpu.brand_string
echo -n "  RAM: "; echo "$(( $(sysctl -n hw.memsize) / 1073741824 )) GB"
echo -n "  iogpu.wired_limit_mb: "; sysctl -n iogpu.wired_limit_mb 2>/dev/null
echo -n "  "; sysctl -n vm.swapusage
memory_pressure 2>/dev/null | grep -i "free percentage" | sed 's/^/  /'

echo; echo "--- ollama env actually in effect (LIVE process, not the plist) ---"
PID=$(pgrep -f "ollama serve" | head -1)
echo "  pid=${PID:-none}"
[ -n "$PID" ] && ps eww -p "$PID" 2>/dev/null | tr ' ' '\n' | grep -E '^OLLAMA_' | sed 's/^/    /'
echo "  (a variable absent here is NOT in effect, whatever the plist says)"
echo -n "  ollama: "; ollama --version 2>&1 | head -1

echo; echo "--- models that CANNOT fit in RAM (will swap or spill to CPU) ---"
RAMGB=$(( $(sysctl -n hw.memsize) / 1073741824 ))
ollama list 2>/dev/null | awk -v ram="$RAMGB" 'NR>1 {
    sz=$3; unit=$4; gb = (unit=="GB") ? sz+0 : sz/1024
    if (gb > ram*0.80) printf "  !! %-32s %s %s  (>80%% of %d GB RAM)\n", $1, $3, $4, ram
}'
echo "  (none listed = every model fits)"

echo; echo "--- throughput + TTFT: $MODEL ---"
for i in 1 2 3; do
curl -s --max-time 150 http://127.0.0.1:11434/api/generate \
  -d "{\"model\":\"$MODEL\",\"prompt\":\"Write 200 words about computer networking.\",\"stream\":false,\"options\":{\"temperature\":0,\"num_predict\":256}}" \
| python3 -c '
import sys,json
d=json.load(sys.stdin)
ec=d.get("eval_count",0); ed=d.get("eval_duration",1)/1e9
pc=d.get("prompt_eval_count",0); pd=d.get("prompt_eval_duration",0)/1e9
ld=d.get("load_duration",0)/1e9
print(f"  gen {ec:4d} tok in {ed:6.2f}s = {ec/ed:5.1f} tok/s | prefill {pc:3d} tok {pd*1000:6.0f} ms | load {ld*1000:6.0f} ms")'
done

echo; echo "--- residency (PROCESSOR must say 100% GPU; any CPU%% means it spilled) ---"
ollama ps 2>&1 | sed 's/^/  /'

echo; echo "--- swap after the run (growth = memory pressure) ---"
sysctl -n vm.swapusage | sed 's/^/  /'
echo; echo "DONE — $LOG"
