# VPS systemd drop-ins for `api-proxy.service`

Every `Environment=` the live proxy actually receives comes from here, on the VPS at
`/etc/systemd/system/api-proxy.service.d/`. None of it was tracked in this repo until
2026-09-13, which is how DEFECT_LEDGER #17 stayed invisible: `COMPRESS_URL` was **set and
live** while `DEPLOYMENT.md` said "unset = disabled" and the repo contained no mention of it.

CLAUDE.md already names this failure mode — "out-of-repo config is a known loss vector (the
4-day verifier outage, closed defect #5)". It was named and then repeated.

**These files are a mirror for review, not a deploy target.** `cloud/deploy.sh` does not write
them. Changing the VPS still means editing `/etc/systemd/system/api-proxy.service.d/` and
running `systemctl daemon-reload && systemctl restart api-proxy.service`. Mirror the change
back here in the same commit.

## Verify live state rather than trusting these files

```bash
PID=$(systemctl show -p MainPID --value api-proxy.service)
tr '\0' '\n' < /proc/$PID/environ | grep -E 'COMPRESS|VERIFY|RAG_|MODEL_ID|DISABLE|HYBRID' | sort
```

Note what that command reveals and these files do not: `MODEL_ID`, `DISABLE_THINKING`,
`RAG_TOP_K`, `RAG_MAX_PER_DOC` and `HYBRID_SEARCH` are **not set anywhere on the VPS**. The
proxy runs on its in-code defaults, which happen to match what CLAUDE.md documents. That is the
same shape as the T5810's conf.d problem: a value that looks configured, is not, and only
agrees by luck. Do not "fix" it by adding them without checking the code default first.

## Live contents, 2026-09-13

| file | sets | note |
|---|---|---|
| `deploy-sha.conf` | `DEPLOY_GIT_SHA` | rewritten by `cloud/deploy.sh`; do not hand-edit |
| `headroom.conf.disabled` | **nothing — it is not loaded** | **MUST STAY DISABLED — DEFECT_LEDGER #17.** See the warning below before touching it. |
| `override.conf` | `VERIFIER_GPU` | display string for `/api/system-info` |
| `system-info.conf` | `KB_DOC_COUNT=35`, `KB_CHUNK_COUNT=99` | chunk count is stale and unused — the proxy reads it live from Qdrant (`_live_chunk_count`) |
| `verifier.conf` | `VERIFIER_URL` | enables the out-of-band judge; unset = judge off |
| `verify-gate.conf` | `VERIFY_MIN_SCORE=0.002` | calibrated off-topic gate (`verify_gate.py`) |

### Why the headroom row says "not loaded" — read before renaming anything

systemd loads **only** files matching `*.conf` from a drop-in directory. The suffix is the
entire disabling mechanism. On the VPS the file is:

```
/etc/systemd/system/api-proxy.service.d/headroom.conf.disabled-20260913-042628
```

Verified live 2026-09-14: that filename, and `systemctl show api-proxy -p Environment` carries
**no `COMPRESS_*` at all**.

This row previously read `headroom.conf` / sets `COMPRESS_URL`, under a heading that says
"Live contents". That was wrong in both halves and it was the dangerous kind of wrong: an
operator reconciling the VPS against this mirror would have recreated an **active**
`headroom.conf` and re-enabled the P0 that shredded the generator's evidence for three months.
The tracked copy here is `headroom.conf.disabled` for the same reason — so that a plain
`cp * /etc/systemd/system/api-proxy.service.d/` cannot arm it.

**To re-enable it you would have to rename it to end in `.conf`.** Do not, without reading
DEFECT_LEDGER #17 first: it was measured at ~45% token loss, taking device names ("Ti") and
counts ("two") out of the evidence, and fabricated-GPU answers went 67% -> 0% when it was
switched off.
