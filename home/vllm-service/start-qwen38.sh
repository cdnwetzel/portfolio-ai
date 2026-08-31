#!/bin/bash
# Launcher for the qwen3.8-27b vLLM backend slot on the T5810.
#
# WHY A LAUNCHER AND NOT command_args:
# Two of vLLM's flags take JSON values containing double quotes:
#   --compilation-config {"cudagraph_capture_sizes":[1,2,4,8]}
#   --limit-mm-per-prompt {"image":0,"video":0}
# OpenRC word-splits `command_args` through the shell, which STRIPS those quotes
# and hands vLLM `{cudagraph_capture_sizes:[1,2,4,8]}` — invalid JSON. The failure
# would be at startup, but the cause would look nothing like the symptom. Keeping
# the argv here, correctly quoted, removes that whole class of problem.
#
# This reproduces the configuration recovered from /proc/96627/cmdline on
# 2026-08-30 — the process that had been serving since Aug 26 from a venv that had
# since been deleted out from under it. That command line existed nowhere on disk;
# this file is now its home.
#
# Config comes from /etc/conf.d/vllm-qwen38 (OpenRC exports it before we run).
set -euo pipefail

: "${VLLM_VENV:=/opt/pscode/vllm-serve-env-0.27.1}"
: "${VLLM_MODEL:=/data/models/Qwen3.8-27B-FP8}"
: "${VLLM_SERVED_NAME:=qwen3.8-27b}"
: "${VLLM_HOST:=0.0.0.0}"
: "${VLLM_PORT:=8007}"
: "${VLLM_TP:=2}"
: "${VLLM_UTIL:=0.93}"
: "${VLLM_CTX:=32768}"
: "${VLLM_SEQS:=4}"
: "${VLLM_GDN:=triton}"
: "${VLLM_TOOLPARSER:=qwen3_coder}"
: "${VLLM_REASONING_PARSER:=qwen3}"
: "${VLLM_CUDAGRAPH_SIZES:=[1,2,4,8]}"

# --- refuse to collide with labrouter ------------------------------------
# labrouter owns :8004 and is the STABLE CONTRACT PORT the cwdotcom VPS tunnel
# forwards (FLEET-ENDPOINTS.md §2). The retired /etc/init.d/vllm hardcoded
# --port 8004; had anyone run it, it would have taken the contract port away from
# labrouter and broken the site in a way that looks like a routing failure.
# Backend slots are 8007/8008/8009. This guard makes that mistake unrepeatable.
if [ "${VLLM_PORT}" = "8004" ]; then
    echo "FATAL: VLLM_PORT=8004 is labrouter's contract port. Backend slots are 8007/8008/8009." >&2
    exit 78   # EX_CONFIG
fi

# --- preflight: fail loudly, not mysteriously ----------------------------
[ -x "${VLLM_VENV}/bin/python" ] || { echo "FATAL: no interpreter at ${VLLM_VENV}/bin/python" >&2; exit 78; }
[ -x "${VLLM_VENV}/bin/vllm" ]   || { echo "FATAL: no vllm at ${VLLM_VENV}/bin/vllm" >&2; exit 78; }
[ -d "${VLLM_MODEL}" ]           || { echo "FATAL: model dir missing: ${VLLM_MODEL}" >&2; exit 78; }

# The failure that started all of this: the venv was deleted while vLLM ran, so
# lazily-imported modules vanished mid-flight and only STREAMING broke (it is the
# one path that calls anyio.create_task_group). Import it up front — if the venv
# is incomplete we find out now, at start, not from a user's blank chat bubble.
"${VLLM_VENV}/bin/python" -c 'import vllm, anyio._backends._asyncio' \
    || { echo "FATAL: venv incomplete — 'import vllm, anyio._backends._asyncio' failed" >&2; exit 78; }

# --- runtime env (from /proc/96627/environ of the known-good process) -----
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"
export TORCHINDUCTOR_COMPILE_THREADS="${TORCHINDUCTOR_COMPILE_THREADS:-32}"

