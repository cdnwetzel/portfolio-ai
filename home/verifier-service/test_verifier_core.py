"""Unit tests for the verifier's pure logic (no judge model needed)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from verifier_core import (
    strip_followups, is_refusal, parse_judge_claims, compute_verdict,
    build_judge_messages,
)


def test_strip_followups_removes_block_and_separator():
    text = 'Chris runs two A4500 GPUs.\n\n---\nFOLLOWUPS:["a","b","c"]'
    assert strip_followups(text) == "Chris runs two A4500 GPUs."


def test_strip_followups_noop_when_absent():
    assert strip_followups("Just an answer.") == "Just an answer."


def test_is_refusal():
    assert is_refusal("I don't have that documented in my knowledge base.")
    assert is_refusal("My knowledge base has conflicting information on this.")
    assert not is_refusal("Chris runs two A4500 GPUs.")


def test_parse_judge_claims_valid():
    content = '{"claims":[{"text":"two A4500s","verdict":"supported","source":1}]}'
    claims = parse_judge_claims(content)
    assert claims == [{"text": "two A4500s", "verdict": "supported", "source": 1}]


def test_parse_judge_claims_lenient_with_prose_wrapper():
    content = 'Sure! Here is the JSON:\n{"claims":[{"text":"x","verdict":"unsupported","source":null}]}\nDone.'
    claims = parse_judge_claims(content)
    assert claims == [{"text": "x", "verdict": "unsupported", "source": None}]


def test_parse_judge_claims_drops_invalid_verdict():
    content = '{"claims":[{"text":"a","verdict":"maybe"},{"text":"b","verdict":"supported"}]}'
    claims = parse_judge_claims(content)
    assert claims == [{"text": "b", "verdict": "supported", "source": None}]


def test_parse_judge_claims_unparseable_returns_none():
    assert parse_judge_claims("not json at all") is None
    assert parse_judge_claims('{"oops": true}') is None


def test_compute_verdict_all_supported_not_flagged():
    claims = [{"text": "a", "verdict": "supported", "source": 1},
              {"text": "b", "verdict": "supported", "source": 1}]
    v = compute_verdict(claims, threshold=0.8)
    assert v["faithfulness"] == 1.0
    assert v["flagged"] is False


def test_compute_verdict_below_threshold_flags():
    claims = [{"text": "a", "verdict": "supported", "source": 1},
              {"text": "b", "verdict": "unsupported", "source": None}]
    v = compute_verdict(claims, threshold=0.8)
    assert v["faithfulness"] == 0.5
    assert v["flagged"] is True


def test_compute_verdict_any_contradiction_flags_even_above_threshold():
    claims = ([{"text": f"s{i}", "verdict": "supported", "source": 1} for i in range(9)]
              + [{"text": "bad", "verdict": "contradicted", "source": 1}])
    v = compute_verdict(claims, threshold=0.8)
    assert v["faithfulness"] == 0.9          # above threshold
    assert v["n_contradicted"] == 1
    assert v["flagged"] is True              # but contradiction always flags


def test_compute_verdict_empty():
    v = compute_verdict([], threshold=0.8)
    assert v["faithfulness"] is None
    assert v["flagged"] is False


def test_build_judge_messages_numbers_chunks():
    msgs = build_judge_messages("q?", "a.", [{"title": "T", "source": "s", "content": "c"}])
    assert msgs[0]["role"] == "system"
    assert "[1] T (s)" in msgs[1]["content"]
    assert "QUERY: q?" in msgs[1]["content"]


def test_fixtures_file_is_well_formed():
    path = os.path.join(os.path.dirname(__file__), "fixtures.json")
    with open(path) as f:
        fx = json.load(f)
    assert len(fx) >= 5
    for case in fx:
        assert case["expected"]["verdict_type"] in ("judged", "refusal")
        # refusal fixtures must actually look like refusals to the core logic
        if case["expected"]["verdict_type"] == "refusal":
            assert is_refusal(case["answer"])
