#!/usr/bin/env python3
"""Repeat-sample the live chat to surface INTERMITTENT defects.

Single-pass checking cannot clear this system. The two worst defects found on 2026-09-02/03 --
a retired RTX 3060 Ti presented as current hardware, and a removed 130 W power profile read as
the live configuration -- each surfaced in roughly ONE RUN IN FOUR. A "verified clean across
six phrasings" claim was made on that basis and was not proof.

So this asks each question N times and reports two different things:

  1. FORBIDDEN  -- a known-wrong string appeared. Hard failure, same list as the eval gate.
  2. UNSTABLE   -- runs DISAGREED with each other on a checkable fact. This is the real signal:
                   an answer that says 40 GB three times and 56 GB twice is broken even though
                   no single run looks obviously wrong.

Metadata only: records which probes matched, never answer text (red-lines.md #2).
"""
import argparse, asyncio, re, sys
from collections import defaultdict
sys.path.insert(0, "scripts")
from run_diagnostic_battery import ask

# (question, [(probe_label, regex), ...], [forbidden regexes])
#
# PROBES ARE REGEXES, NOT SUBSTRINGS -- and that is not a style choice, it is the fix for
# three false positives this harness produced on its first run (2026-09-04):
#
#   "6 warehouse"  missed every run that wrote "six warehouses"      -> word vs digit
#   forbid "29.4"  fired on "moved generation FROM 29.4 TO 33.2"     -> a correct history line
#   forbid "3060"  fired on "retired RTX 3060 Ti"                    -> a correct retirement note
#
# All three are the same mistake: matching a token instead of the claim. It is the same trap
# the golden set hit the day before ("encode the defect, not the token") and the same shape as
# the router's `selection` -> `election` bug. A probe that cannot tell a fact from a mention of
# its history reports noise, and noise in a checker is worse than no checker.
CASES = [
    ("What has Chris built?",
     [("a4500", r"a4500"), ("27b", r"27b")],
     # NOT forbidding "3060": "retired RTX 3060 Ti" is a correct historical statement here.
     # The defect was the 3060 presented as CURRENT, which the targeted questions below cover.
     [r"qwen2\.5[- ]7b"]),
    ("Tell me about the GPU home lab setup",
     [("40gb_total", r"40\s*gb"), ("165w", r"165\s*w"), ("a4500", r"a4500")],
     [r"capped at 130", r"130\s*w per card", r"56\s*gb total"]),
    ("What specific models are running on the AI Portfolio Chat system?",
     [("qwen38", r"qwen3\.8"), ("judge14b", r"14b"), ("bge", r"bge")],
     [r"3060", r"qwen2\.5[- ]7b"]),
    ("How does this chat system work end to end?",
     [("qdrant", r"qdrant"), ("rerank", r"rerank"), ("vllm", r"vllm")],
     [r"3060"]),
    ("How much VRAM do the two A4500s have in total?",
     [("40gb", r"40\s*gb"), ("20gb_each", r"20\s*gb")],
     [r"56\s*gb"]),
    ("What is the GPU power cap on the T5810?",
     [("165w", r"165")],
     [r"130\s*w", r"1200\s*mhz"]),
    ("Why does this system use two separate machines?",
     [("t5810", r"t5810"), ("vram", r"vram")],
     [r"cross-compil", r"beelink"]),
    ("How fast is generation, in tokens per second?",
     # Require the CURRENT figure rather than forbidding the historical one: "moved from
     # 29.4 to 33.2" is a correct sentence and must not be flagged.
     [("current_throughput", r"33(\.\d)?\s*(tok|tokens)")],
     [r"6 tokens per second", r"enforce_eager"]),
    ("What was the payback period for the AVD migration?",
     [("six_months", r"(6|six)\s*month")],
     [r"(5|five)\s*month", r"\$?39k"]),
    ("Tell me about Chris's SAP Business One work.",
     [("warehouses", r"(6|six)\s*warehouse"), ("continents", r"(4|four)\s*continent")],
     [r"(5|five)\s*warehouse", r"five continents"]),
]

async def main(url, n):
    """Three outcomes, deliberately distinguished.

    FORBIDDEN  a known-wrong string appeared -> failure.
    UNSTABLE   runs produced DIFFERENT VALUES for the same fact (40 GB in one run, 56 GB in
               another) -> failure, and the signature of an intermittent defect.
    VARIABLE   a fact appeared in some runs and was simply ABSENT in others, never
               contradicted -> informational, NOT a failure.

    That last distinction was added after the first version reported the SAP question as
    unstable because one run gave a shorter answer that omitted the warehouse count. Across 21
    samples it never once gave a WRONG count. Answer length varies; that is not a defect, and
    a checker that calls it one trains you to ignore it -- the same alert-fatigue failure as
    DEFECT #8.
    """
    unstable, forbidden_hits, variable, errors = [], [], [], []
    for q, probes, forbidden in CASES:
        values = defaultdict(list)        # probe -> [matched value or None per run]
        hits = set()
        for i in range(n):
            r = await ask(url, q)
            a = (r.get("answer") or "").lower()
            if not a or a.startswith("[connection error") or a.startswith("[error"):
                errors.append((q, i + 1)); continue
            for label, rx in probes:
                m = re.search(rx, a)
                values[label].append(m.group(0).strip() if m else None)
            for f in forbidden:
                if re.search(f, a):
                    hits.add(f)
            await asyncio.sleep(0.5)

        # Contradiction = two runs produced DIFFERENT non-None values for the same fact.
        contradictions, absences = {}, {}
        for k, v in values.items():
            present = [x for x in v if x is not None]
            if len(set(present)) > 1:
                contradictions[k] = sorted(set(present))
            elif present and len(present) < len(v):
                absences[k] = f"{len(present)}/{len(v)}"

        if hits:
            status = "FORBIDDEN"; forbidden_hits.append((q, sorted(hits)))
            detail = "  forbidden: " + ",".join(sorted(hits))
        elif contradictions:
            status = "UNSTABLE"; unstable.append((q, contradictions))
            detail = "  conflicting: " + "; ".join(f"{k}={v}" for k, v in contradictions.items())
        elif absences:
            status = "VARIABLE"; variable.append((q, absences))
            detail = "  present in " + ", ".join(f"{k} {v}" for k, v in absences.items()) + " (no wrong value seen)"
        else:
            status = "OK"; detail = ""
        print(f"  [{status:9}] {q[:52]:52}{detail}")

    print(f"\n  questions: {len(CASES)}  runs each: {n}  total generations: {len(CASES)*n}")
    print(f"  FORBIDDEN (wrong value present):        {len(forbidden_hits)}")
    print(f"  UNSTABLE  (runs contradicted each other): {len(unstable)}")
    print(f"  VARIABLE  (omitted sometimes, never wrong): {len(variable)}  <- informational")
    print(f"  transport errors:                        {len(errors)}")
    if unstable:
        print("\n  UNSTABLE detail:")
        for q, c in unstable:
            for k, vals in c.items():
                print(f"    {q[:46]:46} {k}: {vals}")
    return 1 if (forbidden_hits or unstable) else 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="wss://dev.cwetzel.com/ws/chat")
    ap.add_argument("-n", type=int, default=5)
    a = ap.parse_args()
    print(f"Repeat-sampling {len(CASES)} questions x {a.n} runs against {a.url}\n")
    sys.exit(asyncio.run(main(a.url, a.n)))
