#!/usr/bin/env python3
"""
Consistency battery for the portfolio RAG chat — the k-sample harness for
stochastic generation defects.

Why this exists (DEFECT_LEDGER #1): the hallucination defect is STOCHASTIC at
temperature 0.2 — the same question, chunks, prompt and sampling answered
correctly and incorrectly an hour apart (2026-08-19). selftest.py asks each
question ONCE, so it cannot see this class: a probe that fails 1-in-5 passes a
single-sample gate 80% of the time. This harness asks each probe k times and
requires k/k deterministic substring checks to pass. No LLM judge — expect/forbid
string checks only, so the gate itself is deterministic and free.

Probes are the ledger's documented live failures, so a regression on any of them
means a known confabulation is back in production.

Usage:
    python3 scripts/consistency_battery.py                    # 6 probes x 5 samples
    python3 scripts/consistency_battery.py --samples 10
    python3 scripts/consistency_battery.py --url wss://localhost:8000/ws/chat
    python3 scripts/consistency_battery.py --threshold 0.8    # relax the k/k gate

Exit code 0 = every probe at/above the threshold; 1 = inconsistency detected.
"""
import argparse
import asyncio
import sys
from datetime import date

from run_diagnostic_battery import ask

# Chris's DOB, used to compute the age the chatbot SHOULD give right now, so the
# age probe never goes stale on his birthday. Mirrors OWNER_BIRTHDATE in
# cloud/api-proxy.py — keep them in sync.
OWNER_BIRTHDATE = date(1982, 1, 9)


def current_age() -> int:
    today = date.today()
    return today.year - OWNER_BIRTHDATE.year - (
        (today.month, today.day) < (OWNER_BIRTHDATE.month, OWNER_BIRTHDATE.day)
    )


# Each probe:
#   q          the exact question to ask
#   expect_any at least one of these (lowercased) must appear in the answer
#   forbid     none of these (lowercased) may appear — the documented confabulations
#   note       the live failure this probe guards (ledger reference)
def probes() -> list:
    age = str(current_age())
    return [
        {
            # 2026-08-22: answered "26 years old" — pattern-matched the KB's
            # "26 years of experience" onto age. Fixed by server-computed age
            # injection (server_facts_block).
            "q": "How old is Chris?",
            "expect_any": [age],
            "forbid": ["26 years old", "26-year-old", "born in 2000", "born 2000"],
            "note": "age confabulation (ledger #1)",
        },
        {
            # 2026-08-22: refused outright (education chunk never reached the
            # generator's context); 2026-08-21: invented "Rowan". Fixed via the
            # school/college/education alias group + resume wording.
            "q": "Where did Chris go to school?",
            "expect_any": ["college of new jersey", "tcnj"],
            "forbid": ["rowan"],
            "note": "education retrieval miss + Rowan confabulation",
        },
        {
            # 2026-08-19 ledger case B: answered "does not have onboard storage"
            # while the corrected chunk sat at rank 3 in context stating the
            # opposite. The cleanest generation-side isolation on record.
            "q": "Does the T5810 have onboard storage?",
            "expect_any": ["onboard storage"],
            "forbid": ["does not have onboard storage", "no onboard storage",
                       "relies on external"],
            "note": "T5810 storage negation (ledger #1, case B)",
        },
        {
            # 2026-08-19 ledger case A: invented a Realtek ALC892 codec and
            # 5600 MHz DDR4; the KB says Intel AX200 / I225-V.
            "q": "Tell me about the Asrock B550",
            "expect_any": ["b550"],
            "forbid": ["alc892", "5600"],
            "note": "Asrock spec-sheet confabulation (ledger #1, case A)",
        },
        {
            # 2026-08-29: answered "Bash" while RESUME.md states "Favorite
            # languages: Python and SQL". Same shape as the education miss — the
            # fact was indexed but unrankable: it sat inside the Automation &
            # Scripting skills list, so "favorite programming language" retrieved
            # tangential sysadmin chunks (top score 0.0587, resume absent from
            # top-5) and the model lifted "Bash" from one of them. Fixed with a
            # Preferences section high in the resume + a favorite/preferred alias
            # group. Bash and PowerShell are forbidden here precisely because they
            # ARE in the KB as scripting tools — the failure is preferring them.
            "q": "What is Chris's favorite programming language?",
            "expect_any": ["python"],
            "forbid": ["favorite programming language is bash",
                       "favorite language is bash",
                       "favorite programming language is powershell"],
            "note": "favorite-language confabulation (2026-08-29)",
        },
        {
            # 2026-07 live failure (golden-set regression item): invented
            # "40 GB of storage" (aggregate VRAM mislabeled) and "AMD GPUs".
            "q": "Tell me about the GPU home lab setup",
            "expect_any": ["a4500"],
            "forbid": ["gb of storage", "amd gpu", "both the nvidia and amd"],
            "note": "VRAM-as-storage confabulation (golden set)",
        },
        {
            # Control: a well-grounded question that should pass k/k. If THIS one
            # flakes, the problem is the pipeline, not any single fact.
            "q": "What GPUs does Chris run on his home server?",
            "expect_any": ["a4500"],
            "forbid": [],
            "note": "control probe — known-good retrieval",
        },
    ]


def check(answer: str, probe: dict):
    """Return (ok, detail). Deterministic substring checks only."""
    low = (answer or "").lower()
    if not low or low.startswith("[connection error") or low.startswith("[error"):
        return False, f"transport error: {(answer or 'empty')[:80]}"
    for bad in probe["forbid"]:
        if bad in low:
            return False, f"FORBIDDEN '{bad}': …{answer[:160]}"
    if probe["expect_any"] and not any(e in low for e in probe["expect_any"]):
        return False, f"missing {probe['expect_any']}: …{answer[:160]}"
    return True, "ok"


async def run(url: str, samples: int, threshold: float) -> bool:
    all_pass = True
    for probe in probes():
        fails = []
        for i in range(samples):
            result = await ask(url, probe["q"])
            ok, detail = check(result.get("answer", ""), probe)
            if not ok:
                fails.append((i + 1, detail))
        passed = samples - len(fails)
        rate = passed / samples
        status = "PASS" if rate >= threshold else "FAIL"
        if rate < threshold:
            all_pass = False
        print(f"[{status}] {passed}/{samples}  {probe['q']}")
        print(f"       guards: {probe['note']}")
        for n, detail in fails:
            print(f"       sample {n}: {detail}")
    return all_pass


def main():
    ap = argparse.ArgumentParser(description="k-sample consistency battery")
    ap.add_argument("--url", default="wss://dev.cwetzel.com/ws/chat")
    ap.add_argument("--samples", type=int, default=5,
                    help="repetitions per probe (default 5; k>=5 per ledger #1)")
    ap.add_argument("--threshold", type=float, default=1.0,
                    help="per-probe pass rate required (default 1.0 = k/k)")
    args = ap.parse_args()

    n = len(probes())
    print(f"Consistency battery: {n} probes x {args.samples} samples "
          f"= {n * args.samples} chats against {args.url}")
    print(f"Gate: each probe must pass >= {args.threshold:.0%}  (expected age today: {current_age()})\n")

    ok = asyncio.run(run(args.url, args.samples, args.threshold))
    print(f"\n=== CONSISTENCY {'PASSED' if ok else 'FAILED'} ===")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
