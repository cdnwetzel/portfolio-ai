# Runbook: dead-man's-switch monitoring for an endpoint

A repeatable recipe for adding **healthchecks.io** monitoring to any service. Written from the
setup already running for the portfolio AI stack (`scripts/health_aggregate.py`), generalized so
you can drop it on a new endpoint in ~10 minutes.

---

## What a dead-man's switch is (and why it's different)

Ordinary uptime monitoring is **outside-in**: a third party polls your URL and alerts when the
poll fails. It has a blind spot — if your monitor and your service share a failure (the whole box,
the network, the datacenter), the monitor goes silent *with* the service and nobody is paged.

A dead-man's switch inverts the direction. **Your side pings out on a schedule; the alert fires
when the pings stop.** You prove you're alive; silence is the alarm. This catches the case
outside-in polling can't: the monitor itself dying takes the heartbeat with it, which *is* the
signal.

The two are complementary, and the portfolio stack runs both:

| Layer | Direction | Tool | Catches |
|---|---|---|---|
| In-band probes | your monitor → services | ntfy on state change | a specific service going down |
| **Dead-man's switch** | your monitor → healthchecks.io | this runbook | your **monitor/box/network** dying |

healthchecks.io is the free hosted receiver for the heartbeat. You never expose an inbound port;
the pinger only makes outbound HTTPS calls.

---

## The recipe

### 1. Create the check on healthchecks.io

Log in → **Add Check** → name it after the endpoint. Set two numbers:

- **Period** — the expected time between pings. Set it to your ping interval, or a small multiple
  of it to tolerate transient blips without paging. *Example: pinging every 5 min but Period = 15
  min tolerates two missed pings before the clock is considered late.*
- **Grace** — how long *past* the Period a ping may be late before you're alerted.

**Alert fires when:** `now > last_ping + Period + Grace`. With 15 min / 5 min that's ~20 min of
total silence before you're paged. Tighten both for a latency-critical service; loosen them for a
noisy or bursty one. **Rule: Period must be ≥ your ping interval**, or a single on-time run that
lands a few seconds late will false-alarm.

Copy the **ping URL** it gives you — `https://hc-ping.com/<uuid>`. Treat it as a secret (anyone
with it can spoof your heartbeat). Configure where alerts go under **Integrations** (email, ntfy,
Slack, etc.).

### 2. Write the pinger

The pinger does two things: check the thing you care about, and **ping only if it's healthy**.
Pinging unconditionally would defeat the point — you'd report "alive" while the endpoint is broken.

Minimal, stdlib-only (no dependencies), mirroring `ping_healthchecks()` in `health_aggregate.py`:

```python
#!/usr/bin/env python3
"""Heartbeat pinger: check ENDPOINT, ping healthchecks.io only when it's healthy."""
import os, sys, urllib.request

ENDPOINT = os.environ["ENDPOINT_URL"]          # what you're monitoring
HC_URL   = os.environ["HEALTHCHECKS_URL"]      # https://hc-ping.com/<uuid>  (secret)
TIMEOUT  = 10

def healthy() -> bool:
    try:
        with urllib.request.urlopen(ENDPOINT, timeout=TIMEOUT) as r:
            return r.status == 200                # tighten: parse JSON, check a field, etc.
    except Exception:
        return False

def ping(suffix=""):                              # "" = success, "/fail" = failure, "/start" = timing
    try:
        urllib.request.urlopen(HC_URL + suffix, timeout=TIMEOUT).read()
    except Exception as e:
        print(f"healthchecks ping failed: {e}")

if healthy():
    ping()                                        # heartbeat: I checked, it's up
else:
    ping("/fail")                                 # optional: actively signal down for a faster page
    sys.exit(1)
```

