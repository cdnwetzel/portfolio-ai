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

# Refuse to start on top of a previous, unreverted experiment. This replaces a
# `backup_once` that skipped the copy whenever a .orig already existed -- which turned
# those files into a TIME BOMB: the Aug-31 run left .orig copies behind, so any later
# `revert` would have restored the Aug-31 launcher and conf.d over whatever was current,
# silently undoing unrelated fixes and reinstating the stale unexported VLLM_EXTRA_ARGS
# line, while reporting "reverted and serving". Backing up unconditionally is only safe
# if the live state is genuinely a baseline, so assert that instead of assuming it.
assert_clean_baseline() {
    # Read the value the way OpenRC will: source the file. A regex gets this wrong --
    # `VLLM_EXTRA_ARGS=\'\'` is an EMPTY setting, not an active experiment, and a commented
    # line is not a setting at all.
    # Absolute path required: POSIX `.` searches PATH for a name with no slash, so a
    # relative $CONF would silently source nothing and report a clean baseline.
    case "$CONF" in /*) _c="$CONF" ;; *) _c="$PWD/$CONF" ;; esac
    _cur=$(sh -c '. "$1" >/dev/null 2>&1; printf %s "${VLLM_EXTRA_ARGS:-}"' _ "$_c" 2>/dev/null || true)
    if [ -n "$_cur" ]; then
        echo "!! $CONF already carries an active VLLM_EXTRA_ARGS=$_cur"
        grep -nE '^[[:space:]]*(export[[:space:]]+)?VLLM_EXTRA_ARGS=' "$CONF" | sed 's/^/     /'
        echo "   That is a previous experiment that was never reverted. Backing up now would"
        echo "   record an EXPERIMENT as the baseline, and every later revert would restore it."
        echo "   Run:  sudo $0 revert    then try again."
        exit 7
    fi
}

backup_baseline() {
    # Unconditional, with the previous copy rotated rather than discarded.
    for f in "start-qwen38.sh:$LAUNCHER" "vllm-qwen38:$CONF"; do
        _n=${f%%:*}; _src=${f#*:}
        if [ -f "$BAKDIR/${_n}.orig" ] && ! cmp -s "$BAKDIR/${_n}.orig" "$_src"; then
            cp -a "$BAKDIR/${_n}.orig" "$BAKDIR/${_n}.orig.superseded-$(date +%Y%m%d-%H%M%S)"
            echo "  rotated a stale backup of ${_n} (live file had changed since)"
        fi
        cp -a "$_src" "$BAKDIR/${_n}.orig"
    done
    echo "  baseline backed up: $BAKDIR"
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

# Wrap a string in single quotes for safe shell re-parsing, escaping embedded quotes.
shq() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"; }

set_extra() {
    # MUST be `export`. OpenRC sources conf.d into the INIT SCRIPT's shell; an unexported
    # assignment never reaches the daemon. (As of 2026-09-12 the unit exports conf.d itself,
    # so this is belt-and-braces rather than the only mechanism -- but keep it: a conf.d line
    # that works regardless of which unit is installed is strictly safer.)
    #
    # AND IT MUST BE SHELL-QUOTED AS ONE WORD. `echo "export VLLM_EXTRA_ARGS=$1"` worked for
    # the prefix experiment, whose EXTRA is a single quoted word, and produced a conf.d that
    # DOES NOT PARSE for ngram, whose EXTRA is two words:
    #   export VLLM_EXTRA_ARGS='--speculative-config' '{"method":"ngram",...}'
    # bash reads that as exporting TWO names and rejects the JSON as "not a valid identifier",
    # so `rc-service` failed with "error loading .../conf.d/vllm-qwen38" and then "failed to
    # stop" -- which, luckily, meant the old engine kept serving rather than the box being left
    # with no backend. The ngram experiment had therefore never run even once.
    sed -i '/^\(export \)\?VLLM_EXTRA_ARGS=/d' "$CONF"
    [ -n "$1" ] && printf 'export VLLM_EXTRA_ARGS=%s\n' "$(shq "$1")" >> "$CONF"
    echo "  VLLM_EXTRA_ARGS=${1:-<empty>}"
}

assert_conf_parses() {
    # Validate BEFORE restarting. The cost of not doing this was a failed restart that left
    # conf.d unparseable, so every subsequent rc-service call on this unit would also fail.
    # Check what OpenRC will do (source it) and what the launcher will do (eval the array).
    local want="${1:-}"
    if ! sh -c ". '$CONF'" >/dev/null 2>&1; then
        echo "  !! $CONF does not parse -- refusing to restart. Error:"
        sh -c ". '$CONF'" 2>&1 | sed 's/^/       /' | head -3
        echo "     restoring the baseline conf.d"
        cp -a "$BAKDIR/vllm-qwen38.orig" "$CONF"
        exit 8
    fi
    local n
    n=$(bash -c ". '$CONF' >/dev/null 2>&1; eval \"_e=(\${VLLM_EXTRA_ARGS:-})\"; echo \${#_e[@]}" 2>/dev/null)
    echo "  conf.d parses; launcher will see $n extra argv word(s):"
    bash -c ". '$CONF' >/dev/null 2>&1; eval \"_e=(\${VLLM_EXTRA_ARGS:-})\"; for a in \"\${_e[@]}\"; do printf '       [%s]\n' \"\$a\"; done" 2>/dev/null
    if [ -n "$want" ]; then
        bash -c ". '$CONF' >/dev/null 2>&1; eval \"_e=(\${VLLM_EXTRA_ARGS:-})\"; printf '%s\n' \"\${_e[@]}\"" 2>/dev/null \
          | grep -q -- "$want" || {
            echo "  !! expected '$want' among the extra argv and it is not there -- refusing to restart"
            cp -a "$BAKDIR/vllm-qwen38.orig" "$CONF"; exit 9; }
    fi
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
    # Both flags together. They act on different halves of a turn -- prefix caching on
    # prefill, ngram on decode -- so this is the shape a production config takes if each
    # wins its own A/B. Test the SINGLE flags first: a combined arm cannot tell you which
    # half earned the gain, and prefix caching is not yet cleared on the empty-completion
    # question (plans/vllm-flag-experiments-2026-09-12.md).
    both)     EXTRA="'--enable-prefix-caching' '--speculative-config' '{\"method\":\"ngram\",\"num_speculative_tokens\":4,\"prompt_lookup_min\":2,\"prompt_lookup_max\":4}'" ;;
    *) echo "usage: $0 {baseline|prefix|ngram|both|revert}"; exit 1 ;;
esac

banner "EXPERIMENT: $EXP — $(date)"
assert_clean_baseline
backup_baseline
[ "$EXP" = baseline ] || add_hook
set_extra "$EXTRA"

echo; echo "--- conf.d validation (before any restart) ---"
case "$EXP" in
    prefix) assert_conf_parses "enable-prefix-caching" ;;
    ngram)  assert_conf_parses "speculative-config" ;;
    both)   assert_conf_parses "enable-prefix-caching"; assert_conf_parses "speculative-config" ;;
    *)      assert_conf_parses ;;
esac

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
      both)   _need="enable-prefix-caching" ;;   # the other is covered by assert_conf_parses
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
