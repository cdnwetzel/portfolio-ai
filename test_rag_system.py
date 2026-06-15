#!/usr/bin/env python3
"""
RAG system test suite.
Requires the full stack running locally: api-proxy on :8000, vLLM on :8004,
Qdrant on :6333, embedding service on :8005.

Usage:
    python test_rag_system.py
"""
import asyncio
import json
import websockets
from typing import List, Tuple

WS_URL = "ws://127.0.0.1:8000/ws/chat"
RESPONSE_TIMEOUT = 120  # seconds for a full response

NOT_DOCUMENTED_PHRASE = "don't have that documented"

# Positive cases: question + keywords that should appear in a grounded response.
# Pass threshold: >=50% of keywords present.
POSITIVE_CASES = [
    ("What is your experience with Gentoo Linux?",
     ["gentoo", "kernel", "portage", "openrc"],
     "Gentoo expertise"),
    ("Tell me about your multi-machine Gentoo setup.",
     ["machine", "t5810", "surface", "amd"],
     "Infrastructure fleet"),
    ("How do you configure kernels for different hardware?",
     ["kernel_config", "hardware", "driver", "patch"],
     "Kernel configuration"),
    ("What GPU hardware do you run for AI inference?",
     ["a4500", "nvlink", "vllm", "tensor"],
     "GPU inference setup"),
    ("Tell me about your infrastructure automation tools.",
     ["harvest", "generate", "kernel", "tools"],
     "Automation tooling"),
    ("How much have you saved clients through infrastructure consolidation?",
     ["vmware", "p2v", "server", "cost"],
     "Infrastructure ROI"),
    ("Tell me about a multi-region virtual desktop project.",
     ["avd", "azure", "migration", "user"],
     "VDI deployment"),
    ("What is the pxx project?",
     ["aider", "memory", "endpoint", "observation"],
     "pxx project"),
    ("How do you handle system updates across your Gentoo machines?",
     ["emerge", "update", "portage", "kernel"],
     "Update management"),
    ("What is the AI chat system at dev.cwetzel.com?",
     ["qdrant", "rag", "vllm", "websocket"],
     "Portfolio chat system"),
    ("Tell me about your SOC2 compliance work.",
     ["soc2", "audit", "control", "compliance"],
     "SOC2 compliance"),
    ("What is your SAP deployment experience?",
     ["sap", "warehouse", "continent", "integration"],
     "SAP deployment"),
]

# Negative cases: questions that are off-KB.
# Pass condition: response contains the NOT_DOCUMENTED_PHRASE.
NEGATIVE_CASES = [
    ("What are your thoughts on Bitcoin and cryptocurrency investing?",
     "Off-KB: cryptocurrency"),
    ("Can you explain the history of the Roman Empire?",
     "Off-KB: Roman history"),
    ("What is the best programming language for a complete beginner to learn first?",
     "Off-KB: beginner programming advice"),
    ("Tell me about your experience with Kubernetes, Helm, and Terraform.",
     "Off-KB: Kubernetes/Helm/Terraform"),
]


async def query(question: str) -> str:
    """Send a question over WebSocket and collect the full streamed response."""
    try:
        async with websockets.connect(WS_URL) as ws:
            await ws.send(json.dumps({
                "type": "chat",
                "payload": {
                    "model": "qwen2.5-coder-14b-pscode",
                    "messages": [{"role": "user", "content": question}],
                }
            }))

            response = ""
            try:
                async with asyncio.timeout(RESPONSE_TIMEOUT):
                    while True:
                        raw = await ws.recv()
                        msg = json.loads(raw)
                        if msg.get("type") == "chunk":
                            delta = (msg.get("data", {})
                                       .get("choices", [{}])[0]
                                       .get("delta", {})
                                       .get("content", ""))
                            response += delta
                        elif msg.get("type") in ("done", "error"):
                            break
            except asyncio.TimeoutError:
                response += "  [TIMED OUT]"

            return response
    except Exception as e:
        return f"[ERROR: {e}]"


def keyword_score(response: str, keywords: List[str]) -> Tuple[int, List[str]]:
    lower = response.lower()
    found = [kw for kw in keywords if kw.lower() in lower]
    return len(found), found


async def run():
    total = passed = 0
    failures = []

    print("=" * 72)
    print("RAG TEST SUITE")
    print("=" * 72)

    # --- Positive cases ---
    print(f"\nPositive cases ({len(POSITIVE_CASES)}) — expect grounded answers\n")
    for question, keywords, label in POSITIVE_CASES:
        total += 1
        response = await query(question)
        found_count, found = keyword_score(response, keywords)
        ratio = found_count / len(keywords) if keywords else 0
        ok = ratio >= 0.5 and not response.startswith("[ERROR")
        if ok:
            passed += 1
            print(f"  ✓  {label}  ({found_count}/{len(keywords)} keywords)")
        else:
            failures.append((label, question, response))
            print(f"  ✗  {label}  ({found_count}/{len(keywords)} keywords: {found})")
            print(f"     {response[:120]}...")

    # --- Negative cases ---
    print(f"\nNegative cases ({len(NEGATIVE_CASES)}) — expect 'not documented' responses\n")
    for question, label in NEGATIVE_CASES:
        total += 1
        response = await query(question)
        ok = NOT_DOCUMENTED_PHRASE in response.lower() and not response.startswith("[ERROR")
        if ok:
            passed += 1
            print(f"  ✓  {label}")
        else:
            failures.append((label, question, response))
            print(f"  ✗  {label}")
            print(f"     {response[:120]}...")

    # --- Summary ---
    print()
    print("=" * 72)
    pct = 100 * passed // total if total else 0
    print(f"RESULT: {passed}/{total} passed ({pct}%)")
    if failures:
        print("\nFailed:")
        for label, q, r in failures:
            print(f"  {label}")
            print(f"    Q: {q}")
            print(f"    A: {r[:100]}...")
    print("=" * 72)

    if passed >= total * 0.75:
        print("✅ RAG grounding looks solid.")
    else:
        print("⚠️  Below 75% pass rate — check KB coverage or model behavior.")


if __name__ == "__main__":
    asyncio.run(run())
