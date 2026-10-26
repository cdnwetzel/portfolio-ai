"""Unit tests for the retrieval-relevance verification gate."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cloud"))

from verify_gate import should_verify


# --- must skip (low/irrelevant evidence) -----------------------------------------------
def test_skips_below_threshold():
    """Score below threshold always skips."""
    assert not should_verify(0.01, 0.05)


def test_skips_when_no_evidence():
    """Zero score (no chunks retrieved) skips."""
    assert not should_verify(0.0, 0.05)


def test_skips_when_score_none():
    """None score (missing evidence) skips."""
    assert not should_verify(None, 0.05)


def test_skips_well_below_threshold():
    """Regression: even a moderate score below threshold skips."""
    assert not should_verify(0.04, 0.05)


# --- must NOT skip (relevant evidence) -------------------------------------------------
def test_verifies_above_threshold():
    """Score strictly above threshold proceeds."""
    assert should_verify(0.10, 0.05)


def test_verifies_at_threshold():
    """Score exactly at threshold is inclusive (≥, not >)."""
    assert should_verify(0.05, 0.05)


def test_verifies_high_score():
    """High-confidence score always proceeds."""
    assert should_verify(0.08, 0.05)


def test_threshold_zero_allows_all():
    """Threshold of 0.0 allows any non-None score (gate disabled)."""
    assert should_verify(0.0, 0.0)
    assert should_verify(0.001, 0.0)
    assert should_verify(0.08, 0.0)
    assert not should_verify(None, 0.0)  # still skip on None
