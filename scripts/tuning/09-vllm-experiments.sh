#!/bin/bash
# 09-vllm-experiments.sh — apply ONE vLLM flag experiment, restart, verify, measure,
# and AUTO-REVERT if the engine does not come back.
#
# WHY A LAUNCHER HOOK: start-qwen38.sh hardcodes argv on purpose — two flags carry JSON
# with double quotes, and OpenRC's command_args word-splitting strips them. This adds a
# VLLM_EXTRA_ARGS hook that preserves quoting via a bash array, leaving the existing
# argv untouched.
#
# ALREADY SETTLED WITHOUT A RESTART (do not re-test):
#   symm-mem all-reduce — REQUIRES device capability 9.0 (Hopper) or 10.x (Blackwell).
#   The A4500 is 8.6, so SymmMemCommunicator disables itself and PYNCCL is correct.
#   VLLM_ALLREDUCE_USE_SYMM_MEM already defaults True; setting it changes nothing.
#
# EXPERIMENTS:
#   prefix  --enable-prefix-caching
#           enable_prefix_caching is False today NOT as a bug: arg_utils.py:2604 sets
#           `default = is_prefix_caching_supported and not is_hybrid` — hybrid models
#           are supported but opt-in in 0.27.1. Helps TTFT when a prompt prefix repeats
#           (the constant system prompt across every request, and multi-turn history).
#   ngram   --speculative-config ngram
#           No draft model, no extra VRAM. Proposes continuations by matching against
#           the prompt itself, so it wins exactly when the answer quotes retrieved
#           context — which grounded RAG does constantly.
#
# Usage (as root, on the T5810):
#   ./09-vllm-experiments.sh baseline    # measure current config, no change
#   ./09-vllm-experiments.sh prefix
#   ./09-vllm-experiments.sh ngram
#   ./09-vllm-experiments.sh revert      # restore original launcher + conf, restart
set -uo pipefail
LOGDIR=/home/chris/tuning-logs; mkdir -p "$LOGDIR"
EXP="${1:-}"
LOG="$LOGDIR/09-vllm-${EXP:-none}-$(date +%Y%m%d-%H%M%S).log"
ln -sfn "$LOG" "$LOGDIR/09-latest.log"
exec > >(tee -a "$LOG") 2>&1
[ "$(id -u)" -eq 0 ] || { echo "must run as root (sudo)"; exit 1; }

LAUNCHER=/opt/vllm-service/start-qwen38.sh
CONF=/etc/conf.d/vllm-qwen38
BAKDIR=/root/vllm-exp-backups; mkdir -p "$BAKDIR"
PORT=8007
READY_WAIT=420

banner(){ echo; echo "=================================================================="; echo " $*"; echo "=================================================================="; }

backup_once() {
    [ -f "$BAKDIR/start-qwen38.sh.orig" ] || { cp -a "$LAUNCHER" "$BAKDIR/start-qwen38.sh.orig"; echo "  backed up launcher"; }
    [ -f "$BAKDIR/vllm-qwen38.orig" ]     || { cp -a "$CONF"     "$BAKDIR/vllm-qwen38.orig";     echo "  backed up conf.d"; }
}

add_hook() {
    grep -q 'VLLM_EXTRA_ARGS' "$LAUNCHER" && { echo "  hook already present"; return 0; }
    python3 - "$LAUNCHER" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
anchor = 'exec "${VLLM_VENV}/bin/python" "${VLLM_VENV}/bin/vllm" serve "${VLLM_MODEL}" \\'
hook = '''# --- experiment hook (scripts/tuning/09-vllm-experiments.sh) -----------------
# Extra argv from VLLM_EXTRA_ARGS in /etc/conf.d/vllm-qwen38. Parsed into an ARRAY so
# JSON values keep their double quotes — the same hazard this launcher exists to avoid.
# Empty by default: with no VLLM_EXTRA_ARGS set, argv is byte-identical to before.
_extra=()
if [ -n "${VLLM_EXTRA_ARGS:-}" ]; then
    eval "_extra=(${VLLM_EXTRA_ARGS})"
    echo "extra args: ${_extra[*]}"
fi

'''
assert anchor in s, "anchor not found"
s = s.replace(anchor, hook + anchor, 1)
s = s.replace('    --trust-remote-code\n', '    --trust-remote-code \\\n    "${_extra[@]}"\n', 1)
open(p, "w").write(s)
print("  hook added")
PY
    bash -n "$LAUNCHER" || { echo "!! launcher syntax broke — restoring"; cp -a "$BAKDIR/start-qwen38.sh.orig" "$LAUNCHER"; exit 3; }
}

set_extra() {
    # MUST be `export`. OpenRC sources conf.d into the INIT SCRIPT's shell; an
    # unexported assignment never reaches the daemon. Verified 2026-08-31: the running
    # vLLM has ZERO VLLM_* vars in /proc/<pid>/environ, so every value in this conf.d
    # has been inert and the launcher's own defaults are what actually run. They happen
    # to be identical, which is why nobody noticed.
    sed -i '/^\(export \)\?VLLM_EXTRA_ARGS=/d' "$CONF"
    [ -n "$1" ] && echo "export VLLM_EXTRA_ARGS=$1" >> "$CONF"
    echo "  VLLM_EXTRA_ARGS=${1:-<empty>}"
}

