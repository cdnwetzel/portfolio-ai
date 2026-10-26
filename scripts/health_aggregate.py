#!/usr/bin/env python3
"""
Deep cross-node health aggregator for the portfolio RAG chat. Runs on the VPS.

WHY THIS EXISTS — the 2026-06-14 outage: Qdrant crash-looped and latched OFF, so every
query answered "I don't have that documented in my knowledge base." Nothing detected it or
paged a human. Per-service `/health` handlers all return a trivial {"status":"ok"} and miss
exactly this class of failure (Qdrant *up* but serving 0 points; the E2E answer degraded).

This aggregator probes the WHOLE chain the VPS can see through the SSH tunnel — proxy, vLLM,
Qdrant (incl. points_count), embed, rerank, verifier — plus an optional real end-to-end WS
query, maps each signal to a severity, and pages the owner via ntfy ONLY on state transitions
(no re-paging a still-broken service). On every green run it pings a healthchecks.io URL; that
external dead-man's switch is what alerts you if the VPS/monitor itself dies (it stops pinging).

Design choices (see plans/zany-rolling-yao.md):
  - Monitor + ALERT ONLY. No auto-restart of stateful services (blind respawn hid the outage).
  - stdlib-only HTTP probes so the modest VPS needs no new deps. The E2E smoke reuses
    scripts/selftest.py + run_diagnostic_battery.ask and runs ONLY if `websockets` is importable;
    otherwise it is skipped.
  - The E2E smoke is THROTTLED to SMOKE_INTERVAL_SEC (default 30 min) while the cheap
    probes run every 5 min, because it drives real GPU generation and writes verifier
    verdicts. On throttled cycles it reports its LAST severity, never INFO — see
    probe_smoke() for why that distinction prevents a false "recovered" page.

  *** The E2E smoke is the only check that exercises GENERATION, and it must stay on. ***
  On 2026-08-29 the site returned an empty answer to every question for an unknown period
  and this monitor stayed green throughout: the deployed unit ran with `--no-smoke`, and
  every other probe passes in that failure (the proxy is alive, /v1/models lists a model,
  Qdrant has points, embed answers). vLLM was serving from a deleted venv and only the
  streaming path was broken. Nothing short of a real end-to-end query can see that.

Env:
  NTFY_URL           e.g. https://ntfy.sh/<private-topic>  (unset = print alerts only, dry run)
  HEALTHCHECKS_URL   dead-man's-switch ping URL, pinged on every all-green run (optional)
  STATE_FILE         default /var/lib/portfolio-health/state.json
  SMOKE_WS_URL       default ws://127.0.0.1:8000/ws/chat  (internal path; canary covers public)
  PROXY_URL VLLM_URL QDRANT_URL EMBED_URL RERANK_URL VERIFIER_URL  (127.0.0.1 defaults)

Usage:
  python3 scripts/health_aggregate.py            # one probe cycle; page on transitions
  python3 scripts/health_aggregate.py --heartbeat  # also send a daily "all green" summary
  python3 scripts/health_aggregate.py --no-smoke   # skip the E2E query (probes only)

Exit code 0 = no CRITICAL; 1 = at least one CRITICAL service.
"""
import argparse
import json
import os
import socket
import sys
import time
import urllib.request
import urllib.error

# --- severity ---------------------------------------------------------------
OK, DEGRADED, CRITICAL, INFO = "ok", "degraded", "critical", "info"

PROXY_URL    = os.environ.get("PROXY_URL",    "http://127.0.0.1:8000")
VLLM_URL     = os.environ.get("VLLM_URL",     "http://127.0.0.1:8004")
QDRANT_URL   = os.environ.get("QDRANT_URL",   "http://127.0.0.1:6333")
EMBED_URL    = os.environ.get("EMBED_URL",    "http://127.0.0.1:8005")
# 8016, not 8006: the reranker moved to the asrock (Tier 3) and the VPS tunnel
# forwards :8016 -> asrock:8006. api-proxy.py already defaults to 8016. This was
# still pointing at 8006 — a port nothing has listened on since the move — so the
# monitor reported the reranker degraded regardless of its real state, and would
# not have noticed the genuine 2026-08-29 outage of it.
RERANK_URL   = os.environ.get("RERANK_URL",   "http://127.0.0.1:8016")
VERIFIER_URL = os.environ.get("VERIFIER_URL", "http://127.0.0.1:8007")

