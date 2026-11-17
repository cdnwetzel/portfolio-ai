#!/home/chris/miniforge3/bin/python3
"""
Reranker service — cross-encoder for RAG precision.

Sits between Qdrant retrieval and the LLM in the RAG pipeline. Qdrant's
bi-encoder cosine (bge-base-en-v1.5, 768-d) is fast but imprecise — good enough
to get the right chunk into the top-15, not precise enough to pick the best 5.
This cross-encoder re-scores (query, chunk) pairs with full cross-attention
and returns the best top_k.

Placement history: CPU-only on the T5810 (GPUs saturated by vLLM; ~3s per
query — the dominant retrieval term). Tier 3 moves it to the asrock's RTX
5060 Ti (~50-100ms per query) now that the verifier box has GPU headroom.

Env config (defaults preserve the original T5810 behavior exactly):
  RERANK_DEVICE   default "cpu". Set "cuda" on the asrock (Tier 3).
  RERANK_BIND     default 127.0.0.1. On the asrock, set the box's LAN IP so the
                  T5810's tunnel -L forward can reach it (mirrors VERIFIER_BIND).
  RERANK_PORT     default 8006.

Mirrors the embed-service pattern (port 8005).
"""
import os

from fastapi import FastAPI
from sentence_transformers import CrossEncoder
import uvicorn
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RERANK_DEVICE = os.environ.get("RERANK_DEVICE", "cpu")
RERANK_BIND = os.environ.get("RERANK_BIND", "127.0.0.1")
RERANK_PORT = int(os.environ.get("RERANK_PORT", "8006"))

app = FastAPI(title="Reranker Service")

# max_length=512 is the model's position-embedding limit; ~400-word chunks get
# their tail truncated, acceptable for relevance scoring (head carries signal).
# Device is env-driven: "cpu" on the T5810 (vLLM owns the VRAM), "cuda" on the
# asrock (Tier 3) — same model, same scores, different hardware.
model = CrossEncoder("BAAI/bge-reranker-base", max_length=512, device=RERANK_DEVICE)
logger.info(f"Reranker loaded on device={RERANK_DEVICE}")


@app.post("/rerank")
async def rerank(payload: dict):
    """Score (query, doc) pairs, return top_k original indices sorted by relevance."""
    query = payload.get("query", "")
    documents = payload.get("documents", [])
    top_k = payload.get("top_k", 5)

    if not query or not documents:
        return {"error": "query and documents required"}, 400

    scores = model.predict([(query, doc) for doc in documents])
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
    results = [{"index": int(i), "score": float(s)} for i, s in ranked]
    logger.info(f"Reranked {len(documents)} docs -> top {len(results)}")
    return {"results": results}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host=RERANK_BIND, port=RERANK_PORT, log_level="info")
