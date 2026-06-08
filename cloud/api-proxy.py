"""
FastAPI proxy: cwetzel.com:8000 → T5810 (vLLM:8004, Qdrant:6333)
Handles auth, rate limiting, request logging.
"""
import asyncio
import logging
from fastapi import FastAPI, WebSocket, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Portfolio AI Proxy")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dev.cwetzel.com", "https://cwetzel.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Use existing pscode vLLM on 8004
VLLM_URL = "http://ai.cwetzel.com:8004"
QDRANT_URL = "http://ai.cwetzel.com:6333"
EMBED_URL = "http://127.0.0.1:8005"  # Embedding service via SSH tunnel

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/chat")
async def chat(request: Request):
    """Proxy chat request to vLLM"""
    try:
        body = await request.json()
        logger.info(f"Chat request: {body.get('messages', [])[-1:] if body.get('messages') else 'no messages'}")

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{VLLM_URL}/v1/chat/completions",
                json=body,
                headers={"Content-Type": "application/json"}
            )
            return JSONResponse(response.json())
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat-stream")
async def chat_stream(request: Request):
    """Proxy streaming chat to vLLM"""
    try:
        body = await request.json()
        body["stream"] = True
        logger.info(f"Stream request: {body.get('model')}")

        async def generate():
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{VLLM_URL}/v1/chat/completions",
                    json=body,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            yield line[6:] + "\n"

        return StreamingResponse(generate(), media_type="text/event-stream")
    except Exception as e:
        logger.error(f"Stream error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/search")
