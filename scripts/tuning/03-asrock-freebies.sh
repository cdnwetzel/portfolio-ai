#!/bin/bash
# 03-asrock-freebies.sh — asrock B550 / RTX 5060 Ti (verifier + reranker node).
#   A) CPU governor powersave -> performance
#      measured: 5950X averaging 2338 MHz against a 4.9 GHz boost. Affects the
#      reranker (:8006, IN the chat critical path) and the judge's CPU-side prefill.
#   B) Ollama: OLLAMA_FLASH_ATTENTION=1 + OLLAMA_KV_CACHE_TYPE=q8_0
#      measured: BOTH UNSET. flash-attn is a speed+memory win; q8_0 KV halves KV
#      footprint (needs flash-attn to take effect). More headroom against the
#      reranker on the same 16 GB card (judge 11.4 GB + reranker 1.6 GB today).
#   C) OLLAMA_KEEP_ALIVE 60s -> 30m
#      measured: /etc/conf.d/ollama says 60s; CLAUDE.md documents 30m. The verifier
#      passes keep_alive per-request so it holds today, but any request that omits
#      it evicts an 11.4 GB model. Make the service default match the doc.
#
# (B) and (C) require an ollama restart -> the judge reloads. The verifier is
# fail-open and out-of-band, so chat is unaffected, but run it off-peak anyway.
#
# Rollback: sudo ./03-asrock-freebies.sh --rollback
set -uo pipefail

LOGDIR=/home/chris/tuning-logs; mkdir -p "$LOGDIR"
LOG="$LOGDIR/03-asrock-$(date +%Y%m%d-%H%M%S).log"
ln -sfn "$LOG" "$LOGDIR/03-latest.log"
exec > >(tee -a "$LOG") 2>&1

[ "$(id -u)" -eq 0 ] || { echo "must run as root (sudo)"; exit 1; }
CONF=/etc/conf.d/ollama
BAK="${CONF}.pre-tuning"

rerank_bench() {
  echo -n "  rerank :8006 x5 -> "
  for _ in 1 2 3 4 5; do
    curl -s -o /dev/null -w "%{time_total}\n" --max-time 20 -X POST http://10.0.1.115:8006/rerank \
      -H 'Content-Type: application/json' \
      -d '{"query":"what gpus does the t5810 have","documents":["The T5810 has two RTX A4500 GPUs joined by NVLink.","Qdrant stores dense vectors for retrieval.","The asrock B550 runs the faithfulness verifier.","vLLM serves the model with tensor parallelism.","The embedding service runs bge-base on CPU."],"top_k":5}'
  done | awk '{s+=$1; if($1>mx)mx=$1; if(mn==0||$1<mn)mn=$1; n++}
              END{printf "mean %.1f ms  (min %.1f  max %.1f)\n", s/n*1000, mn*1000, mx*1000}'
}
state() {
  echo -n "  governor: "; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
  grep MHz /proc/cpuinfo | awk '{s+=$4;n++} END{printf "  cpu avg %.0f MHz over %d threads\n",s/n,n}'
  nvidia-smi --query-gpu=power.draw,clocks.sm,temperature.gpu,memory.used --format=csv,noheader | sed 's/^/  gpu: /'
  echo "  ollama env:"; grep -v '^#' "$CONF" 2>/dev/null | grep . | sed 's/^/    /'
}

rollback() {
  echo; echo ">>> ROLLBACK"
  for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo powersave > "$g" 2>/dev/null; done
  if [ -f "$BAK" ]; then cp "$BAK" "$CONF"; echo "  restored $CONF from $BAK"; rc-service ollama restart; fi
  sleep 3; state; echo ">>> rolled back."
}
[ "${1:-}" = "--rollback" ] && { rollback; exit 0; }

echo "=================================================================="; echo " 03 ASROCK FREEBIES — $(date)"; echo "=================================================================="
echo; echo "--- BEFORE ---"; state; rerank_bench

echo; echo ">>> A) governor powersave -> performance"
for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo performance > "$g"; done
sleep 3
echo "--- after governor only ---"; state; rerank_bench

echo; echo ">>> B/C) ollama flash-attn + q8_0 KV + keep-alive 30m"
[ -f "$BAK" ] || cp "$CONF" "$BAK"
echo "  backup: $BAK"
sed -i '/OLLAMA_FLASH_ATTENTION/d;/OLLAMA_KV_CACHE_TYPE/d;/OLLAMA_KEEP_ALIVE/d' "$CONF"
cat >> "$CONF" <<'EOF'
OLLAMA_FLASH_ATTENTION="1"
OLLAMA_KV_CACHE_TYPE="q8_0"
OLLAMA_KEEP_ALIVE="30m"
EOF
rc-service ollama restart
echo "  waiting 20s for ollama to come back..."; sleep 20

echo; echo "--- AFTER (judge must reload on first verify; expect one slow call) ---"; state; rerank_bench
echo -n "  verifier health: "; curl -s --max-time 10 http://10.0.1.115:8007/health | head -c 150; echo

echo
echo "GO/NO-GO: keep if rerank mean improved and the verifier still answers."
echo "  rollback: sudo $0 --rollback"
echo "  NOTE: governor resets on reboot; the ollama conf change PERSISTS."
echo "log: $LOG"
