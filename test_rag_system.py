#!/usr/bin/env python3
"""
Automated RAG test suite.
Tests semantic search + chat grounding with synthetic questions.
"""

import asyncio
import json
import websockets
from typing import List, Tuple

TEST_CASES = [
    ("What is your experience with Gentoo Linux?", ["gentoo", "kernel", "portage", "openrc"], "Gentoo expertise"),
    ("How do you configure kernel options for different hardware?", ["kernel_config", "hardware", "nuc", "xps", "surface"], "Kernel configuration"),
    ("Tell me about your multi-machine Gentoo setup.", ["machine", "precision", "beelink", "xps", "surface"], "Infrastructure at scale"),
    ("What is your experience with Linux system administration?", ["openrc", "gentoo", "configuration", "setup"], "Linux sysadmin background"),
    ("How do you approach hardware compatibility in Linux?", ["hardware", "kernel", "driver", "patch"], "Hardware driver experience"),
    ("How much have you saved clients through infrastructure consolidation?", ["vmware", "p2v", "800k", "hardware"], "Infrastructure ROI"),
    ("Tell me about a multi-region virtual desktop project.", ["avd", "azure", "region", "latency"], "VDI deployment"),
    ("How do you handle system updates across multiple machines?", ["update", "emerge", "gentoo", "portage"], "Update management"),
    ("What's your experience with GPU-accelerated systems?", ["gpu", "nvlink", "precision", "cuda"], "GPU infrastructure"),
    ("How do you manage kernel configuration across different hardware?", ["kernel", "hardware", "config", "laptop", "desktop"], "Cross-hardware kernel"),
    ("Tell me about your infrastructure automation tools.", ["script", "tool", "harvest", "generate", "update"], "Automation and tooling"),
    ("What infrastructure challenges have you solved?", ["infrastructure", "consolidation", "migration", "gentoo"], "General infrastructure"),
]

async def test_chat(question: str) -> str:
    """Send a question via WebSocket chat."""
    try:
        async with websockets.connect('ws://127.0.0.1:8000/ws/chat') as ws:
            await ws.send(json.dumps({
                'type': 'chat',
                'payload': {
                    'model': 'qwen2.5-coder-14b-pscode',
                    'messages': [{'role': 'user', 'content': question}]
                }
            }))

            response = ''
            while True:
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                    if msg.get('type') == 'chunk':
                        chunk = msg.get('data', {})
                        if 'choices' in chunk:
                            delta = chunk['choices'][0].get('delta', {})
                            if 'content' in delta:
                                response += delta['content']
                    elif msg.get('type') == 'done':
                        break
                except asyncio.TimeoutError:
                    break

            return response
    except Exception as e:
        return f"[ERROR: {str(e)}]"

def check_keywords(response: str, keywords: List[str]) -> Tuple[int, List[str]]:
    """Count matching keywords."""
    response_lower = response.lower()
    found = [kw for kw in keywords if kw.lower() in response_lower]
    return len(found), found

async def run_tests():
    """Run all test cases."""
    print("=" * 80)
    print("RAG SYSTEM TEST SUITE - Gentoo + Infrastructure Knowledge")
    print("=" * 80)
    print()

    results = []
    passed = 0

    for i, (question, keywords, description) in enumerate(TEST_CASES, 1):
        print(f"[{i}/{len(TEST_CASES)}] {description}")
        print(f"Q: {question}")

        response = await test_chat(question)
        found_count, found_keywords = check_keywords(response, keywords)
        match_ratio = found_count / len(keywords) if keywords else 0
        is_pass = match_ratio >= 0.5 and not response.startswith("[ERROR")

        if is_pass:
            passed += 1
            status = "✓ PASS"
        else:
            status = "✗ FAIL"

        print(f"{status} ({found_count}/{len(keywords)} keywords: {', '.join(found_keywords)})")
        print(f"Response: {response[:150]}...")
        print()

        results.append({
            'question': question,
            'description': description,
            'passed': is_pass,
            'keywords_found': found_keywords,
            'response': response[:300]
        })

    # Summary
    print("=" * 80)
    print(f"RESULTS: {passed}/{len(TEST_CASES)} tests passed ({100*passed/len(TEST_CASES):.0f}%)")
    print("=" * 80)
    print()

    for r in results:
        status = "✓" if r['passed'] else "✗"
        print(f"{status} {r['description']}")
        if not r['passed']:
            print(f"   Expected: {', '.join(r.get('keywords_found', []))}")
            print(f"   Got: {r['response'][:80]}...")
        print()

    return passed, len(TEST_CASES)

async def main():
    try:
        passed, total = await run_tests()
        if passed >= total * 0.7:
            print(f"✅ {passed}/{total} tests passed. RAG is grounding well.")
            return 0
        else:
            print(f"⚠️  {passed}/{total} tests passed. Check response quality.")
            return 0
    except Exception as e:
        print(f"✗ Error: {e}")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
