#!/bin/bash
# Graceful shutdown for the asrock B550 (verifier + reranker node) on UPS battery-low.
# Wired as NUT's SHUTDOWNCMD in upsmon SLAVE mode -- i.e. this runs locally as root on the
# asrock, triggered by upsd on the T5810. Nothing SSHes in as root to run it.
#
# STAGED -- not installed. See README.md, including the open question of whether this box is
# even on the same UPS as the T5810 (if it is on the old 550 VA unit, this trigger is too late).
set -u

LOG=/var/log/ups-shutdown.log
log() { echo "$(date -Iseconds) $*" >> "$LOG"; }

log "UPS battery low - graceful shutdown (asrock)"

# 1. verifier-service first: it writes verdicts.db (SQLite). That is the only state on this
#    box that a hard cut actually corrupts.
if rc-service verifier-service status >/dev/null 2>&1; then
    log "stopping verifier-service"
    rc-service verifier-service stop >> "$LOG" 2>&1
    sleep 2
fi

# 2. ollama holds the 14B judge. No persistent state, but stop it before the DB is gone
#    so nothing is mid-write against a closed service.
if rc-service ollama status >/dev/null 2>&1; then
    log "stopping ollama"
    rc-service ollama stop >> "$LOG" 2>&1
    sleep 2
fi

# 3. rerank-service: cross-encoder, no persistent state.
if rc-service rerank-service status >/dev/null 2>&1; then
    log "stopping rerank-service"
    rc-service rerank-service stop >> "$LOG" 2>&1
fi

# Both of these are FAIL-OPEN in the proxy (reranker degrades to cosine top-5, verifier is
# skipped entirely), so the public site keeps answering while this box is down. That is why
# this node can be shut down early and the T5810 cannot.
log "syncing filesystems"
sync
log "halting"
/sbin/shutdown -h now "UPS battery low"
