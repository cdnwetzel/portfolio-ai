"""Unit tests for the golden set's expect_substrings semantics (scripts/expectations.py).

The defect these pin: one YAML field was read as ANY-of-strings against the answer by
eval_graded.py and as ALL-of-strings against the retrieved context by compare_retrieval.py.
Lists like ["6", "six"] are alternative SPELLINGS of one fact, so under ALL-semantics three
golden items could never score a full hit and the retrieval metric's ceiling was 33/36.
Lists like ["A4500", "T5810"] are two FACTS, so under ANY-semantics half an answer passes.
"""
import importlib.util
import os

_PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "expectations.py")
_spec = importlib.util.spec_from_file_location("expectations", _PATH)
E = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(E)


# --- normalize: a bare string is a one-spelling fact; nesting marks alternatives ---

def test_flat_list_is_one_fact_per_string():
    assert E.normalize(["A4500", "T5810"]) == [["a4500"], ["t5810"]]


def test_nested_list_is_one_fact_with_alternatives():
    assert E.normalize([["6", "six"]]) == [["6", "six"]]


def test_mixed_shapes_coexist():
    assert E.normalize(["A4500", ["20 gb", "20gb"]]) == [["a4500"], ["20 gb", "20gb"]]


def test_bare_string_and_none():
    assert E.normalize("A4500") == [["a4500"]]
    assert E.normalize(None) == []
    assert E.normalize([]) == []


def test_empty_alternatives_are_dropped_not_kept_as_a_vacuous_fact():
    # A fact with no spellings could never be satisfied, which is the exact shape of the
    # bug being fixed — so it must not survive normalization.
    assert E.normalize(["A4500", []]) == [["a4500"]]
    assert E.normalize([["", None]]) == []


# --- answer side: ANY-of-facts, preserving eval_graded's existing behaviour ---

def test_any_fact_present_matches_a_single_fact():
    assert E.any_fact_present(["A4500", "T5810"], "runs on two A4500 cards") is True


def test_any_fact_present_is_case_insensitive():
    assert E.any_fact_present(["a4500"], "Two RTX A4500 GPUs") is True


def test_any_fact_present_false_when_nothing_matches():
    assert E.any_fact_present(["A4500"], "no GPUs documented") is False


def test_any_fact_present_none_when_nothing_expected():
    # None, not False: the 1-5 ladder distinguishes "no expectation set" (score 4) from
    # "expected a known fact and missed it" (score 2).
    assert E.any_fact_present(None, "anything") is None
    assert E.any_fact_present([], "anything") is None


def test_alternative_spellings_both_satisfy_the_answer_check():
    for phrasing in ("6 warehouses", "six warehouses"):
        assert E.any_fact_present([["6 warehouse", "six warehouse"]], phrasing) is True


# --- context side: ALL facts, each by any one spelling ---

def test_facts_found_requires_every_fact():
    assert E.facts_found(["A4500", "T5810"], "two A4500 cards") == (1, 2)
    assert E.facts_found(["A4500", "T5810"], "A4500 cards in the T5810") == (2, 2)


def test_alternatives_count_as_one_satisfied_fact_either_way():
    # The regression: the KB only ever writes the digit, so ["6","six"] read as two facts
    # capped this row at partial forever.
    assert E.facts_found([["6", "six"]], "6 warehouses") == (1, 1)
    assert E.facts_found([["6", "six"]], "six warehouses") == (1, 1)


def test_alternatives_unsatisfied_when_no_spelling_present():
    assert E.facts_found([["6 warehouse", "six warehouse"]], "several depots") == (0, 1)


def test_facts_found_on_empty_expectation():
    assert E.facts_found(None, "text") == (0, 0)


# --- the audit helper that found the dead weight ---

def test_missing_spellings_reports_only_what_the_corpus_lacks():
    corpus = "the KB says 6 warehouses spanning 4 continents"
    assert E.missing_spellings([["6 warehouse", "six warehouse"]], corpus) == ["six warehouse"]


