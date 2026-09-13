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
SIZES=""            # per-mode cudagraph capture sizes; empty = leave conf.d alone
SPEC_K=""           # num_speculative_tokens, for the divisibility check
export SPEC_K
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

set_sizes() {
    # The launcher interpolates VLLM_CUDAGRAPH_SIZES into its own --compilation-config, so
    # this is the supported way to change capture sizes without a second, conflicting
    # --compilation-config in VLLM_EXTRA_ARGS.
    [ -z "${1:-}" ] && return 0
    sed -i -E "s|^([[:space:]]*)VLLM_CUDAGRAPH_SIZES=.*|\\1VLLM_CUDAGRAPH_SIZES=$1|" "$CONF"
    echo "  VLLM_CUDAGRAPH_SIZES=$1"
    grep -nE '^[[:space:]]*VLLM_CUDAGRAPH_SIZES=' "$CONF" | sed 's/^/     /'
}

assert_captured() {
    # vLLM does NOT log each captured size; it logs one "Graph capturing finished" line.
    # It also does not silently drop a size on OOM -- gpu_model_runner.py:6303 re-raises, so a
    # failed capture crashes startup and wait_ready + auto-revert catch it. What CAN happen
    # silently is vLLM rewriting or clamping the requested list, so assert the RESOLVED value.
    local want="${1:-}"
    [ -z "$want" ] && return 0
    local got
    got=$(grep -a "Initializing a V1 LLM engine" /var/log/qwen38/writer.log | tail -1 \
          | grep -oE "'cudagraph_capture_sizes': \[[^]]*\]" | grep -oE '\[[^]]*\]' | tr -d ' ')
    echo "  requested capture sizes: $want"
    echo "  resolved  capture sizes: ${got:-<none found>}"
    if [ "$got" != "$want" ]; then
        echo "  !! vLLM did not use the requested capture sizes. Every spec-decode number from"
        echo "     this run would be measuring the wrong config. Reverting."
        revert; exit 10
    fi
    grep -a "Graph capturing finished" /var/log/qwen38/writer.log | tail -1 \
      | sed 's/.*\] /     /' || echo "     !! no 'Graph capturing finished' line — capture may not have run"
    echo "  uniform-decode divisibility check:"
    python3 - "$want" <<'PY'
import sys, re
import os
sizes=sorted(int(x) for x in re.findall(r'\d+', sys.argv[1]))
k=os.environ.get('SPEC_K','')
if not k: print("     (no spec tokens; N/A)"); raise SystemExit
q=1+int(k); seqs=4
# Uniform decode lands ONLY on multiples of q (num_seqs * query_len). Each must be captured
# EXACTLY: if it is not, _bs_to_padded_graph_size pads it UP to a larger size and then
# `padded % q != 0` takes the else-branch -> PIECEWISE. Extra non-multiples are harmless.
need=[n*q for n in range(1, seqs+1)]
missing=[n for n in need if n not in sizes]
print(f"     query_len=1+{k}={q}; reachable decode widths {need}")
print(f"     captured exactly: {[n for n in need if n in sizes]}; missing: {missing if missing else 'none'}")
print("     -> FULL cudagraphs for uniform decode at every concurrency" if not missing
      else "     -> MISSING widths will run PIECEWISE (cudagraph_dispatcher.py:143-148)")
PY
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

    # --- speculative decoding WITH the capture sizes it actually needs ----------
    # Why SIZES changes per mode, and why the numbers are not arbitrary:
    # cudagraph_dispatcher.py:37 sets `uniform_decode_query_len = 1 + num_speculative_tokens`,
    # and :143-148 will only use a FULL cudagraph when
    #     num_tokens_padded % uniform_decode_query_len == 0
    # otherwise it falls to the `else` branch, sets uniform_decode=False, and decode runs
    # PIECEWISE. That is what happened on 2026-09-13: k=4 gives query_len 5, a 5-token step
    # padded up to 8, and 8 % 5 != 0 -- so the engine reported FULL_AND_PIECEWISE while decode
    # never used FULL. Acceptance was fine (2.27 tokens/step, 31.7% draft acceptance); the
    # -9.2% was per-step cost, not yield.
    # So every capture size must be an exact MULTIPLE of (1+k), up to max_num_seqs*(1+k) so
    # concurrent batches are covered too (num_tokens > max_size falls back to real eager).
    mtp)      EXTRA="'--speculative-config' '{\"method\":\"mtp\",\"num_speculative_tokens\":3}'"
              SIZES="[1,2,4,8,12,16]"; SPEC_K=3 ;;        # query_len 4 -> multiples of 4, to 4*4=16
    ngram-g)  EXTRA="'--speculative-config' '{\"method\":\"ngram\",\"num_speculative_tokens\":4,\"prompt_lookup_min\":2,\"prompt_lookup_max\":4}'"
              SIZES="[1,2,4,5,8,10,15,20]"; SPEC_K=4 ;;   # query_len 5 -> multiples of 5, to 4*5=20
    ngram-g2) EXTRA="'--speculative-config' '{\"method\":\"ngram\",\"num_speculative_tokens\":2,\"prompt_lookup_min\":2,\"prompt_lookup_max\":4}'"
              SIZES="[1,2,3,4,6,8,9,12]"; SPEC_K=2 ;;     # query_len 3 -> multiples of 3, to 4*3=12

    # ngram_gpu is a DISTINCT method (NgramGPUTypes) that is EXEMPT from the async-scheduling
    # disable (config/vllm.py:1107-1118), unlike plain "ngram". Same prompt_lookup validation
    # path (speculative.py:748), different proposer implementation (ngram_proposer_gpu.py).
    # prompt_lookup 2/4 is pinned DELIBERATELY: vLLM's own default when unset is 5/5
    # (speculative.py:752-753), and inheriting that would make this a different experiment
    # rather than an async-scheduling isolation.
    # Pre-registered: acceptance within +/-0.2 of 2.22 => clean scheduling isolation; outside
    # that, the row also measures proposer differences and is confounded.
    # MTP k=2. Pre-check (speculative.py:703-712): method="mtp" with no `model` key
    # auto-resolves to the TARGET checkpoint ("use the draft model from the same model") and
    # inherits its quantization, so mtp.safetensors is discovered without a path key.
    # k=2 exists because verify cost is hypothesised to scale with k: 48 of 64 layers are GDN
    # recurrences that process draft tokens SEQUENTIALLY, so fewer drafts = less sequential
    # work on a step whose weight-read cost is fixed. If ngram-g2 confirms that scaling, this
    # is the likely MTP optimum, not k=3.
    mtp2)     EXTRA="'--speculative-config' '{\"method\":\"mtp\",\"num_speculative_tokens\":2}'"
              SIZES="[1,2,3,4,6,8,9,12]"; SPEC_K=2 ;;   # query_len 3 -> multiples of 3, to 4*3=12

    ngram-gpu) EXTRA="'--speculative-config' '{\"method\":\"ngram_gpu\",\"num_speculative_tokens\":4,\"prompt_lookup_min\":2,\"prompt_lookup_max\":4}'"
              SIZES="[1,2,4,5,8,10,15,20]"; SPEC_K=4 ;;

    *) echo "usage: $0 {baseline|prefix|ngram|both|mtp|mtp2|ngram-g|ngram-g2|ngram-gpu|revert}"; exit 1 ;;