# PATH must carry `ninja`. psaios/tools/bl343/serve.sh records the failure mode:
# the sampler's forward_cuda JIT-compiles during profile_run and dies with
# `FileNotFoundError: 'ninja'` when it is absent. An interactive shell has it via
# /usr/bin; an OpenRC service inherits a narrower PATH and would not. Set it
# explicitly — the venv ships its own ninja, and /usr/bin/ninja exists as backup.
# /opt/cuda/bin matches the known-good process's PATH.
export PATH="${VLLM_VENV}/bin:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin:/opt/bin:/opt/cuda/bin${PATH:+:${PATH}}"
command -v ninja >/dev/null 2>&1 || echo "WARN: ninja not on PATH — sampler JIT may fail during profile_run" >&2

# nvcc must use gcc<=14. Gentoo's default is 15, and CUDA's host_config.h hard-
# fails on it: "unsupported GNU version! gcc versions later than 14 are not
# supported". flashinfer JIT-compiles its sampling kernels at engine init, so
# without this the engine dies during startup with
#   FAILED: .../flashinfer/<ver>/86/cached_ops/sampling/csrc_sampling.cuda.o
#   ninja: build stopped: subcommand failed.
#   RuntimeError: Engine core initialization failed.
# and supervise-daemon then crash-loops on it (observed 2026-08-30 during the
# cutover). The long-running process never hit this because its flashinfer cache
# was already built; the rebuilt venv ships a newer flashinfer that must compile.
# Verified: `nvcc -ccbin /usr/bin/g++-14` compiles, plain nvcc does not.
# Preferred over -allow-unsupported-compiler, which builds against a host
# compiler CUDA does not support and can miscompile at runtime.
: "${CUDAHOSTCXX:=/usr/bin/g++-14}"
if [ -x "${CUDAHOSTCXX}" ]; then
    export CUDAHOSTCXX
    export CUDA_NVCC_EXECUTABLE="${CUDA_NVCC_EXECUTABLE:-/opt/cuda/bin/nvcc}"
    export NVCC_PREPEND_FLAGS="${NVCC_PREPEND_FLAGS:+${NVCC_PREPEND_FLAGS} }-ccbin ${CUDAHOSTCXX}"
else
    echo "WARN: CUDAHOSTCXX=${CUDAHOSTCXX} not executable — flashinfer JIT will fail if nvcc sees gcc>14" >&2
fi

# DELIBERATELY NOT SET — read before adding.
# psaios/tools/pscode/bin/start-vllm.sh exports NCCL_P2P_LEVEL=NVL,
# VLLM_WORKER_MULTIPROC_METHOD=spawn and CUDA_VISIBLE_DEVICES=0,1 to satisfy its
# INV-B NVLink-P2P invariant. Those belong to the *pscode-vllm* service (14B +
# LoRA), and the qwen3.8 process that has been serving since Aug 26 has **none of
# them** — its entire environment is 32 vars, none NCCL/CUDA. This config also
# passes --disable-custom-all-reduce, which addresses the same all-reduce concern
# a different way. Since the running configuration is the measured-good one,
# reproducing it exactly beats importing settings from a different service.
# If NVLink P2P enforcement is wanted here, add it as a deliberate, benchmarked
# change — not as a silent copy.

# --- reap orphaned workers from a previous instance ---------------------------
# vLLM's TP workers are SEPARATE processes (VLLM::Worker_TP0/TP1) under an
# EngineCore parent. If the API server dies abruptly — SIGKILL, OOM-killer, crash —
# the workers SURVIVE and keep holding ~19 GB of VRAM each. Nothing reaps them:
# supervise-daemon only tracks the process it spawned.
#
# Observed 2026-08-30: killing the supervised child left both workers orphaned;
# every respawn then found a full card, refused to start, and the service could
# not self-heal. The refusal was correct, but with no reaper it was a deadlock —
# a service that supervises itself into a permanent outage.
#
# Anything matching VLLM:: at this point predates the process we are about to
# exec, so it is by definition an orphan and safe to kill.
for _pid in $(pgrep -f 'VLLM::' 2>/dev/null); do
    _ppid="$(ps -o ppid= -p "${_pid}" 2>/dev/null | tr -d ' ')"
    echo "reaping orphaned vLLM worker ${_pid} (parent ${_ppid:-?}) from a previous instance"
    [ -n "${_ppid}" ] && [ "${_ppid}" != "1" ] && kill -9 "${_ppid}" 2>/dev/null || true
    kill -9 "${_pid}" 2>/dev/null || true
