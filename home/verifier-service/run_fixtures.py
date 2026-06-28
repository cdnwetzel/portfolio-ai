#!/usr/bin/env python3
"""
Judge-accuracy gate (verifier-faithfulness-layer.md §8.1).

Runs the fixtures against a LIVE /verify endpoint and checks each gets the expected
verdict_type + flag. This validates the judge model before its telemetry is believed
("the eval can measure the wrong thing"). Requires a running verifier-service +
judge model; no-ops with a clear message if the endpoint is unreachable.

Usage:
    python3 run_fixtures.py --url http://127.0.0.1:8007
"""
import argparse
import json
import os
import sys
import urllib.request


def post_verify(base_url: str, case: dict, timeout: float = 90.0) -> dict:
    body = json.dumps({"query": case["query"], "answer": case["answer"],
                       "chunks": case["chunks"]}).encode()
    req = urllib.request.Request(base_url.rstrip("/") + "/verify", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8007")
    ap.add_argument("--fixtures", default=os.path.join(os.path.dirname(__file__), "fixtures.json"))
    args = ap.parse_args()

    with open(args.fixtures) as f:
        cases = json.load(f)

    try:
        urllib.request.urlopen(args.url.rstrip("/") + "/health", timeout=5).read()
    except Exception as e:
        print(f"⚠ verifier not reachable at {args.url} ({e}); skipping judge-accuracy gate.")
        sys.exit(0)

    passed = 0
    for case in cases:
        try:
            res = post_verify(args.url, case)
        except Exception as e:
            print(f"  [FAIL] {case['name']}: request error {e}")
            continue
        exp = case["expected"]
        ok = (res.get("verdict_type") == exp["verdict_type"]
              and bool(res.get("flagged")) == bool(exp["flagged"]))
        passed += ok
        f = res.get("faithfulness")
        print(f"  [{'PASS' if ok else 'FAIL'}] {case['name']:32} "
              f"type={res.get('verdict_type')} flagged={res.get('flagged')} faith={f}")

    print(f"\n  {passed}/{len(cases)} fixtures correct")
    print(f"=== JUDGE-ACCURACY {'PASSED' if passed == len(cases) else 'FAILED'} ===")
    sys.exit(0 if passed == len(cases) else 1)


if __name__ == "__main__":
    main()