esac

banner "EXPERIMENT: $EXP — $(date)"

# --- manifest: what this row IS, printed every run so a result can never be orphaned ------
# The harness SHA is part of the row: commit before the first run, not after.
echo "--- manifest ---"
printf '    harness SHA   : %s\n' "$(git -C /home/chris/ai/cwdotcom log -1 --format=%h -- scripts/tuning/09-vllm-experiments.sh 2>/dev/null || echo unknown)"
printf '    repo dirty    : %s\n' "$(git -C /home/chris/ai/cwdotcom status --porcelain -- scripts/tuning/09-vllm-experiments.sh 2>/dev/null | grep -q . && echo YES-UNCOMMITTED || echo no)"
printf '    vllm version  : %s\n' "$(grep -aoE 'V1 LLM engine \(v[0-9.]+\)' /var/log/qwen38/writer.log | tail -1)"
printf '    model         : %s\n' "${VLLM_MODEL:-/data/models/Qwen3.8-27B-FP8} (fp8 e4m3 weight-only, Marlin on sm_86; compute bf16)"
printf '    mode          : %s   SPEC_K=%s   SIZES=%s\n' "$EXP" "${SPEC_K:--}" "${SIZES:-<conf.d default>}"
echo "    PINNED FLAGS FROM THE PREVIOUS BOOT -- these are pre-restart reads, NOT this row's"
echo "    applied config. This row's real config prints after the restart under 'engine config"
echo "    as RESOLVED'. (CLAUDE.md: losing any of the three is SILENT and costs ~4x.)"
printf '      1. CUDA graphs ON      : %s\n' "$(grep -aoE 'enforce_eager=[A-Za-z]+' /var/log/qwen38/writer.log | tail -1)"
printf '      2. custom all-reduce   : %s\n' "$(grep -aoE 'disable_custom_all_reduce=[A-Za-z]+' /var/log/qwen38/writer.log | tail -1)"
printf '      3. capture sizes       : %s  <-- PREVIOUS boot; THIS ROW APPLIES: %s\n' "$(grep -a "Initializing a V1 LLM engine" /var/log/qwen38/writer.log | tail -1 | grep -oE "'cudagraph_capture_sizes': \[[^]]*\]")" "${SIZES:-<unchanged>}"
echo "    resolved BACKENDS (distinct subsystems — do not conflate the FlashInfer ones):"
printf '      attention backend    : %s\n' "$(grep -aoE 'Using [A-Z_]+ attention backend' /var/log/qwen38/writer.log | tail -1)"
printf '      flash-attn version   : %s\n' "$(grep -aoE 'Using FlashAttention version [0-9]+' /var/log/qwen38/writer.log | tail -1)"
# NOTE: match "Using [...]" — the rest of that line lists POTENTIAL backends, which is not
# what was selected. (An earlier greedy `sed 's/.*] /'` ate the "Using [...]" prefix and
# reported nothing.) This is the ALL-REDUCE FlashInfer, a different subsystem from the
# FlashInfer ATTENTION backend printed above; never conflate them in a row.
printf '      all-reduce backend   : %s\n' "$(grep -a 'all-reduce backends' /var/log/qwen38/writer.log | tail -1 | grep -oE "Using \[[^]]*\]")"
printf '      AR potential (unused): %s\n' "$(grep -a 'all-reduce backends' /var/log/qwen38/writer.log | tail -1 | grep -oE "potential backends: \[[^]]*\]")"
printf '      linear/quant kernel  : %s\n' "$(grep -aoE 'Selected [A-Za-z0-9]+ for [A-Za-z0-9]+' /var/log/qwen38/writer.log | tail -1)"