NTFY_URL         = os.environ.get("NTFY_URL", "").rstrip("/")
# Separate topic for pages that demand action (DOWN / recovered). The routine daily
# heartbeat stays on NTFY_URL.
#
# WHY: on 2026-08-26 the monitor correctly detected a total outage and paged
# "[urgent] Portfolio AI DOWN" on Aug 27 AND Aug 28. Nothing happened. Detection was
# never the problem — the urgent page arrived on the same topic as a daily "all
# services green" heartbeat, and a channel that pings you every day teaches you to
# ignore it. This topic must stay SILENT unless something is actually wrong, so that
# any notification on it is worth opening.
#
# Falls back to NTFY_URL when unset, so an un-migrated deployment behaves as before.
NTFY_CRITICAL_URL = os.environ.get("NTFY_CRITICAL_URL", "").rstrip("/") or NTFY_URL
HEALTHCHECKS_URL = os.environ.get("HEALTHCHECKS_URL", "").rstrip("/")
STATE_FILE       = os.environ.get("STATE_FILE", "/var/lib/portfolio-health/state.json")
SMOKE_WS_URL     = os.environ.get("SMOKE_WS_URL", "ws://127.0.0.1:8000/ws/chat")
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "documents")

# How often the expensive end-to-end probe may actually run, in seconds. The probe
# timer fires every 5 min for the cheap checks; generation is far too costly to
# drive that often. 0 disables throttling (every cycle runs it).
SMOKE_INTERVAL_SEC = int(os.environ.get("SMOKE_INTERVAL_SEC", "1800"))

HTTP_TIMEOUT = float(os.environ.get("HEALTH_HTTP_TIMEOUT", "8.0"))