Two ways to use the result:
- **Success-only (pure dead-man's switch)** — ping on healthy, stay silent on failure, and let the
  Period+Grace clock catch it. This is what the portfolio monitor does. Simplest; alert latency is
  bounded by Period+Grace.
- **Active fail signal** — also ping `<url>/fail` when unhealthy. healthchecks.io pages
  *immediately* instead of waiting out the grace window. Use when you want a faster page than the
  clock gives, at the cost of the pinger needing to run to send it.

Optional: ping `<url>/start` at the top and `<url>` at the end to record **duration** (healthchecks
graphs it and can alert on a run that takes too long).

### 3. Schedule it

Match the interval to the Period you set. Two options.

**systemd timer** (the portfolio convention — see `cloud/systemd/portfolio-health.timer`):

```ini
# /etc/systemd/system/heartbeat-ENDPOINT.timer
[Unit]
Description=Heartbeat pinger for ENDPOINT

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min       # ping interval — keep ≤ the healthchecks Period
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/heartbeat-ENDPOINT.service
[Unit]
Description=Heartbeat pinger for ENDPOINT
[Service]
Type=oneshot
EnvironmentFile=/etc/default/heartbeat-ENDPOINT     # holds the secret (step 4)
ExecStart=/usr/bin/python3 /opt/heartbeat/ping_ENDPOINT.py
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now heartbeat-ENDPOINT.timer
systemctl list-timers heartbeat-ENDPOINT.timer      # confirm next run
```

**OpenRC / cron** (for the Gentoo boxes), every 5 min:

```
*/5 * * * * ENDPOINT_URL=... HEALTHCHECKS_URL=... /usr/bin/python3 /opt/heartbeat/ping_ENDPOINT.py
```

> Put the pinger on a **different failure domain** than the endpoint where you can. A pinger on the
> same box that dies with the endpoint still works (the switch trips on silence) — but a pinger
> that can independently reach the endpoint also catches "endpoint down, box up," which the pure
> dead-man's switch alone would only catch after Period+Grace.

### 4. Wire the secret (do not commit it)

The ping URL is a credential. Keep it in an env file, not in the repo:

```bash
# /etc/default/heartbeat-ENDPOINT   (chmod 600)
ENDPOINT_URL=https://your-service/health
HEALTHCHECKS_URL=https://hc-ping.com/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

Add `*/heartbeat-*` (or the specific file) to `.gitignore` if it ever lands near the tree. In this
repo the pattern is already established: the aggregator reads `HEALTHCHECKS_URL` from
`/etc/default/portfolio-health`, which is not tracked.

### 5. Test it — prove both edges

A monitor you haven't seen fire is a hope, not a monitor. Verify both transitions:

```bash
# 1. Green path: run the pinger by hand, confirm healthchecks flips to "up".
sudo systemctl start heartbeat-ENDPOINT.service
#    → the check's last-ping updates; dashboard shows a green dot.

# 2. Dead path: stop the pinger and wait out Period+Grace (or curl the /fail URL to force it now).
sudo systemctl stop heartbeat-ENDPOINT.timer
curl -fsS https://hc-ping.com/<uuid>/fail          # forces an immediate down alert
#    → you should receive the alert on your configured channel.

# 3. Re-arm.
sudo systemctl start heartbeat-ENDPOINT.timer
```

If step 2 doesn't page you, fix that *before* trusting the check — a silent dead-man's switch is
the worst kind of instrument, because it reads as "all clear."

---

## Reference: the portfolio AI setup

The live example this runbook is generalized from:

- **Pinger:** `scripts/health_aggregate.py` — probes proxy/vLLM/Qdrant/embed/rerank/verifier, pages
  via ntfy **only on state transitions** (no re-paging a still-broken service), and pings
  `HEALTHCHECKS_URL` on every all-green run (`ping_healthchecks()`).
- **Schedule:** `cloud/systemd/portfolio-health.timer` — every 5 min (`--no-smoke`), plus a daily
  E2E heartbeat run.
- **healthchecks.io config:** Period 15 min, Grace 5 min → alerts after ~20 min of silence.
- **Secret:** `HEALTHCHECKS_URL` in `/etc/default/portfolio-health` (untracked).
- **Signal used:** success-ping only (pure dead-man's switch); ntfy carries the fast in-band
  down/recovered pages.
- **Monitor-of-the-monitor:** `portfolio-health-alert.service` uses systemd `OnFailure=` so a crash
  of the pinger *itself* is caught locally, in addition to healthchecks noticing the silence.

For a new endpoint, the smallest useful version skips the multi-probe aggregator: one health check,
one ping, one timer, steps 1–5 above.