assert_clean_baseline
backup_baseline
[ "$EXP" = baseline ] || add_hook
set_extra "$EXTRA"
set_sizes "$SIZES"

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
    # Derive the needle FROM $EXTRA, not a second case on $EXP. The original was a parallel
    # switch needing an update for every new mode -- it did not get one, so mtp/ngram-g/ngram-g2
    # left _need unset and `set -u` killed the script AFTER a successful 365s restart, with no
    # measurement taken and no revert performed. One source of truth now, and fail-closed.
    case "$EXTRA" in
      *speculative-config*)    _need="speculative-config" ;;
      *enable-prefix-caching*) _need="enable-prefix-caching" ;;
      *)                       _need="" ;;
    esac
    if [ -z "$_need" ]; then
        echo "    !! mode '$EXP' sets EXTRA with no recognised flag to assert. Refusing to report"
        echo "       a measurement that cannot be attributed to a config. Reverting."
        revert; exit 11
    fi
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

echo; echo "--- cudagraph capture: requested vs RESOLVED ---"
assert_captured "$SIZES"

echo; echo "--- silent downgrades vLLM warns about (do not let these hide a result) ---"
grep -aE "Async scheduling not supported|max_num_scheduled_tokens is set to|won.t work with speculative" \
  /var/log/qwen38/writer.log | tail -4 | sed 's/.*\] /    /' || echo "    (none)"

echo; echo "--- KV cache dtype as RESOLVED (fp8-KV on FA2/Ampere can silently fall back) ---"
grep -aoE "kv_cache_dtype=[a-z0-9_]+" /var/log/qwen38/writer.log | tail -1 | sed 's/^/    /'
echo "    (a fallback makes the row INVALID, not zero-gain — different conclusions)"

echo; echo "--- KV budget under this config (capacity, not a footnote) ---"
grep -aE "GPU KV cache size|Maximum concurrency|Available KV cache memory" \
  /var/log/qwen38/writer.log | tail -3 | sed 's/.*\] /    /'

echo; echo "--- smoke: does it actually generate? ---"
R=$(curl -s -m 120 "http://127.0.0.1:$PORT/v1/completions" -H 'Content-Type: application/json' \
      -d "{\"model\":\"qwen3.8-27b\",\"prompt\":\"Reply with one word: ok\",\"max_tokens\":5,\"temperature\":0}" \
    | python3 -c 'import json,sys; print((json.load(sys.stdin)["choices"][0]["text"] or "").strip()[:20])' 2>/dev/null)
[ -n "$R" ] && echo "    PASS -> \"$R\"" || { echo "    FAIL — auto-reverting"; revert; exit 4; }

echo; echo "--- decode throughput (CONTENTION-GATED) ---"
# bench-vllm.sh measures SINGLE-STREAM decode; vLLM's continuous batching means a concurrent
# request shares the step rather than queueing, so the bench collapses while aggregate rises.
# Caught live 2026-09-13 (running=1->2->3, bench read 33.4->23.1->20.0). bench_quiet.sh
# invalidates any window where peak Running:N > 1.
"$(dirname "$0")/bench_quiet.sh" 3 || echo "    ^^ row's decode number is INVALID — re-run quiet"

