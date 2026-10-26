#!/bin/bash
# Graceful shutdown for the T5810 on UPS battery-low.
# Wired as NUT's SHUTDOWNCMD. See README.md in this directory for why the ORDER matters:
# a plain `halt` orphans vLLM's TP workers and can leave the Qdrant collection half-written.
#
# STAGED — not installed. Blocked on the UPS USB data cable being plugged in.
set -u

LOG=/var/log/ups-shutdown.log
log() { echo "$(date -Iseconds) $*" >> "$LOG"; }

log "UPS battery low - beginning graceful shutdown"

# 1. vLLM first: stop it as a SERVICE so the unit's orphan reaper runs. Killing the API
#    server alone leaves TP workers holding ~19 GB VRAM each.
if rc-service vllm-qwen38 status >/dev/null 2>&1; then
    log "stopping vllm-qwen38"
    rc-service vllm-qwen38 stop >> "$LOG" 2>&1
    # Do not block forever on a wedged unload; the battery is finite.
    for _ in $(seq 1 30); do
        pgrep -f '[V]LLM::EngineCore' >/dev/null 2>&1 || break
        sleep 1
    done
    pgrep -f '[V]LLM::EngineCore' >/dev/null 2>&1 \
        && log "WARN: vLLM workers still present after 30s, continuing anyway"
fi

# 2. Qdrant next: it holds the entire retrieval index open.
if rc-service qdrant status >/dev/null 2>&1; then
    log "stopping qdrant"
    rc-service qdrant stop >> "$LOG" 2>&1
    sleep 3
fi

# 3. Flush and halt.
log "syncing filesystems"
sync
log "halting"
/sbin/shutdown -h now "UPS battery low"
