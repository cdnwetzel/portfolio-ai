#!/usr/bin/env python3
"""Workload probes for the vLLM flag experiments.

bench-vllm.sh measures steady-state decode on a short prompt. Neither experiment
shows up there:

  prefix caching accelerates PREFILL when a prompt prefix repeats. cwdotcom sends a
  constant system prompt on every request and resends history each turn, so the
  question is "does a repeated prefix get cheaper", not "is decode faster".

  ngram speculative decoding accelerates DECODE only when the output repeats spans
  from the input. Grounded RAG quotes retrieved context constantly; a generic
  "write about networking" prompt has nothing to copy, so it would show ~0 gain
  and look like a failure.

Probes:
  A. cold TTFT           — fresh prompt, no shared prefix
  B. repeated prefix     — same long prefix, different question (the cwdotcom shape)
  C. quoting decode      — asks for verbatim reproduction of supplied text
  D. non-quoting decode  — control; ngram should NOT help here
"""
import json, time, urllib.request

BASE = "http://127.0.0.1:8007"
MODEL = json.load(urllib.request.urlopen(BASE + "/v1/models", timeout=10))["data"][0]["id"]

PREFIX = ("You are a retrieval system answering from the sources below.\n\n"
          + "".join(
              f"### Source {i}\nThe T5810 workstation runs two RTX A4500 GPUs joined by an "
              f"NVLink bridge, serving a 27B model with tensor parallelism across both cards. "
              f"Retrieval uses a 768-dimensional bge-base embedding into Qdrant, reranked by a "
              f"cross-encoder on a separate GPU. Document {i} of the corpus.\n\n"
              for i in range(28)))

def run(prompt, max_tokens=192, temperature=0.0):
    body = json.dumps({"model": MODEL, "prompt": prompt, "max_tokens": max_tokens,
                       "temperature": temperature, "stream": True}).encode()
    req = urllib.request.Request(BASE + "/v1/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter(); first = None; n = 0
    with urllib.request.urlopen(req, timeout=300) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data: ") or line.endswith("[DONE]"):
                continue
            try: d = json.loads(line[6:])
            except ValueError: continue
            t = d.get("choices", [{}])[0].get("text", "")
            if t:
                if first is None: first = time.perf_counter() - t0
                n += 1
    total = time.perf_counter() - t0
    dec = (n - 1) / (total - first) if (first and n > 1 and total > first) else 0.0
    return (first or 0) * 1000, dec, n

print("A. cold TTFT (fresh prompt each time)")
for i in range(2):
    ttft, _, _ = run(PREFIX + f"\n\nQuestion {i}: describe the GPU layout.\nAnswer:", 32)
    print("     run %d: TTFT %6.0f ms" % (i + 1, ttft))

print("B. REPEATED prefix, different question  <-- prefix caching shows up here")
for i in range(3):
    ttft, _, _ = run(PREFIX + f"\n\nQuestion: item {i}, describe the retrieval path.\nAnswer:", 32)
    print("     run %d: TTFT %6.0f ms" % (i + 1, ttft))

print("C. quoting decode  <-- ngram spec-dec shows up here")
q = (PREFIX + "\n\nReproduce Source 3 above verbatim, word for word, then Source 4 "
     "verbatim.\nAnswer:")
for i in range(2):
    ttft, dec, n = run(q, 192)
    print("     run %d: %5.1f tok/s decode (%d tok), TTFT %5.0f ms" % (i + 1, dec, n, ttft))

print("D. non-quoting decode (control — ngram should NOT help)")
for i in range(2):
    ttft, dec, n = run("Write 150 words of original prose about ocean currents.\nAnswer:", 192)
    print("     run %d: %5.1f tok/s decode (%d tok), TTFT %5.0f ms" % (i + 1, dec, n, ttft))