def test_missing_spellings_empty_when_all_present():
    assert E.missing_spellings(["a4500"], "two A4500 cards") == []


# --- forbid rules: claim-shaped, sentence-scoped -----------------------------
#
# The defect these pin: a bare `3060` forbid hard-failed an answer the judge scored 5/5,
# because the answer contained "There is no RTX 3060 or 7B model in the current active
# system" -- the very fact the rule exists to protect. Six such rules across four golden
# questions had the same collision, since the retirement notes live in a chunk that sits in
# the top-5 for all of them.

RETIRED_OK = "There is no RTX 3060 or 7B model in the current active system."
PAST_OK = "It replaced an earlier Qwen2.5-7B on a 3060 Ti 8 GB."
REAL_DEFECT = "The faithfulness judge runs on a 3060 Ti in the asrock B550."


def test_plain_string_entry_is_unchanged_substring_match():
    assert E.forbid_hit(["gb of storage"], "it has 40 GB of storage") == "gb of storage"
    assert E.forbid_hit(["gb of storage"], "it has 40 GB of VRAM") is None


def test_plain_string_entry_is_not_sentence_scoped():
    # Whole-answer substring semantics, deliberately preserved for the 13 rules that want it.
    assert E.forbid_hit(["amd gpu"], "First sentence. Then an amd gpu claim.") == "amd gpu"


def test_claim_shaped_entry_exempts_a_correct_retirement_sentence():
    assert E.forbid_hit([{"match": "3060"}], RETIRED_OK) is None
    assert E.forbid_hit([{"match": "3060"}], PAST_OK) is None


def test_claim_shaped_entry_still_catches_the_real_defect():
    assert E.forbid_hit([{"match": "3060"}], REAL_DEFECT) == "3060"


def test_a_correct_note_cannot_launder_a_wrong_claim_elsewhere():
    # Scoping to ONE sentence is the whole point: a whole-answer exemption would let the
    # retirement note excuse a wrong claim in a different sentence of the same answer.
    assert E.forbid_hit([{"match": "3060"}], RETIRED_OK + " " + REAL_DEFECT) == "3060"


def test_explicit_unless_vocabulary_overrides_the_default():
    s = "The A4500s are in the T5810, not the verifier box."
    assert E.forbid_hit([{"match": "a4500"}], s) == "a4500"          # default frames don't cover it
    assert E.forbid_hit([{"match": "a4500", "unless": ["t5810", "not"]}], s) is None


def test_explicit_null_unless_is_the_same_as_omitting_it():
    # A dict entry ALWAYS means sentence-scoped; there is no dict spelling for whole-answer,
    # because the plain-string form already is that. YAML cannot distinguish an absent key
    # from an explicit null, so both must mean the same thing or the format is a trap.
    assert E.forbid_hit([{"match": "3060", "unless": None}], RETIRED_OK) is None
    assert E.forbid_hit([{"match": "3060"}], RETIRED_OK) is None
    assert E.forbid_hit([{"match": "3060", "unless": None}], REAL_DEFECT) == "3060"


def test_regex_mode_for_repeat_sample_entries():
    pat = r"qwen2\.5[- ]7b"
    assert E.forbid_hit([{"match": pat, "regex": True}], "It runs Qwen2.5-7B today.") == pat
    assert E.forbid_hit([{"match": pat, "regex": True}], "That Qwen2.5 7B is retired.") is None


def test_use_regex_default_applies_to_plain_entries():
    assert E.forbid_hit([r"\b40\s*gb\b"], "it has 40 GB", use_regex=True) == r"\b40\s*gb\b"
    assert E.forbid_hit([r"\b40\s*gb\b"], "it has 40 GB", use_regex=False) is None


def test_empty_and_missing_entries():
    assert E.forbid_hit([], "anything") is None
    assert E.forbid_hit(None, "anything") is None


def test_first_matching_entry_wins_and_is_returned():
    hit = E.forbid_hit(["nope", {"match": "3060"}], REAL_DEFECT)
    assert hit == "3060"
