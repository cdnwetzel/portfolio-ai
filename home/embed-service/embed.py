#!/home/chris/miniforge3/bin/python3
"""
Embedding service — CPU bge-base-en-v1.5 for the RAG pipeline.

Embeds incoming chat queries to 768-dim vectors for Qdrant cosine search. The
indexer (scripts/index_with_embeddings.py) uses the same model, so index vectors
match query vectors. No query/passage instruction prefix is used — index and query
are embedded identically, which keeps them consistent (the reranker then refines).
Runs CPU-only on the T5810 (vLLM owns the GPUs). Mirrors the reranker service
pattern (port 8006); this is port 8005.
"""
from fastapi import FastAPI
from sentence_transformers import SentenceTransformer
import uvicorn
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Embedding Service")
model = SentenceTransformer('BAAI/bge-base-en-v1.5', device='cpu')  # CPU-only; vLLM owns the GPUs

@app.post("/embed")
async def embed(payload: dict):
    text = payload.get("text", "")
    if not text:
        return {"error": "text field required"}, 400

    vector = model.encode(text).tolist()
    logger.info(f"Embedded query ({len(text)} chars) -> {len(vector)} dims")
    return {"embedding": vector, "dims": len(vector)}

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8005, log_level="info")