def _get(url, timeout=HTTP_TIMEOUT):
    """GET a URL; return (status_code, body_text). Raises on connection failure."""
    req = urllib.request.Request(url, headers={"User-Agent": "portfolio-health/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


# --- per-service probes: each returns (severity, detail) --------------------
# `down_severity` is what a hard failure (refused/timeout/5xx) maps to.

def probe_http_ok(name, url, path, down_severity):
    try:
        code, _ = _get(url + path)
        if code == 200:
            return OK, f"{name} 200"
        return down_severity, f"{name} HTTP {code}"
    except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
        return down_severity, f"{name} unreachable: {getattr(e, 'reason', e)}"


def probe_vllm():
    # vLLM up AND actually serving a model (a bare TCP accept isn't enough).
    try:
        code, body = _get(VLLM_URL + "/v1/models")
        if code == 200 and '"id"' in body:
            return OK, "vLLM serving a model"
        return CRITICAL, f"vLLM /v1/models HTTP {code} / no model listed"
    except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
        return CRITICAL, f"vLLM unreachable: {getattr(e, 'reason', e)}"


def probe_qdrant():
    # The outage signature: Qdrant *up* but the collection missing or empty. A trivial
    # /health would say "ok" here; points_count is the signal that actually matters.
    try:
        code, body = _get(f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}")
        if code != 200:
            return CRITICAL, f"Qdrant collection '{QDRANT_COLLECTION}' HTTP {code}"
        data = json.loads(body).get("result", {})
        status = data.get("status")
        points = data.get("points_count")
        if points in (None, 0):
            return CRITICAL, f"Qdrant '{QDRANT_COLLECTION}' has points_count={points} (empty → all queries refuse)"
        if status != "green":
            return DEGRADED, f"Qdrant '{QDRANT_COLLECTION}' points={points} but status={status}"
        return OK, f"Qdrant green, points={points}"
    except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
        return CRITICAL, f"Qdrant unreachable: {getattr(e, 'reason', e)}"
    except (ValueError, KeyError) as e:
        return CRITICAL, f"Qdrant bad response: {e}"


_smoke_ran_at = None   # set when a real smoke run happens; persisted by main()


def probe_smoke():
    """End-to-end WS query — the only check that exercises generation.

    THROTTLED, because it is the one expensive probe: it drives real GPU
    generation and (via the proxy) writes verifier verdicts. At the 5-minute
    cadence of the probe timer it would burn GPU continuously and skew the verdict
    corpus, so it runs at most once per SMOKE_INTERVAL_SEC.

    On a throttled cycle it returns the PREVIOUS severity, not INFO. That matters:
    main() pages on severity transitions, so returning INFO after a CRITICAL smoke
    would read as a recovery and fire a false "recovered" alert while the site was
    still down. Carrying the last verdict forward keeps the state machine honest.
    """
    global _smoke_ran_at
    st = load_state()
    last = st.get("last_smoke_ts", 0)
    now = time.time()
    # A last_smoke_ts in the FUTURE (clock skew, a corrupted or hand-edited state
    # file) would make `now - last` negative forever and silently disable the E2E
    # probe — the one check that catches a generation-layer outage. Treat any
    # future timestamp as "never ran" and run now. Found 2026-08-31 when a seeded
    # test state produced "next E2E in 8211820844s".
    if last > now:
        last = 0
    if SMOKE_INTERVAL_SEC > 0 and last and (now - last) < SMOKE_INTERVAL_SEC:
        prev_sev = st.get("severities", {}).get("e2e_smoke", OK)
        prev_detail = st.get("details", {}).get("e2e_smoke", "no prior E2E result")
        # Strip any suffix a previous throttled cycle added, or each cycle appends
        # another and the detail grows without bound:
        #   "... [cached, next E2E in 1497s] [cached, next E2E in 1194s] [cached...]"
        prev_detail = prev_detail.split(" [cached,")[0]
        wait = int(SMOKE_INTERVAL_SEC - (now - last))
        return prev_sev, f"{prev_detail} [cached, next E2E in {wait}s]"

    try:
        import asyncio
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from selftest import run_live, SMOKE  # reuses ask() + invariants
    except ImportError as e:
        return INFO, f"E2E smoke skipped (no websockets client: {e})"
    _smoke_ran_at = now
    try:
        rows = asyncio.run(run_live(SMOKE_WS_URL, SMOKE))
    except Exception as e:  # noqa: BLE001 — a broken smoke run must not crash the monitor
        return CRITICAL, f"E2E smoke transport error: {e}"
    fails = [r for r in rows if not r["ok"]]
    grounded_fail = [r for r in fails if r["kind"] == "grounded"]
    if grounded_fail:
        return CRITICAL, f"E2E smoke: {len(grounded_fail)} grounded Q(s) returned fallback (outage signature)"
    if fails:
        return DEGRADED, f"E2E smoke: {len(fails)} non-grounded check(s) failed"
    return OK, f"E2E smoke: {len(rows)}/{len(rows)} passed"


def build_checks(run_smoke):
    checks = [
        ("proxy",    lambda: probe_http_ok("proxy", PROXY_URL, "/health", CRITICAL)),
        ("vllm",     probe_vllm),
        ("qdrant",   probe_qdrant),
        ("embed",    lambda: probe_http_ok("embed", EMBED_URL, "/health", CRITICAL)),
        ("rerank",   lambda: probe_http_ok("rerank", RERANK_URL, "/health", DEGRADED)),
        ("verifier", lambda: probe_http_ok("verifier", VERIFIER_URL, "/health", INFO)),
    ]
    if run_smoke:
        checks.append(("e2e_smoke", probe_smoke))
    return checks


# --- alerting ---------------------------------------------------------------
def ntfy(title, message, priority="default", tags="", url=None):
    """Post to ntfy. `url` defaults to the routine topic; pass NTFY_CRITICAL_URL for
    anything that should wake someone up."""
    target = url if url is not None else NTFY_URL
    line = f"[{priority}] {title}: {message}"
    if not target:
        print(f"  (dry, no ntfy URL) {line}")
        return
    # HTTP headers are latin-1, not UTF-8 — emoji in Title/Tags raise UnicodeEncodeError.
    # ntfy renders the *named* Tags (e.g. "rotating_light") as emoji, so keep the Title
    # ASCII and let Tags carry the icon. The message BODY is UTF-8 data and may hold emoji.
    safe_title = title.encode("ascii", "ignore").decode("ascii").strip() or "Portfolio AI"
    try:
        req = urllib.request.Request(
            target, data=message.encode("utf-8"),
            headers={"Title": safe_title, "Priority": priority, "Tags": tags},
            method="POST")
        urllib.request.urlopen(req, timeout=HTTP_TIMEOUT).read()
        print(f"  ntfy sent: {line}")
    except Exception as e:  # noqa: BLE001 — never let a failed alert crash the monitor
        print(f"  ntfy FAILED ({e}): {line}")


def ping_healthchecks():
    if not HEALTHCHECKS_URL:
        return
    try:
        urllib.request.urlopen(HEALTHCHECKS_URL, timeout=HTTP_TIMEOUT).read()
    except Exception as e:  # noqa: BLE001
        print(f"  healthchecks ping failed: {e}")


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def save_state(state):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except OSError as e:
        print(f"  WARN: could not persist state to {STATE_FILE}: {e}")


def main():
    ap = argparse.ArgumentParser(description="Deep health aggregator for the portfolio RAG chat")
    ap.add_argument("--heartbeat", action="store_true",
                    help="also send an 'all green' ntfy summary (run once/day on a schedule)")
    ap.add_argument("--no-smoke", action="store_true", help="skip the end-to-end WS query")
    args = ap.parse_args()

    results = {}   # name -> (severity, detail)
    for name, fn in build_checks(run_smoke=not args.no_smoke):
        try:
            results[name] = fn()
        except Exception as e:  # noqa: BLE001 — a probe bug must not take down the monitor
            results[name] = (CRITICAL, f"probe raised: {e}")

    for name, (sev, detail) in results.items():
        print(f"  [{sev.upper():8}] {detail}")

    # Tunnel heuristic: if every tunneled downstream is unreachable at once, it's the tunnel.
    tunneled = ["vllm", "qdrant", "embed", "rerank"]
    if all("unreachable" in results.get(n, ("", ""))[1] for n in tunneled):
        print("  → all tunneled services unreachable: SSH tunnel is likely DOWN")

    criticals = {n: d for n, (s, d) in results.items() if s == CRITICAL}
    degraded  = {n: d for n, (s, d) in results.items() if s == DEGRADED}

    # Transition-based paging: compare each check's severity to last run's.
    prev = load_state()
    prev_sev = prev.get("severities", {})
    new_criticals, recovered = [], []
    for name, (sev, detail) in results.items():
        was = prev_sev.get(name, OK)
        if sev == CRITICAL and was != CRITICAL:
            new_criticals.append((name, detail))
        elif sev != CRITICAL and was == CRITICAL:
            recovered.append((name, detail))

    if new_criticals:
        body = "\n".join(f"• {n}: {d}" for n, d in new_criticals)
        if degraded:
            body += "\n(also degraded: " + ", ".join(degraded) + ")"
        ntfy("Portfolio AI DOWN", body, priority="urgent", tags="rotating_light",
             url=NTFY_CRITICAL_URL)
    if recovered:
        body = "\n".join(f"• {n}: {d}" for n, d in recovered)
        # Recovery goes to the SAME topic as the page. Being told it is down and then
        # left wondering is how you end up SSHing in to check something already fixed.
        ntfy("Portfolio AI recovered", body, priority="default", tags="white_check_mark",
             url=NTFY_CRITICAL_URL)

    all_ok = not criticals
    if all_ok:
        ping_healthchecks()
    if args.heartbeat:
        if all_ok and not degraded:
            ntfy("Portfolio AI heartbeat", "All services green.", priority="min", tags="heartbeat")
        elif all_ok:
            ntfy("Portfolio AI heartbeat (degraded)", "Up, but degraded: " + "; ".join(f"{n}: {d}" for n, d in degraded.items()),
                 priority="low", tags="warning")
        # if criticals, the transition alert above already fired.

    # Preserve last_smoke_ts across cycles that did not run the E2E probe, or the
    # throttle would reset every run and the smoke would fire on every cycle.
    prev_smoke_ts = prev.get("last_smoke_ts", 0)
    save_state({"severities": {n: s for n, (s, d) in results.items()},
                "details": {n: d for n, (s, d) in results.items()},
                "last_smoke_ts": _smoke_ran_at if _smoke_ran_at else prev_smoke_ts})

    sys.exit(1 if criticals else 0)


if __name__ == "__main__":
    main()
