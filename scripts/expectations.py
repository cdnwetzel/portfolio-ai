"""Shared reading of the golden set's `expect_substrings`, for the two scripts that
disagreed about what it means.

THE BUG THIS FIXES. One field was being read with two incompatible semantics:

    eval_graded.py:131     any(s.lower() in low for s in expect)     -> ANY, against the ANSWER
    compare_retrieval.py:117  len(found) == len(expect)              -> ALL, against the CONTEXT

Both readings are defensible, because the lists themselves mean two different things:

    expect_substrings: ["A4500", "T5810"]   two FACTS, both of which should be present
    expect_substrings: ["6", "six"]         one fact, two SPELLINGS -- "six" is never in the KB

Under ALL-semantics the second shape can never score a full hit, so three golden items were
permanently pinned at "partial" and the headline retrieval recall had a hard ceiling of 33/36
(92%), not 100%. Every retrieval A/B -- including the three that were declined on evidence --
carried that dead weight. Under ANY-semantics the first shape is too easy: "A4500" alone
satisfies a question that asked for both.

The list format cannot tell the two apart, so the format grows one level:

    expect_substrings: ["A4500", "T5810"]       two facts, each with one spelling
    expect_substrings: [["6", "six"]]           ONE fact, two acceptable spellings
    expect_substrings: ["A4500", ["20 gb", "20gb"]]   mixed

A bare string is a one-spelling fact, so every existing entry keeps its current meaning.

This is the same lesson as `repeat_sample.py`'s move from substrings to regexes -- "encode the
claim, not the token". That fix was made in one harness on 2026-09-04 and never reached this
field, which is why "6 warehouse" missed every run that wrote "six warehouses" there while "six"
was simultaneously unmatchable here.

Stdlib only, so tests/ can cover it offline.
"""
from __future__ import annotations

import re


def normalize(expect) -> list[list[str]]:
    """-> one inner list per FACT, holding that fact's acceptable spellings (lowercased).

    Accepts a bare string, a flat list, or a list with nested alternative-groups.
    """
    if expect is None:
        return []
    if isinstance(expect, str):
        return [[expect.lower()]]
    facts: list[list[str]] = []
    for entry in expect:
        if isinstance(entry, str):
            facts.append([entry.lower()])
        else:
            # Filter BEFORE str(): str(None) is "none", a spelling that silently matches
            # any text containing the word "none" -- a vacuous fact, the exact shape of the
            # bug this module exists to remove. Caught by tests/test_expectations.py.
            spellings = [str(s).lower() for s in entry if isinstance(s, str) and s]
            if spellings:
                facts.append(spellings)
    return facts


def fact_present(spellings: list[str], haystack_lower: str) -> bool:
    """A fact is present if ANY of its spellings is."""
    return any(s in haystack_lower for s in spellings)


def any_fact_present(expect, haystack: str) -> bool | None:
    """ANY-of-facts. The answer-side check used by eval_graded.

    Returns None when nothing was expected, so "no expectation set" stays distinguishable
    from "expected something and missed it" -- the distinction its 1-5 ladder depends on.
    """
    facts = normalize(expect)
    if not facts:
        return None
    low = haystack.lower()
    return any(fact_present(f, low) for f in facts)


def facts_found(expect, haystack: str) -> tuple[int, int]:
    """(facts present, facts expected). The context-side check used by compare_retrieval:
    a full hit is every fact found, each by any one of its spellings."""
    facts = normalize(expect)
    low = haystack.lower()
    return sum(1 for f in facts if fact_present(f, low)), len(facts)


def missing_spellings(expect, corpus: str) -> list[str]:
    """Spellings that appear NOWHERE in `corpus` -- i.e. cannot be retrieved, only generated.

    Used to audit the golden set against the committed KB. A spelling missing here is fine
    as an answer-side alternative (the model may well write "six") but is dead weight for
    any context-side metric, so it must be an alternative and never a standalone fact.
    """
    low = corpus.lower()
    return [s for f in normalize(expect) for s in f if s not in low]

# --- forbid rules -----------------------------------------------------------
#
# A forbid entry is a NEGATIVE assertion: "this answer must not claim X". Until 2026-09-13 both
# harnesses matched it as a bare substring over the whole answer, which cannot tell a claim from
# a mention of its own history. The bare `3060` rule hard-failed an answer the judge scored 5/5,
# for the sentence "There is no RTX 3060 or 7B model in the current active system" -- the exact
# fact the rule exists to protect. Six rules across four golden questions have that collision,
# because the retirement notes live in `Current Work 2026`, which sits in the top-5 for all of
# them.
#
# Two entry shapes, so the cheap case stays cheap:
#
#   "gb of storage"                    plain string: substring anywhere. Unchanged.
#   {"match": "3060"}                  claim-shaped: scoped to ONE SENTENCE, and ignored if that
#                                      same sentence frames the mention as history.
#   {"match": "a4500", "unless": [..]} claim-shaped with an explicit exemption vocabulary.
#
# Sentence scoping is what makes this safe: "There is no RTX 3060 Ti" exempts itself, while
# "the judge runs on a 3060 Ti" in a different sentence still fails. A whole-answer exemption
# would let one correct retirement note launder a wrong claim elsewhere in the same answer.

RETIREMENT_FRAMES = (
    "retired", "replac", "no longer", "there is no", "there are no", "not in use",
    "isn't in use", "is not in use", "former", "previous", "earlier", "supersed",
    "removed", "decommission", "legacy", "used to", "prior to", "no rtx", "not part of",
)

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def split_sentences(text: str) -> list[str]:
    return [s for s in _SENT_SPLIT.split(text or "") if s.strip()]


def _present(needle: str, hay: str, use_regex: bool) -> bool:
    return bool(re.search(needle, hay, re.I)) if use_regex else needle.lower() in hay.lower()


def forbid_hit(entries, text: str, *, use_regex: bool = False):
    """-> the offending entry's match string, or None.

    `use_regex` is the default for PLAIN string entries: the golden set writes literals,
    repeat_sample.py writes regexes. A dict entry may override it with "regex".
    """
    if not entries:
        return None
    sentences = None
    for e in entries:
        if isinstance(e, str):
            match, unless, rx = e, None, use_regex
        else:
            # A dict entry is ALWAYS sentence-scoped. There is deliberately no dict spelling
            # for whole-answer matching -- the plain-string form is that. YAML cannot tell an
            # absent key from an explicit null, so both resolve to the default vocabulary
            # rather than silently meaning different things.
            match = e["match"]
            unless = tuple(e["unless"]) if e.get("unless") else RETIREMENT_FRAMES
            rx = e.get("regex", use_regex)
        if unless is None:
            if _present(match, text, rx):
                return match
            continue
        if sentences is None:
            sentences = split_sentences(text)
        for sent in sentences:
            if _present(match, sent, rx) and not any(_present(u, sent, False) for u in unless):
                return match
    return None
