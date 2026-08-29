#!/usr/bin/env python3
"""
Turn-handoff check for /ws/chat — guards the "Connection lost" class of bug.

Why this exists (DEFECT_LEDGER #7, closed 2026-08-19): the client holds the socket
open after `done` to receive a faithfulness verdict. On paths where no verdict can
ever arrive (guardrail, meta, off-topic, not-documented, or a low-relevance answer
the verify gate skips), it used to wait the full VERDICT_WINDOW_MS. That lingering
socket counted against ConnectionRateLimiter, so the user's OWN next question was
rejected with a 429 before accept() — which a browser surfaces as an opaque 1006
close, i.e. "Connection lost" with the question silently unanswered.

The bug was typing-speed dependent: read the answer slowly and the window expires
harmlessly; fire off two questions quickly and both vanish. That is why it survived
so long, and why a check has to reproduce the FAST case deliberately.

This asks a question, keeps the first socket open exactly as the old client did,
and immediately opens a second for the follow-up. It also asserts the `done` frame
carries `verify`, which is what tells the client whether waiting is warranted at
all. selftest.py cannot catch this: it asks each question on its own connection.

Usage:
    python3 scripts/ws_concurrency_check.py
    python3 scripts/ws_concurrency_check.py --url ws://localhost:8000/ws/chat

Exit code 0 = every follow-up was answered; 1 = a handoff was rejected.
"""
import argparse
import asyncio
import json
import sys

import websockets

# (first question, immediate follow-up). Each pair pins a distinct path:
#   canned/meta   -> no verifier runs, so the old client waited the full window
#   low-relevance -> the verify gate skips, same outcome via a different branch
#   full RAG      -> a real answer whose verdict may or may not arrive
PAIRS = [
    ("what can I ask?", "what am I supposed to do"),
    ("what is Chris's favorite operating system", "what can you tell me about chris"),
    ("Tell me about the GPU home lab setup", "tell me about the Asrock B550"),
]


async def ask(ws, question, timeout):
    await ws.send(json.dumps({
        "type": "chat",
        "payload": {
            "messages": [{"role": "user", "content": question}],
            # The proxy pins the model server-side (MODEL_ID); this value is ignored
            # on purpose — sending a stale one here is part of the regression check.
            "model": "ignored-by-proxy",
            "max_tokens": 2048,
        },
    }))
    text, verify, sources = "", "MISSING", 0
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        kind = msg.get("type")
        if kind == "sources":
            sources = len(msg.get("data") or [])
        elif kind == "chunk":
            text += msg["data"]["choices"][0]["delta"].get("content") or ""
        elif kind == "done":
            return text, msg.get("verify", "MISSING"), sources
        elif kind == "error":
            raise RuntimeError(f"error frame: {msg.get('message')}")


async def run(url, timeout):
    failures = 0
    for first, second in PAIRS:
        print(f"\n=== {first!r}\n    THEN IMMEDIATELY {second!r} ===")
        held = await websockets.connect(url, open_timeout=10)
        try:
            text, verify, n = await ask(held, first, timeout)
            print(f"  [1] ok  sources={n} verify={verify} len={len(text)}")
            if verify == "MISSING":
                print("  [1] FAIL: `done` lacks the verify field — the client cannot "
                      "know whether to wait, which is what caused the 429s")
                failures += 1
            if not text.strip():
                print("  [1] FAIL: empty answer")
                failures += 1

            # The old client kept the first socket open here for the verdict window.
            # Hold it and open the follow-up anyway — this is the failing case.
            try:
                async with websockets.connect(url, open_timeout=10) as ws2:
                    text2, verify2, n2 = await ask(ws2, second, timeout)
                    print(f"  [2] ok  sources={n2} verify={verify2} len={len(text2)}")
                    if not text2.strip():
                        print("  [2] FAIL: empty answer")
                        failures += 1
            except Exception as e:
                print(f"  [2] FAIL: follow-up rejected while the previous socket was "
                      f"open -> {type(e).__name__}: {e}")
                failures += 1
        finally:
            await held.close()

    print(f"\n{'=== PASSED ===' if not failures else f'=== FAILED ({failures}) ==='}")
    return failures


def main():
    ap = argparse.ArgumentParser(description="WebSocket turn-handoff regression check")
    ap.add_argument("--url", default="wss://dev.cwetzel.com/ws/chat")
    ap.add_argument("--timeout", type=float, default=120.0,
                    help="per-frame receive timeout (default 120s)")
    args = ap.parse_args()
    print(f"Turn-handoff check against {args.url}  ({len(PAIRS)} pairs)")
    sys.exit(1 if asyncio.run(run(args.url, args.timeout)) else 0)


if __name__ == "__main__":
    main()
