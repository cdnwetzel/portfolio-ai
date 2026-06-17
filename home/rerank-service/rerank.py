#!/home/chris/miniforge3/bin/python3
"""
Reranker service — CPU cross-encoder for RAG precision.

Sits between Qdrant retrieval and the LLM in the RAG pipeline. Qdrant's
bi-encoder cosine (MiniLM, 384-d) is fast but imprecise — good enough to get
the right chunk into the top-20, not precise enough to pick the best 3-5.
This cross-encoder re-scores (query, chunk) pairs with full cross-attention
and returns the best top_k.

Runs CPU-only (device="cpu") ON PURPOSE: the GPUs are saturated by vLLM, and
the T5810 has 256GB idle DDR4. Reranking 20 candidates measures ~0.33s on CPU,
negligible next to generation. Mirrors the embed-service pattern (port 8005).
"""
from fastapi import FastAPI
from sentence_transformers import CrossEncoder
import uvicorn
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Reranker Service")

# CPU-pinned — must NOT compete with vLLM for VRAM. bge-reranker-base (278M).
# max_length=512 is the model's position-embedding limit; ~400-word chunks get
# their tail truncated, acceptable for relevance scoring (head carries signal).
model = CrossEncoder("BAAI/bge-reranker-base", max_length=512, device="cpu")


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
    uvicorn.run(app, host="127.0.0.1", port=8006, log_level="info")
