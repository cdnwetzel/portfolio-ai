"""Unit tests for the BM25 sparse encoder (rag-improvements.md §2.1)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cloud"))

from sparse_bm25 import (
    tokenize, hash_token, build_idf, encode_doc, encode_query, SPARSE_DIM,
)


def test_tokenize_drops_stopwords_and_short():
    toks = tokenize("What GPUs does Chris run on the T5810?")
    assert "gpus" in toks and "chris" in toks and "t5810" in toks
    assert "the" not in toks and "on" not in toks


def test_hash_token_deterministic_and_in_range():
    assert hash_token("qdrant") == hash_token("qdrant")
    assert hash_token("qdrant") != hash_token("vllm")
    assert 0 <= hash_token("anything") < SPARSE_DIM


def test_build_idf_rare_term_weighted_higher():
    corpus = [tokenize("qdrant vector database"),
              tokenize("vector search engine"),
              tokenize("vector store index")]
    idf, avgdl = build_idf(corpus)
    # 'qdrant' appears in 1 doc, 'vector' in all 3 → qdrant has higher idf
    assert idf[hash_token("qdrant")] > idf[hash_token("vector")]
    assert avgdl >= 1.0


def test_encode_doc_returns_sparse_pairs():
    corpus = [tokenize("qdrant vector database"), tokenize("vllm inference server")]
    idf, avgdl = build_idf(corpus)
    vec = encode_doc(tokenize("qdrant vector database"), idf, avgdl)
    assert len(vec["indices"]) == len(vec["values"]) > 0
    assert all(v > 0 for v in vec["values"])


def test_query_doc_dot_product_scores_match():
    # A doc sharing a rare query term should outscore one that doesn't.
    corpus = [tokenize("the chris portfolio uses qdrant for retrieval"),
              tokenize("the azure virtual desktop migration for users"),
              tokenize("disaster recovery planning and backups")]
    idf, avgdl = build_idf(corpus)
    docs = [encode_doc(t, idf, avgdl) for t in corpus]
    q = encode_query("what vector database qdrant")

    def dot(qv, dv):
        dmap = dict(zip(dv["indices"], dv["values"]))
        return sum(dmap.get(i, 0.0) * v for i, v in zip(qv["indices"], qv["values"]))

    scores = [dot(q, d) for d in docs]
    assert scores[0] == max(scores) and scores[0] > 0  # the qdrant doc wins


def test_query_with_no_overlap_scores_zero():
    corpus = [tokenize("qdrant vector database")]
    idf, avgdl = build_idf(corpus)
    d = encode_doc(corpus[0], idf, avgdl)
    q = encode_query("completely unrelated banana terms")
    dmap = dict(zip(d["indices"], d["values"]))
    score = sum(dmap.get(i, 0.0) * v for i, v in zip(q["indices"], q["values"]))
    assert score == 0.0