echo; echo "--- workload probes (TTFT + repeat-prefix + quoting) ---"
python3 /home/chris/tuning/exp_probe.py 2>&1 | sed 's/^/  /'

if [ -n "$SPEC_K" ]; then
echo; echo "--- speculative acceptance (the yield side; the probes above are the cost side) ---"
python3 - <<'PY'
import re
rows=[]
for l in open('/var/log/qwen38/writer.log', errors='ignore'):
    if 'SpecDecoding metrics' in l:
        try:
            rows.append((int(re.search(r'Accepted: (\d+) tokens',l).group(1)),
                         int(re.search(r'Drafted: (\d+) tokens',l).group(1)),
                         [float(x) for x in re.search(r'Per-position acceptance rate: ([\d., ]+?), Avg',l).group(1).split(', ')]))
        except Exception: pass
rows = rows[-12:]                      # this run's windows
if not rows:
    print("    !! NO SpecDecoding metrics logged — spec decode may not have engaged at all")
else:
    A=sum(r[0] for r in rows); D=sum(r[1] for r in rows)
    k=len(rows[-1][2]); steps=D/k if k else 0
    print(f"    windows={len(rows)}  accepted={A}  drafted={D}  draft acceptance={100*A/D:.1f}%")
    print(f"    MEAN ACCEPTANCE LENGTH = {1+A/steps:.2f} tokens/step   (1.0 = spec decode doing nothing)")
    for i in range(k):
        v=[r[2][i] for r in rows if len(r[2])>i]
        print(f"      pos {i+1}: {sum(v)/len(v):.3f}")
PY
fi

echo; echo "--- OUTPUT HASH (golden ledger; temp 0 + ignore_eos, same prompt every row) ---"
# Scope of the invariant: SAME ENGINE BUILD + SAME BENCH PROTOCOL, idle single-stream.
# NOT a claim that vLLM is deterministic in general -- under load, batch composition and
# reduction order move, and a hash check there would cry wolf.
_R=$(curl -s -m 180 "http://127.0.0.1:$PORT/v1/completions" -H 'Content-Type: application/json' \
  -d '{"model":"qwen3.8-27b","prompt":"Write a Python function that reverses a singly linked list in place.","max_tokens":256,"temperature":0,"ignore_eos":true}')
printf '%s' "$_R" | python3 -c '
import hashlib, json, sys
d=json.load(sys.stdin); t=d["choices"][0]["text"]
print(f"    tokens: {d[\"usage\"][\"completion_tokens\"]}")
print(f"    sha256: {hashlib.sha256(t.encode()).hexdigest()}")
' 2>/dev/null || echo "    (hash probe failed)"

echo; echo "--- ms/step (acceptance-INDEPENDENT: the pure per-step cost) ---"
echo "    steps/s = tok/s / mean_acceptance_length ;  ms/step = 1000 / steps/s"
echo "    reference: baseline 33.8 tok/s @ accept 1.00 = 29.6 ms/step"
echo "               ngram    30.7 @ 2.27 = 73.9 ms/step (2.50x)"
echo "               ngram-g  31.0 @ 2.22 = 71.6 ms/step (2.42x)"
echo "    break-even acceptance at 2.42x per-step cost = 2.42 tokens/step"
echo "    -> compute this row's ms/step from the decode and acceptance numbers above."

echo; echo "--- RESULTS TABLE (decode AND ttft: 0.29 Mamba/GDN caching moves ttft, not decode) ---"
python3 - <<'PY'
import re, subprocess
bench = subprocess.run(['bash','-c',
    "grep -E '^  run ' /tmp/.bench-$$ 2>/dev/null || true"], capture_output=True, text=True).stdout
print("    decode (256-tok bench, temp 0, ignore_eos)  -> see '--- decode throughput ---' above")
print("    TTFT reference points, same probes, this box:")
print("      baseline cold / repeated-prefix : 1386-1325 ms / 1328-1336 ms   (no prefix caching)")
print("      prefix caching on               : ~465 ms cold-2 / ~450 ms repeated / 480 ms median (probe E n=20)")
print("    -> quote TTFT from probes A/B/E above for THIS row; decode alone will miss a")
print("       Mamba/GDN prefix-caching win, which lands on prefill.")
PY

echo; echo "--- prefix cache hit rate (last 5 windows) ---"
grep -a "Prefix cache hit rate" /var/log/qwen38/writer.log | tail -5 \
  | grep -oE "Prefix cache hit rate: [0-9.]+%" | sed 's/^/    /'

banner "DONE — $EXP.  revert with: sudo $0 revert    log: $LOG"