wait_ready() {
    # $1 = PID before the restart. Without this, a restart that silently did nothing
    # returns "ready after 0s" because the OLD process is still serving — which is
    # exactly what happened on the first `prefix` run.
    local want_new="${1:-}" w=0 now
    printf "  waiting for :%s " "$PORT"
    while [ "$w" -lt "$READY_WAIT" ]; do
        if curl -sf -m 5 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1; then
            now=$(pgrep -f "bin/vllm serve" | head -1)
            if [ -n "$want_new" ] && [ "$now" = "$want_new" ]; then
                printf "!"; sleep 10; w=$((w+10)); continue   # old process, not a restart
            fi
            echo " ready after ${w}s (pid ${now:-?})"; return 0
        fi
        printf "."; sleep 10; w=$((w+10))
    done
    echo " TIMEOUT after ${w}s"; return 1
}

revert() {
    banner "REVERT — restoring original launcher and conf"
    [ -f "$BAKDIR/start-qwen38.sh.orig" ] && cp -a "$BAKDIR/start-qwen38.sh.orig" "$LAUNCHER" && echo "  launcher restored"
    [ -f "$BAKDIR/vllm-qwen38.orig" ]     && cp -a "$BAKDIR/vllm-qwen38.orig"     "$CONF"     && echo "  conf restored"
    _op=$(pgrep -f "bin/vllm serve" | head -1)
    rc-service vllm-qwen38 restart 2>&1 | sed 's/^/    /'
    wait_ready "$_op" && echo "  reverted and serving" || echo "  !! DID NOT COME BACK — check /var/log/qwen38/writer.log"
}
[ "$EXP" = "revert" ] && { revert; exit 0; }

case "$EXP" in
    baseline) EXTRA="" ;;
    prefix)   EXTRA="'--enable-prefix-caching'" ;;
    ngram)    EXTRA="'--speculative-config' '{\"method\":\"ngram\",\"num_speculative_tokens\":4,\"prompt_lookup_min\":2,\"prompt_lookup_max\":4}'" ;;
    *) echo "usage: $0 {baseline|prefix|ngram|revert}"; exit 1 ;;
esac

banner "EXPERIMENT: $EXP — $(date)"
backup_once
[ "$EXP" = baseline ] || add_hook
set_extra "$EXTRA"

echo; echo "--- restarting vLLM (the site is down for this window) ---"
OLDPID=$(pgrep -f "bin/vllm serve" | head -1); echo "  pid before: ${OLDPID:-none}"
rc-service vllm-qwen38 restart 2>&1 | sed 's/^/    /'
if ! wait_ready "$OLDPID"; then
    echo "!! engine did not come back — AUTO-REVERTING"; revert; exit 2
fi

echo; echo "--- live argv assertion (never trust the file you edited) ---"
ps -eo args | grep -F 'bin/vllm serve' | grep -v grep | tr ' ' '\n' \
  | grep -E "enable-prefix-caching|speculative-config|ngram|method" | sed 's/^/    /' \
  || echo "    (none present)"
if [ "$EXP" != baseline ]; then
    _pid=$(pgrep -f "bin/vllm serve" | head -1)
    case "$EXP" in
      prefix) _need="enable-prefix-caching" ;;
      ngram)  _need="speculative-config" ;;
    esac
    if ! tr '\0' '\n' < "/proc/$_pid/cmdline" | grep -q -- "$_need"; then
        echo "    !! '$_need' is NOT in the live argv — the experiment did NOT apply."
        echo "       Reverting rather than reporting a meaningless measurement."
        revert; exit 6
    fi
    echo "    ok: '$_need' confirmed in live argv"
fi

echo; echo "--- engine config as RESOLVED (not as requested) ---"
grep -a "Initializing a V1 LLM engine" /var/log/qwen38/writer.log | tail -1 \
  | grep -oE "enable_prefix_caching=[A-Za-z]+|speculative_config=[^,]*" | sed 's/^/    /'

echo; echo "--- smoke: does it actually generate? ---"
R=$(curl -s -m 120 "http://127.0.0.1:$PORT/v1/completions" -H 'Content-Type: application/json' \
      -d "{\"model\":\"qwen3.8-27b\",\"prompt\":\"Reply with one word: ok\",\"max_tokens\":5,\"temperature\":0}" \
    | python3 -c 'import json,sys; print((json.load(sys.stdin)["choices"][0]["text"] or "").strip()[:20])' 2>/dev/null)
[ -n "$R" ] && echo "    PASS -> \"$R\"" || { echo "    FAIL — auto-reverting"; revert; exit 4; }

echo; echo "--- decode throughput ---"
( cd /opt/vllm-service && ./bench-vllm.sh "$PORT" 3 2>&1 | grep -E "^  run |MEAN" )

echo; echo "--- workload probes (TTFT + repeat-prefix + quoting) ---"
python3 /home/chris/tuning/exp_probe.py 2>&1 | sed 's/^/  /'

echo; echo "--- prefix cache hit rate (last 5 windows) ---"
grep -a "Prefix cache hit rate" /var/log/qwen38/writer.log | tail -5 \
  | grep -oE "Prefix cache hit rate: [0-9.]+%" | sed 's/^/    /'

banner "DONE — $EXP.  revert with: sudo $0 revert    log: $LOG"
