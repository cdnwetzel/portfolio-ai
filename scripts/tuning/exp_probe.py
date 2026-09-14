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
  B. repeated prefix     — same long prefix, different question
  C. quoting decode      — asks for verbatim reproduction of supplied text
  D. non-quoting decode  — control; ngram should NOT help here
  E. empty-completion rate on repeated cache-hit prompts (correctness, not speed)

SCOPE LIMIT — READ BEFORE DRAWING A PRODUCTION CONCLUSION FROM PROBE B OR E.
This file talks to **/v1/completions**, a raw text completion whose prompt ends in "Answer:".
cwdotcom never uses that endpoint: the proxy sends **/v1/chat/completions** with a system
message, `enable_thinking=false` and `max_tokens=2048` (cloud/api-proxy.py:_stream_completion).
The two shapes are not interchangeable, and on 2026-09-12 they disagreed sharply. With
`--enable-prefix-caching`, measured at production sampling (temp 0.2, top_p 0.7):

    /v1/completions        25/30 completions came back EMPTY
    /v1/chat/completions    0/30

So probe B's empties are real, reproducible, and **not by themselves evidence of production
risk** -- they are evidence about an endpoint the site does not call. Worse at temp 0.2 than at
temp 0 there, which is the opposite of the usual intuition. Use
`scripts/tuning/prefix_empty_probe.py` (which replays the real SYSTEM_PREFIX through chat
completions) to judge production impact; use this file for TTFT and decode shape only.
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
    """-> (ttft_ms or None, decode_tok_s, n_tokens, finish_reason).

    TTFT is None -- NOT 0 -- when no non-empty token ever arrived. The earlier version
    returned `(first or 0) * 1000`, so an EMPTY generation printed as "TTFT 0 ms" and read
    as an infinitely fast response. That is exactly what happened in the 2026-09-12 prefix
    run: probe B printed "0 ms, 492 ms, 0 ms" and two of those three were zero-token
    completions, not wins. A probe that cannot tell "instant" from "nothing" manufactures
    the result it is supposed to measure -- the same false-pass shape as the Aug-31 argv
    assertion that printed "expected for baseline" during a non-baseline run.
    """
    body = json.dumps({"model": MODEL, "prompt": prompt, "max_tokens": max_tokens,
                       "temperature": temperature, "stream": True}).encode()
    req = urllib.request.Request(BASE + "/v1/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter(); first = None; n = 0; finish = None
    with urllib.request.urlopen(req, timeout=300) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data: ") or line.endswith("[DONE]"):
                continue
            try: d = json.loads(line[6:])
            except ValueError: continue
            ch = d.get("choices", [{}])[0]
            if ch.get("finish_reason"): finish = ch["finish_reason"]
            t = ch.get("text", "")
            if t:
                if first is None: first = time.perf_counter() - t0
                n += 1
    total = time.perf_counter() - t0
    dec = (n - 1) / (total - first) if (first and n > 1 and total > first) else 0.0
    return (None if first is None else first * 1000), dec, n, finish


def fmt_ttft(ttft, n, finish):
    """An empty completion must be impossible to mistake for a fast one."""
    if ttft is None:
        return "  EMPTY -- 0 tokens (finish_reason=%s) -- NOT a latency result" % finish
    return "TTFT %6.0f ms  (%d tok, finish=%s)" % (ttft, n, finish)

empties = 0

# A and B ask for 32 tokens, not 192, and a short deterministic completion can legitimately
# stop at once -- so these two probes are where an empty run is most likely, and where it
# used to be invisible. Asking for a minimum of real text makes the measurement honest.
print("A. cold TTFT (fresh prompt each time)")
for i in range(2):
    ttft, _, n, fin = run(PREFIX + f"\n\nQuestion {i}: describe the GPU layout.\nAnswer:", 32)
    empties += ttft is None
    print("     run %d: %s" % (i + 1, fmt_ttft(ttft, n, fin)))

print("B. REPEATED prefix, different question  <-- prefix caching shows up here")
for i in range(3):
    ttft, _, n, fin = run(PREFIX + f"\n\nQuestion: item {i}, describe the retrieval path.\nAnswer:", 32)
    empties += ttft is None
    print("     run %d: %s" % (i + 1, fmt_ttft(ttft, n, fin)))

print("C. quoting decode  <-- ngram spec-dec shows up here")
q = (PREFIX + "\n\nReproduce Source 3 above verbatim, word for word, then Source 4 "
     "verbatim.\nAnswer:")
for i in range(2):
    ttft, dec, n, fin = run(q, 192)
    empties += ttft is None
    print("     run %d: %5.1f tok/s decode (%d tok, finish=%s), %s"
          % (i + 1, dec, n, fin, fmt_ttft(ttft, n, fin)))

print("D. non-quoting decode (control — ngram should NOT help)")
for i in range(2):
    ttft, dec, n, fin = run("Write 150 words of original prose about ocean currents.\nAnswer:", 192)
    empties += ttft is None
    print("     run %d: %5.1f tok/s decode (%d tok, finish=%s), %s"
          % (i + 1, dec, n, fin, fmt_ttft(ttft, n, fin)))

# E. EMPTY-COMPLETION RATE on repeated cache-hit prompts.
#
# Why this probe exists. In the 2026-09-12 `prefix` run, 2 of 3 probe-B runs produced ZERO
# tokens, which the old code printed as "TTFT 0 ms" and therefore read as an instant win.
# The same three prompts at the same temperature 0 on the same model produced 32 tokens each
# at baseline. Deterministic sampling, identical input, different output: the CONFIG changed
# behaviour. An empty completion is the 2026-08-29 blank-bubble outage symptom, so a flag
# that produces them cannot ship to a public chat however good its TTFT is -- and vLLM 0.27.1
# keeps prefix caching opt-in for hybrid models precisely because the path is still maturing.
#
# Three runs is not enough to act on, so measure the rate with a real n. Deliberately the
# cwdotcom shape: one constant long prefix, a different short question each time.
# Validated, not just cast. EMPTY_N=0 reached `100.0 * e_empty / N_EMPTY` and died with a
# ZeroDivisionError AFTER the probe had already spent a restart window; a non-integer died on
# the cast with a traceback that says nothing about which knob was wrong. Both now fail
# immediately with the variable named.
_raw_empty_n = __import__("os").environ.get("EMPTY_N", "20")
try:
    N_EMPTY = int(_raw_empty_n)
except ValueError:
    raise SystemExit(f"FATAL: EMPTY_N={_raw_empty_n!r} is not an integer (probe E sample count).")
if N_EMPTY < 1:
    raise SystemExit(f"FATAL: EMPTY_N={N_EMPTY} must be >= 1; probe E computes a rate over it.")
print("E. empty-completion rate, %d repeated cache-hit prompts  <-- correctness, not speed" % N_EMPTY)
e_empty = 0; e_ttft = []; reasons = {}
for i in range(N_EMPTY):
    ttft, _, n, fin = run(PREFIX + f"\n\nQuestion: row {i}, summarise the serving stack.\nAnswer:", 32)
    reasons[fin] = reasons.get(fin, 0) + 1
    if ttft is None or n == 0:
        e_empty += 1
    else:
        e_ttft.append(ttft)
med = sorted(e_ttft)[len(e_ttft)//2] if e_ttft else float("nan")
print("     EMPTY: %d/%d (%.0f%%)   non-empty median TTFT: %.0f ms   finish_reasons: %s"
      % (e_empty, N_EMPTY, 100.0*e_empty/N_EMPTY, med, reasons))
empties += e_empty

if empties:
    print("\n  !! %d probe runs generated ZERO tokens. Those rows are NOT latency measurements"
          "\n     and must not be averaged in. An empty completion reaching a user is the"
          "\n     blank-bubble failure mode -- treat this as a correctness result, not noise."
          % empties)
else:
    print("\n  all probe runs produced tokens (no empty completions)")
