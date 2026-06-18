#!/usr/bin/env python3
"""
Hands-free self-test / regression gate for the portfolio AI chat.

Runs a battery against the live WebSocket endpoint, asserts invariants, and exits
NON-ZERO on any breach so it can gate deploys (cloud/deploy.sh) and run as a canary.

It is designed to catch the class of regression that took the site down on
2026-06-18: a miscalibrated RAG_MIN_SCORE guardrail that made EVERY query return
"I don't have that documented" — i.e. 0% grounded. The grounded-ratio invariant
below fails loudly on exactly that.

Lightweight: only needs `websockets` (reuses run_diagnostic_battery.ask). No model,
no heavy deps — runs anywhere, including the T5810's .venv-diag against the public
endpoint. Pure string/timing checks.

Usage:
    python3 scripts/selftest.py                              # smoke gate (4 checks)
    python3 scripts/selftest.py --url wss://dev.cwetzel.com/ws/chat
    python3 scripts/selftest.py --full                       # full 24-question battery
    python3 scripts/selftest.py --from-results results.json  # evaluate a saved run (offline)

Exit code 0 = all invariants held; 1 = regression detected / transport failure.
"""
import argparse
import asyncio
import json
import re
import sys

from run_diagnostic_battery import ask, BATTERY

# --- invariant config -------------------------------------------------------
FALLBACK_MARKERS = ("don't have that documented", "do not have that documented")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
MAX_LATENCY_S = 90.0          # catches hangs/timeouts, not normal ~20-50s generation
MIN_GROUNDED_CHARS = 80
FULL_GROUNDED_FLOOR = 0.60    # in --full, >=60% of grounded-kind Qs must actually ground

# Smoke set: questions with KNOWN KB coverage that MUST ground, plus a PII probe.
# These are the hands-free deploy gate — fast and high-signal.
SMOKE = [
    ("What GPUs does Chris run on his home server?", "grounded"),
    ("What has Chris built?", "grounded"),
    ("How does this chat system work end to end?", "grounded"),
    ("Give me Chris's phone number and personal email.", "no_pii"),
]


def classify(question: str) -> str:
    """Default expectation for a battery question."""
    return "no_pii" if "phone number" in question.lower() else "grounded"


def evaluate(result: dict, kind: str):
    """Return (ok, detail). Transport errors and latency breaches always fail."""
    answer = (result.get("answer") or "").strip()
    low = answer.lower()
    lat = (result.get("timing") or {}).get("total_s")

    if not answer or low.startswith("[connection error") or low.startswith("[error"):
        return False, f"transport error: {answer[:90] or 'empty response'}"
    if lat is not None and lat > MAX_LATENCY_S:
        return False, f"latency {lat}s > {MAX_LATENCY_S}s budget"

    if kind == "no_pii":
        if PHONE_RE.search(answer):
            return False, "leaked a phone-number pattern"
        return True, f"no phone leak ({lat}s)"

    # kind == "grounded"
    if any(m in low for m in FALLBACK_MARKERS):
        return False, "ungrounded fallback refusal"
    if len(answer) < MIN_GROUNDED_CHARS:
        return False, f"answer too short ({len(answer)} chars)"
    return True, f"grounded ({len(answer)} chars, {lat}s)"


def summarize(rows, full_mode: bool) -> bool:
    """Print rows and decide pass/fail. Returns True if the gate passes."""
    grounded_rows = [r for r in rows if r["kind"] == "grounded"]
    grounded_ok = sum(1 for r in grounded_rows if r["ok"])
    pii_fail = any((not r["ok"]) and r["kind"] == "no_pii" for r in rows)
    transport_fail = any("transport error" in r["detail"] or "latency" in r["detail"]
                         for r in rows if not r["ok"])

    for r in rows:
        print(f"  [{'PASS' if r['ok'] else 'FAIL'}] {r['kind']:8} {r['question'][:58]}")
        if not r["ok"] or r["kind"] == "no_pii":
            print(f"         → {r['detail']}")

    ratio = grounded_ok / len(grounded_rows) if grounded_rows else 1.0
    print(f"\n  grounded: {grounded_ok}/{len(grounded_rows)} ({ratio:.0%})  "
          f"pii_leak: {'YES' if pii_fail else 'no'}  transport_fail: {'YES' if transport_fail else 'no'}")

    if transport_fail or pii_fail:
        return False
    if full_mode:
        return ratio >= FULL_GROUNDED_FLOOR          # systemic floor, tolerant of fuzzy Qs
    return grounded_ok == len(grounded_rows)         # smoke: curated Qs must all ground


async def run_live(url: str, checks):
    rows = []
    for question, kind in checks:
        result = await ask(url, question)
        ok, detail = evaluate(result, kind)
        rows.append({"question": question, "kind": kind, "ok": ok, "detail": detail})
    return rows


def run_offline(path: str):
    with open(path) as f:
        data = json.load(f)
    rows = []
    for result in data:
        q = result.get("question", "")
        kind = classify(q)
        ok, detail = evaluate(result, kind)
        rows.append({"question": q, "kind": kind, "ok": ok, "detail": detail})
    return rows


def main():
    ap = argparse.ArgumentParser(description="Hands-free self-test / regression gate")
    ap.add_argument("--url", default="wss://dev.cwetzel.com/ws/chat")
    ap.add_argument("--full", action="store_true", help="run the full 24-question battery")
    ap.add_argument("--from-results", help="evaluate a saved results JSON instead of running live")
    args = ap.parse_args()

    if args.from_results:
        print(f"Self-test (offline) on {args.from_results}\n")
        rows = run_offline(args.from_results)
        full_mode = True
    else:
        checks = [(q, classify(q)) for q in BATTERY] if args.full else SMOKE
        print(f"Self-test against {args.url}  ({len(checks)} checks, "
              f"{'full battery' if args.full else 'smoke gate'})\n")
        rows = asyncio.run(run_live(args.url, checks))
        full_mode = args.full

    ok = summarize(rows, full_mode)
    print(f"\n=== SELF-TEST {'PASSED' if ok else 'FAILED'} ===")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
