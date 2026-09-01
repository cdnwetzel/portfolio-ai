#!/bin/bash
# 00-measure.sh — full baseline/after measuring suite for the home-lab inference stack.
# Uses ONLY tools already on the boxes. Safe: read-only, no config changes.
# Run this BEFORE and AFTER every tuning step. Run from the T5810 (it reaches all three).
#
# Usage:  ./00-measure.sh [label]
#         ./00-measure.sh baseline
#         ./00-measure.sh after-power-200w
set -uo pipefail

LABEL="${1:-run}"
TS=$(date +%Y%m%d-%H%M%S)
LOGDIR=/home/chris/tuning-logs
mkdir -p "$LOGDIR"
LOG="$LOGDIR/measure-${LABEL}-${TS}.log"
ln -sfn "$LOG" "$LOGDIR/measure-latest.log"

ASROCK=chris@10.0.1.115
MINI=cwetzel@10.0.1.20

exec > >(tee -a "$LOG") 2>&1
echo "==================================================================="
echo " MEASURE SUITE — label=$LABEL   $(date)"
echo " log: $LOG"
echo "==================================================================="

hr(){ echo; echo "--- $* ---"; }

# ---------------------------------------------------------------- T5810
hr "T5810 :: hardware state"
nvidia-smi --query-gpu=index,power.limit,power.draw,clocks.sm,clocks.max.sm,clocks.mem,temperature.gpu,memory.used,memory.free \
           --format=csv 2>&1
echo -n "cpu governor: "; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null
grep MHz /proc/cpuinfo | awk '{s+=$4;n++} END{printf "cpu avg %.0f MHz over %d threads\n",s/n,n}'
echo -n "KSM run: "; cat /sys/kernel/mm/ksm/run 2>/dev/null
echo -n "KSM pages_shared: "; cat /sys/kernel/mm/ksm/pages_shared 2>/dev/null
free -g | head -2

hr "T5810 :: vLLM tok/s  (bench-vllm.sh, 256 tok, temp=0, single stream)"
if [ -x /opt/vllm-service/bench-vllm.sh ]; then
    ( cd /opt/vllm-service && ./bench-vllm.sh 8007 3 2>&1 | grep -E "run |ok:|WARN|benchmarking" )
else
    echo "MISSING /opt/vllm-service/bench-vllm.sh"
fi

hr "T5810 :: vLLM live cmdline flags (assert tuning survived a restart)"
ps -eo args | grep -F 'bin/vllm serve' | grep -v grep | tr ' ' '\n' \
  | grep -A1 -E "gpu-memory-utilization|max-model-len|max-num-seqs|compilation-config|enforce-eager|disable-custom-all-reduce|speculative" | paste - - 2>/dev/null | head -20

hr "T5810 :: vLLM prefix-cache hit rate (last 5 log lines)"
grep -a "Prefix cache hit rate" /var/log/qwen38/writer.log 2>/dev/null | tail -5 \
  | sed 's/.*\(GPU KV cache usage.*\)/  \1/' || echo "(no log)"

hr "T5810 :: embed service :8005  (bge-base CPU — IN the chat critical path)"
for i in 1 2 3 4 5; do
  curl -s -o /dev/null -w "%{time_total} " --max-time 15 -X POST http://127.0.0.1:8005/embed \
       -H 'Content-Type: application/json' \
       -d '{"text":"what infrastructure does chris run at home"}'
done; echo " sec  (5 runs)"

hr "T5810 :: Qdrant :6333 search latency"
VEC=$(curl -s --max-time 15 -X POST http://127.0.0.1:8005/embed -H 'Content-Type: application/json' \
      -d '{"text":"what gpus does the t5810 have"}' | python3 -c 'import sys,json; print(json.dumps(json.load(sys.stdin)["embedding"]))' 2>/dev/null)
if [ -n "$VEC" ]; then
  for i in 1 2 3; do
    curl -s -o /dev/null -w "%{time_total} " --max-time 15 -X POST \
      "http://127.0.0.1:6333/collections/documents/points/search" \
      -H 'Content-Type: application/json' \
      -d "{\"vector\":$VEC,\"limit\":15,\"with_payload\":false}"
  done; echo " sec  (3 runs, top-15)"