done
pgrep -f 'VLLM::' >/dev/null 2>&1 && sleep 10 || true

# --- wait for VRAM. THIS MUST LIVE HERE, NOT IN THE UNIT'S start_pre. ---------
# supervise-daemon re-execs THIS script directly on respawn; OpenRC's start_pre
# runs only for `rc-service start`. So a VRAM guard in start_pre protects the one
# case that rarely needs it and skips every case that does.
#
# Observed 2026-08-30: killing the child put the unit into a crash loop. A dying
# 29 GB instance does not release VRAM immediately, so each respawn started into a
# full card and died with:
#   ValueError: Free memory on device cuda:0 (0.44/19.57 GiB) on startup is less
#   than desired GPU memory utilization (0.93, ...)
# which freed nothing, so the next respawn hit the same wall. Waiting here breaks
# that cycle: the process simply sleeps until the card is actually available.
: "${VLLM_MIN_FREE_MIB:=19000}"
: "${VLLM_VRAM_WAIT:=300}"
if command -v nvidia-smi >/dev/null 2>&1; then
    _waited=0
    while [ "${_waited}" -lt "${VLLM_VRAM_WAIT}" ]; do
        # tightest card, not the average — TP=2 needs BOTH
        _free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | sort -n | head -1 | tr -d ' ')
        case "${_free}" in ''|*[!0-9]*) _free=0 ;; esac
        [ "${_free}" -ge "${VLLM_MIN_FREE_MIB}" ] && break
        [ "${_waited}" -eq 0 ] && echo "waiting for VRAM: ${_free} MiB free on tightest GPU, need ${VLLM_MIN_FREE_MIB} (previous instance still releasing?)"
        sleep 10
        _waited=$((_waited + 10))
    done
    if [ "${_free:-0}" -lt "${VLLM_MIN_FREE_MIB}" ]; then
        # Exiting is better than starting: vLLM would fail the same check and die
        # anyway, and exiting lets supervise-daemon back off and retry cleanly.
        echo "FATAL: only ${_free} MiB free after ${VLLM_VRAM_WAIT}s — refusing to start into a full card" >&2
        exit 75   # EX_TEMPFAIL
    fi
    echo "VRAM ok: ${_free} MiB free on tightest GPU"
fi

echo "starting vllm: model=${VLLM_MODEL} name=${VLLM_SERVED_NAME} ${VLLM_HOST}:${VLLM_PORT} tp=${VLLM_TP} util=${VLLM_UTIL} ctx=${VLLM_CTX}"

exec "${VLLM_VENV}/bin/python" "${VLLM_VENV}/bin/vllm" serve "${VLLM_MODEL}" \
    --served-model-name "${VLLM_SERVED_NAME}" \
    --host "${VLLM_HOST}" \
    --port "${VLLM_PORT}" \
    --tensor-parallel-size "${VLLM_TP}" \
    --gpu-memory-utilization "${VLLM_UTIL}" \
    --max-model-len "${VLLM_CTX}" \
    --max-num-seqs "${VLLM_SEQS}" \
    --gdn-prefill-backend "${VLLM_GDN}" \
    --reasoning-parser "${VLLM_REASONING_PARSER}" \
    --enable-auto-tool-choice \
    --tool-call-parser "${VLLM_TOOLPARSER}" \
    --disable-custom-all-reduce \
    --compilation-config "{\"cudagraph_capture_sizes\":${VLLM_CUDAGRAPH_SIZES}}" \
    --limit-mm-per-prompt '{"image":0,"video":0}' \
    --trust-remote-code
