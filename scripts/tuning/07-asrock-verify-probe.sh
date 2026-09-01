#!/bin/bash
# 07-asrock-verify-probe.sh (v2) — measure what 03's keep-alive change bought.
#
# v1 used /usr/bin/time, which is NOT installed on Gentoo (time is a shell builtin).
# v2 times with EPOCHREALTIME, and FORCES a cold start so the measurement is real:
# ollama unloads a model when sent keep_alive:0, which is the only way to test the
# reload path once the judge is already resident.
#
#   call 0 = forced unload           (confirm VRAM drops)
#   call 1 = COLD  -> pays the ~11.4 GB reload
#   call 2 = WARM  -> should be dramatically faster
#   call 3 = WARM  -> confirms it stayed resident (this is what keep_alive=30m buys)
#
# No sudo needed. Run ON asrock as chris so logs land in ~/tuning-logs.
set -uo pipefail
LOGDIR="$HOME/tuning-logs"; mkdir -p "$LOGDIR"
LOG="$LOGDIR/07-verify-probe-$(date +%Y%m%d-%H%M%S).log"
ln -sfn "$LOG" "$LOGDIR/07-latest.log"
exec > >(tee -a "$LOG") 2>&1

V=http://10.0.1.115:8007
OLLAMA=http://127.0.0.1:11434
JUDGE=$(curl -s -m 10 "$V/health" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("model",""))' 2>/dev/null)

vram() { nvidia-smi --query-compute-apps=process_name,used_memory --format=csv,noheader \
         | grep -i llama || echo "      (judge not resident)"; }
now()  { printf '%s' "$EPOCHREALTIME"; }

echo "=================================================================="
echo " 07 VERIFY PROBE v2 — $(date)"
echo " judge=$JUDGE   keep_alive=$(grep -o 'OLLAMA_KEEP_ALIVE=.*' /etc/conf.d/ollama 2>/dev/null)"
echo "=================================================================="

PAYLOAD='{"request_id":"tuning-probe","query":"What GPUs does the T5810 have?","answer":"The T5810 has two NVIDIA RTX A4500 GPUs joined by an NVLink bridge, running vLLM with tensor parallelism across both cards.","chunks":[{"title":"T5810","source":"knowledge_base/infrastructure/homelab_t5810.md","content":"The Dell Precision T5810 has two RTX A4500 GPUs joined by an NVLink bridge (NV4 topology). Usable VRAM is 20470 MiB per card. It runs vLLM in tensor-parallel mode across both cards."}]}'

echo; echo "  resident BEFORE:"; vram | sed 's/^/      /'

echo; echo "  --- call 0: forcing unload (keep_alive:0) ---"
curl -s -m 60 "$OLLAMA/api/generate" \
     -d "{\"model\":\"$JUDGE\",\"prompt\":\"x\",\"keep_alive\":0,\"options\":{\"num_predict\":1}}" \
     -o /dev/null
sleep 6
echo "      VRAM after unload:"; vram | sed 's/^/      /'

for i in 1 2 3; do
    [ "$i" = 1 ] && label="COLD (pays the reload)" || label="WARM"
    echo; echo "  --- call $i: $label ---"
    OUT=$(mktemp)
    T0=$(now)
    curl -s -m 300 -X POST "$V/verify" -H 'Content-Type: application/json' -d "$PAYLOAD" -o "$OUT"
    T1=$(now)
    awk -v a="$T0" -v b="$T1" 'BEGIN{printf "      wall: %.2f s\n", b-a}'
    python3 -c '
import json, sys
# NOTE: no backslash-escaped quotes inside f-strings - Python rejects them.
try:
    d = json.load(open(sys.argv[1]))
    keys = ("verdict_type", "faithfulness", "flagged", "latency_s")
    print("      " + "  ".join("%s=%s" % (k, d.get(k)) for k in keys))
except Exception as e:
    print("      parse failed: %s" % e)
    print("      raw:", open(sys.argv[1]).read()[:300])' "$OUT"
    rm -f "$OUT"
    echo "      VRAM:"; vram | sed 's/^/      /'
done

echo
echo "=================================================================="
echo " READ: call 1 >> calls 2/3 = the reload is real, and keep_alive=30m is"
echo " what stops sparse traffic paying it on EVERY query. Judge VRAM was"
echo " 11,380 MiB before q8_0 KV — compare."
echo " log: $LOG"
echo "=================================================================="