else
  echo "SKIP (embed failed)"
fi

# ---------------------------------------------------------------- asrock
hr "asrock :: hardware state"
ssh -o BatchMode=yes -o ConnectTimeout=8 $ASROCK '
  nvidia-smi --query-gpu=name,power.limit,power.draw,clocks.sm,clocks.max.sm,temperature.gpu,memory.used,memory.total --format=csv
  echo -n "cpu governor: "; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
  grep MHz /proc/cpuinfo | awk "{s+=\$4;n++} END{printf \"cpu avg %.0f MHz over %d threads\n\",s/n,n}"
  echo "--- ollama env ---"; grep -v "^#" /etc/conf.d/ollama 2>/dev/null | grep .
' 2>&1

hr "asrock :: reranker :8006 latency (GPU cross-encoder — IN the chat critical path)"
ssh -o BatchMode=yes -o ConnectTimeout=8 $ASROCK '
for i in 1 2 3 4 5; do
  curl -s -o /dev/null -w "%{time_total} " --max-time 20 -X POST http://10.0.1.115:8006/rerank \
    -H "Content-Type: application/json" \
    -d "{\"query\":\"what gpus does the t5810 have\",\"documents\":[\"The T5810 has two RTX A4500 GPUs joined by NVLink.\",\"Qdrant stores dense vectors for retrieval.\",\"The asrock B550 runs the faithfulness verifier.\",\"vLLM serves the model with tensor parallelism.\",\"The embedding service runs bge-base on CPU.\"],\"top_k\":5}"
done; echo " sec  (5 runs, 5 docs)"' 2>&1

hr "asrock :: verifier :8007 health + judge residency"
ssh -o BatchMode=yes -o ConnectTimeout=8 $ASROCK '
  curl -s --max-time 8 http://10.0.1.115:8007/health | head -c 200; echo
  echo "--- GPU tenants ---"
  nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv' 2>&1

# ---------------------------------------------------------------- mini
hr "Mac Mini :: hardware + memory pressure"
ssh -o BatchMode=yes -o ConnectTimeout=8 $MINI '
  sysctl -n hw.model; sysctl -n machdep.cpu.brand_string
  echo -n "iogpu.wired_limit_mb: "; sysctl -n iogpu.wired_limit_mb 2>/dev/null
  sysctl vm.swapusage
  memory_pressure 2>/dev/null | grep -i "free percentage"' 2>&1

hr "Mac Mini :: ollama tok/s (qwen2.5:7b-instruct, 256 tok, temp=0)"
ssh -o BatchMode=yes -o ConnectTimeout=8 $MINI 'export PATH=/opt/homebrew/bin:$PATH
for i in 1 2; do
curl -s --max-time 120 http://127.0.0.1:11434/api/generate \
  -d "{\"model\":\"qwen2.5:7b-instruct\",\"prompt\":\"Write 200 words about computer networking.\",\"stream\":false,\"options\":{\"temperature\":0,\"num_predict\":256}}" \
| python3 -c "
import sys,json
d=json.load(sys.stdin)
ec=d.get(\"eval_count\",0); ed=d.get(\"eval_duration\",1)/1e9
pc=d.get(\"prompt_eval_count\",0); pd=d.get(\"prompt_eval_duration\",1)/1e9
print(f\"  gen {ec} tok in {ed:.2f}s = {ec/ed:.1f} tok/s | prefill {pc} tok in {pd:.2f}s\")"
done
echo "--- resident ---"; ollama ps 2>&1 | head -3' 2>&1

hr "END-TO-END :: full chain health from the VPS (through the tunnel)"
ssh -o BatchMode=yes -o ConnectTimeout=8 root@cwetzel.com '
for p in 8004 8005 8016 8007; do
  printf "  :%s -> " $p
  curl -s -o /dev/null -w "%{http_code} in %{time_total}s\n" --max-time 8 http://127.0.0.1:$p/health 2>/dev/null || echo fail
done
echo -n "  labrouter backends: "; curl -s --max-time 8 http://127.0.0.1:8004/health' 2>&1

echo
echo "==================================================================="
echo " DONE — $LOG"
echo "==================================================================="
