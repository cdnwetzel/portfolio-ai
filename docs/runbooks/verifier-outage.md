# Runbook: Verifier Dark (no verdicts being recorded)

**Signature:** `verdicts.db` gets no new rows while chats complete normally; the weekly
digest reports "no verdicts in N days", or the UI never shows verdict badges.
**Blast radius:** none user-facing (fail-open by design) — but the continuous-improvement
loop is blind. **First seen:** 2026-08-01→05 (4 days silent; DEFECT_LEDGER #5).

## Diagnosis (ordered by likelihood)

1. **Is the proxy even trying?** On the VPS:
   ```bash
   systemctl show api-proxy -p Environment | tr ' ' '\n' | grep VERIFIER_URL
   ```
   Empty → `_fire_verify` no-ops by design. Fix: drop-in
   `/etc/systemd/system/api-proxy.service.d/verifier.conf` with
   `Environment=VERIFIER_URL=http://127.0.0.1:8007`, `daemon-reload`, restart api-proxy.

2. **Does the tunnel actually carry 8007?** On the VPS:
   ```bash
   curl -s -m 10 http://127.0.0.1:8007/health
   ```
   `ss -tlnp | grep 8007` showing LISTEN is NOT sufficient — an empty `VERIFIER_HOST` in
   `/etc/default/portfolio-ai-tunnel` makes the forward listen-but-dead-end. If the curl
   returns nothing, check the env file has `VERIFIER_HOST=<asrock-lan-ip>` (current:
   10.0.1.115), restart `portfolio-ai-tunnel`.

3. **Is the verifier up on the asrock?**
   ```bash
   ssh asrock 'rc-service verifier-service status && curl -s http://10.0.1.115:8007/health'
   ```

4. **Is the judge evicted and the proxy timeout eating cold loads?** The 14B evicts after
   30m idle (`JUDGE_KEEP_ALIVE`); a cold verify costs ~30s but `VERIFIER_TIMEOUT` is 20s —
   the first verify after an idle stretch is sacrificed. This is expected and
   self-healing (the next one is warm). Symptom of this vs a real break: verdicts resume
   on their own.

5. **Is the gate skipping?** `VERIFY_MIN_SCORE=0.002` skips verification on low-relevance
   answers; the Tier 4 router's off-topic deflections never reach the verifier at all.
   Test with a clearly on-topic question before concluding anything is broken.

## Proof of repair

Send any on-topic chat, wait ~30s, then on the asrock:
```bash
sqlite3 ~/verifier/verdicts.db "SELECT ts, faithfulness, latency_s, substr(request_id,1,8)
                                FROM verdicts ORDER BY ts DESC LIMIT 1"
```
A row with a fresh timestamp **and a non-empty request_id** proves the full path
(proxy → tunnel → verifier → DB), not just the service.

## Prevention

- The weekly digest (`scripts/weekly_verifier_digest.sh`, Mondays from the T5810 cron)
  alerts on ≥48h of verdict silence.
- DEPLOYMENT.md "out-of-repo config" section lists the env state every redeploy must
  preserve — both 2026-08 breaks were redeploys dropping invisible config.