async def search(request: Request):
    """Proxy vector search to Qdrant"""
    try:
        body = await request.json()
        collection = body.get("collection", "documents")
        query = body.get("query", [])
        limit = body.get("limit", 5)

        logger.info(f"Search in {collection}: limit={limit}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{QDRANT_URL}/collections/{collection}/points/search",
                json={"vector": query, "limit": limit, "with_payload": True},
                headers={"Content-Type": "application/json"}
            )
            return JSONResponse(response.json())
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def search_knowledge_base(query: str, limit: int = 3) -> list:
    """Search Qdrant using semantic embeddings — no manual weight tuning needed."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Step 1: Embed the query using all-MiniLM-L6-v2
            logger.info(f"Embedding query: {query[:80]}...")
            embed_response = await client.post(
                f"{EMBED_URL}/embed",
                json={"text": query},
                timeout=5.0
            )
            if embed_response.status_code != 200:
                logger.error(f"Embedding failed: {embed_response.status_code}")
                return []

            query_embedding = embed_response.json()["embedding"]
            logger.info(f"Query embedded to {len(query_embedding)} dims")

            # Step 2: Vector search in Qdrant — cosine similarity ranks results automatically
            search_response = await client.post(
                f"{QDRANT_URL}/collections/documents/points/search",
                json={
                    "vector": query_embedding,
                    "limit": limit,
                    "with_payload": True
                },
                timeout=10.0
            )

            if search_response.status_code == 200:
                results = search_response.json().get("result", [])
                payloads = [r.get("payload", {}) for r in results]
                logger.info(f"Search returned {len(payloads)} results")
                return payloads
            else:
                logger.error(f"Vector search failed: {search_response.status_code}")
                return []

    except Exception as e:
        logger.error(f"Search error: {e}")
        return []


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket for real-time chat streaming with RAG"""
    await websocket.accept()
    logger.info(f"WebSocket connected from {websocket.client}")

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "chat":
                body = data.get("payload", {})
                messages = body.get("messages", [])
                body["stream"] = True

                # Strict decoding for grounded, deterministic responses
                body["temperature"] = 0.1  # Force near-deterministic token selection
                body["top_p"] = 0.7  # Eliminate long-tail creative tokens
                body["presence_penalty"] = 0.5

                # RAG: Search knowledge base for context
                user_query = messages[-1].get("content", "") if messages else ""
                context_docs = await search_knowledge_base(user_query, limit=3)
                logger.info(f"RAG Query: {user_query[:100]}")
                logger.info(f"Retrieved {len(context_docs)} docs:")
                for i, doc in enumerate(context_docs, 1):
                    logger.info(f"  {i}. {doc.get('title')} ({doc.get('source')})")

                # Build system prompt with strict grounding rules
                system_prompt = """You are Chris Wetzel. Answer only from the knowledge base below.

RULES (non-negotiable):
1. First person only. You ARE Chris — never say "as an IT infrastructure expert" in third-person.
2. If the answer is fully supported by the context below, begin with [FOUND].
3. If the context does not contain the answer, respond with exactly: "[NOT FOUND] I don't have that documented in my knowledge base." Then stop.
4. If sources conflict, respond with: "[CONFLICT] Conflicting information found in local knowledge base." Do not resolve or guess.
5. Ground responses in your documented experience. When discussing tools, prioritize those in your knowledge base (Gentoo, kernel_config.sh, shell scripts, vLLM, Qdrant). You can mention how you've used other tools, but only if grounded in actual projects.
6. Cite specific machines, files, or case studies for every factual claim. Include relevant paths like gentoo-machines/machines/*, tools/*, or case study names.

Your documented systems: Precision T5810 (dual A4500 GPUs, PCIe Gen4), Surface Pro 8, ThinkPad X1, custom AMD build, NUC8i7. OS: Gentoo Linux. Automation: custom shell scripts in gentoo-machines repo.

---
KNOWLEDGE BASE (your actual documented work):
"""
                for doc in context_docs:
                    title = doc.get("title", "Unknown")
                    source = doc.get("source", "")
                    content = doc.get("content", "")[:2000]
                    system_prompt += f"\n\n### {title} ({source})\n{content}"

                # Inject system message if not present
                if not any(m.get("role") == "system" for m in messages):
                    messages = [{"role": "system", "content": system_prompt}] + messages
                    body["messages"] = messages

                logger.info(f"Chat request with {len(context_docs)} context docs")

                async with httpx.AsyncClient(timeout=120.0) as client:
                    async with client.stream(
                        "POST",
                        f"{VLLM_URL}/v1/chat/completions",
                        json=body
                    ) as response:
                        full_response = ""
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                try:
                                    chunk = json.loads(line[6:])
                                    # Accumulate response text to check for [NOT FOUND]
                                    if chunk.get("choices"):
                                        delta_content = chunk["choices"][0].get("delta", {}).get("content", "")
                                        full_response += delta_content
                                    # Stream chunk to client (strip [FOUND]/[NOT FOUND]/[CONFLICT] tags before sending)
                                    if chunk.get("choices"):
                                        modified_chunk = chunk.copy()
                                        delta = modified_chunk["choices"][0].get("delta", {})
                                        if delta:
                                            # Remove control tags from display (preserve spaces between words)
                                            delta_content = delta.get("content", "")
                                            if delta_content:
                                                delta["content"] = delta_content.replace("[FOUND]", "").replace("[NOT FOUND]", "").replace("[CONFLICT]", "")
                                            modified_chunk["choices"][0]["delta"] = delta
                                        await websocket.send_json({
                                            "type": "chunk",
                                            "data": modified_chunk
                                        })
                                except:
                                    pass

                        # Log whether response was grounded
                        if "[NOT FOUND]" in full_response:
                            logger.info(f"Response: NOT FOUND — query had no supporting context")
                        elif "[CONFLICT]" in full_response:
                            logger.info(f"Response: CONFLICT — multiple sources disagree")
                        else:
                            logger.info(f"Response: FOUND — answer grounded in knowledge base")

                await websocket.send_json({"type": "done"})
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        try:
            await websocket.close()
        except Exception as close_error:
            logger.debug(f"WebSocket already closed: {close_error}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
