"""
Dependency-free BM25 sparse vectors for hybrid retrieval (rag-improvements.md §2.1).

Dense cosine misses exact/rare terms (names, codenames, error strings). A sparse BM25
vector alongside the dense vector, fused in Qdrant's Query API (RRF), recovers them.

Design that avoids any query-time corpus state (no IDF table to ship to the proxy):
  * Deterministic hashed vocabulary (token -> index in SPARSE_DIM) — same hash on both
    the indexer and the proxy, no shared vocab file.
  * IDF is baked into the DOCUMENT vector at index time (BM25 doc-side weighting).
  * The QUERY vector is just presence (1.0) per unique term.
  * Qdrant sparse dot-product = sum over shared terms of (doc BM25 weight x 1.0),
    i.e. a BM25-style score — computed without IDF at query time.

Pure stdlib so it imports on both the cloud proxy and the T5810 indexer, and unit-tests
without any service.
"""
import math
import re
from typing import Dict, List, Tuple

SPARSE_DIM = 1 << 20          # hashed vocabulary space (~1M); collisions negligible for a small KB
K1 = 1.5
B = 0.75

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "for", "on",
    "with", "that", "this", "it", "as", "at", "be", "by", "from", "was", "were",
    "what", "how", "does", "do", "you", "your", "i", "me", "my",
}


def tokenize(text: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if len(t) > 1 and t not in _STOP]


def hash_token(tok: str) -> int:
    """Deterministic token -> index (Python's hash() is per-process salted, unusable here)."""
    h = 2166136261
    for ch in tok:
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h % SPARSE_DIM


def build_idf(corpus_tokens: List[List[str]]) -> Tuple[Dict[int, float], float]:
    """Return (idf by token-index, average document length) over the tokenized corpus."""
    n_docs = len(corpus_tokens) or 1
    df: Dict[int, int] = {}
    total_len = 0
    for toks in corpus_tokens:
        total_len += len(toks)
        for idx in {hash_token(t) for t in toks}:
            df[idx] = df.get(idx, 0) + 1
    idf = {idx: math.log(1 + (n_docs - n + 0.5) / (n + 0.5)) for idx, n in df.items()}
    avgdl = (total_len / n_docs) if n_docs else 1.0
    return idf, max(avgdl, 1.0)


def encode_doc(tokens: List[str], idf: Dict[int, float], avgdl: float) -> Dict[str, list]:
    """BM25 doc-side sparse vector {indices, values}. IDF baked in here."""
    tf: Dict[int, int] = {}
    for t in tokens:
        idx = hash_token(t)
        tf[idx] = tf.get(idx, 0) + 1
    dl = len(tokens) or 1
    indices, values = [], []
    for idx, f in tf.items():
        w = idf.get(idx, 0.0) * (f * (K1 + 1)) / (f + K1 * (1 - B + B * dl / avgdl))
        if w > 0.0:
            indices.append(idx)
            values.append(round(w, 6))
    return {"indices": indices, "values": values}


def encode_query(text: str) -> Dict[str, list]:
    """Query-side sparse vector: presence (1.0) per unique term (IDF already in doc weights)."""
    idxs = sorted({hash_token(t) for t in tokenize(text)})
    return {"indices": idxs, "values": [1.0] * len(idxs)}
