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


def test_school_alias_group():
    # "school" must pull in the KB's own education vocabulary (2026-08-22 live
    # retrieval miss: "where did Chris go to school" never surfaced the resume's
    # Education chunk).
    terms = expansion_terms("where did chris go to school")
    assert "education" in terms
    assert "college" in terms
    assert "school" not in terms  # already in the query


def test_hindsight_vocabulary_reaches_the_lessons_content():
    # The KB writes its reflection as "Lessons Learned"; visitors ask "what would you do
    # differently". Measured 2026-09-13: unexpanded, that question's top rerank score was
    # 0.0031 -- below the 0.0046 lowest-on-topic floor in verify_gate.py -- with an unrelated
    # chunk at rank 1, so the model correctly refused a question the golden set marks grounded.
    out = expand_query("What would you do differently if you started over?").lower()
    assert "lessons learned" in out
    assert "retrospective" in out


def test_lessons_question_also_pulls_hindsight_terms():
    out = expand_query("What are the lessons learned from the AVD migration?").lower()
    assert "hindsight" in out
    assert "azure virtual desktop" in out          # existing avd group still fires


def test_hindsight_group_does_not_fire_on_unrelated_questions():
    out = expand_query("What GPUs does Chris run?").lower()
    for term in ("lessons learned", "hindsight", "retrospective", "mistakes"):
        assert term not in out
