"""Pure logic for gating faithfulness verification on retrieval relevance.

When the top evidence chunk scores below a relevance threshold, skip verification
entirely — the retrieved chunks are too off-topic to make a faithfulness judgment
meaningful. This prevents false-positive flags on answers to off-topic (non-KB)
questions where Qdrant still returns its top-K nearest vectors, but they're
semantically unrelated to the query/answer domain.

Kept dependency-free and separate so it can be unit-tested without any I/O.
"""


def should_verify(top_score: float | None, threshold: float) -> bool:
    """True if the top retrieval score passes the relevance threshold.

    Args:
        top_score: The rerank (bge-reranker-base) score of the highest-scoring evidence chunk,
                   or None/0.0 if no chunks were retrieved. Measured distribution (2026-07-14,
                   golden_set + off-topic probes against the live index): on-topic top-scores
                   span ~0.005–0.995 (median ~0.40); off-topic cluster tightly at ~0 (max 0.017).
                   NOT the "0.0–0.08" once assumed — the scores use nearly the full 0–1 range.
        threshold: Minimum score to consider evidence relevant enough to judge. Production runs
                   VERIFY_MIN_SCORE=0.002, chosen to gate the clear off-topic cluster (scores ~0)
                   with zero on-topic false-skips (lowest measured on-topic top-score was 0.0046).

    Returns:
        False when top_score is None/missing or below threshold (skip verification).
        True when top_score meets or exceeds threshold (proceed with judge call).

    Example:
        >>> should_verify(0.40, 0.002)   # typical on-topic
        True
        >>> should_verify(0.0003, 0.002) # typical off-topic
        False
        >>> should_verify(None, 0.002)
        False
    """
    return top_score is not None and top_score >= threshold
