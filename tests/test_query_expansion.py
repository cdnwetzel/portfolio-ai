"""Unit tests for the RAG query alias/expansion (rag-improvements.md §1.2)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cloud"))

from query_expansion import expand_query, expansion_terms, MAX_EXPANSION_TERMS


def test_noop_on_novel_vocabulary():
    q = "Tell me about quantum teapot calibration"
    assert expand_query(q) == q
    assert expansion_terms(q) == []


def test_expands_known_alias():
    terms = expansion_terms("what gpus does chris use")
    # 'gpus' is in the GPU group → should pull in siblings like 'a4500'
    assert "a4500" in terms
    assert "gpus" not in terms  # already in the query, not re-appended


def test_expanded_query_contains_original():
    q = "how does the rag pipeline work"
    out = expand_query(q)
    assert out.startswith(q)
    assert len(out) > len(q)
    assert "retrieval augmented generation" in out


def test_word_boundary_prevents_false_match():
    # 'dr' (disaster recovery alias) must NOT trigger inside 'address' / 'andrew'
    assert expansion_terms("what is andrew's address") == []


def test_short_token_b1_matches_only_whole():
    # 'b1' should not trigger on 'b12' or 'sb1'
    assert expansion_terms("the b12 vitamin") == []
    terms = expansion_terms("tell me about sap b1")
    assert "sap business one" in terms


def test_expansion_is_capped():
    # A query touching several groups must still respect the cap.
    q = "rag llm gpu vllm qdrant reranker embedding lora soc2 avd"
    assert len(expansion_terms(q)) <= MAX_EXPANSION_TERMS


def test_no_duplicate_terms():
    terms = expansion_terms("vllm inference server")
    assert len(terms) == len(set(terms))
    # 'inference server' already present, so it isn't re-added
    assert "inference server" not in terms
