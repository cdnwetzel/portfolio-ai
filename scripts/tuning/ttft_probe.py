#!/usr/bin/env python3
"""Measure time-to-first-token against the vLLM backend at varying prompt sizes.

TTFT = prefill + queue + first decode step. For a bursty, mostly-single-turn
workload TTFT dominates the felt experience; sustained decode tok/s does not.
Prefill is COMPUTE-bound (unlike decode, which is memory-bandwidth-bound), so it
should respond differently to the SM-clock change than decode did.
"""
import json, sys, time, urllib.request

BASE = "http://127.0.0.1:8007"
MODEL = json.load(urllib.request.urlopen(BASE + "/v1/models", timeout=10))["data"][0]["id"]

# ~1.3 tokens/word filler; build prompts of a target token size.
WORD = "The retrieval system indexes documents about infrastructure and hardware. "

def make_prompt(target_tokens):
    reps = max(1, int(target_tokens / 13))          # ~13 tok per sentence
    return (WORD * reps) + "\n\nQuestion: what GPUs does the T5810 have?\nAnswer:"

def ttft(prompt, max_tokens=16):
    body = json.dumps({
        "model": MODEL, "prompt": prompt, "max_tokens": max_tokens,
        "temperature": 0, "stream": True,
    }).encode()
    req = urllib.request.Request(BASE + "/v1/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    first = None
    ntok = 0
    with urllib.request.urlopen(req, timeout=180) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data: "):
                continue
            if line.endswith("[DONE]"):
                break
            try:
                d = json.loads(line[6:])
            except ValueError:
                continue
            txt = d.get("choices", [{}])[0].get("text", "")
            if txt:
                if first is None:
                    first = time.perf_counter() - t0
                ntok += 1
    total = time.perf_counter() - t0
    return first, total, ntok

def ntokens(p):
    # crude but consistent across runs; we only compare like with like
    return int(len(p) / 4.2)

if __name__ == "__main__":
    sizes = [int(x) for x in (sys.argv[1:] or [256, 1024, 2048, 4096])]
    print(f"  model={MODEL}")
    print(f"  {'prompt~tok':>11} {'TTFT ms':>9} {'ms/1k prefill':>14}")
    for s in sizes:
        p = make_prompt(s)
        n = ntokens(p)
        ttft(p, 4)                                   # warm the path, discard
        runs = [ttft(p, 8)[0] for _ in range(3)]
        best = min(runs) * 1000
        mean = sum(runs) / len(runs) * 1000
        print(f"  {n:>11} {mean:>8.0f}  {mean/max(n,1)*1000:>13.1f}   (best {best:.0f})")
