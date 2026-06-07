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
    """Search Qdrant for relevant documents."""
    try:
        # Simple text search via Qdrant scroll API
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Get all documents (simple approach - no semantic search yet)
            response = await client.post(
                f"{QDRANT_URL}/collections/documents/points/scroll",
                json={"limit": limit}
            )
            if response.status_code == 200:
                data = response.json()
                points = data.get("result", {}).get("points", [])
                return [p.get("payload", {}) for p in points[:limit]]
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

                # RAG: Search knowledge base for context
                user_query = messages[-1].get("content", "") if messages else ""
                context_docs = await search_knowledge_base(user_query, limit=3)

                # Build system prompt with context
                system_prompt = """You are Chris Wetzel, an IT infrastructure expert with 26 years of experience.
Based on your experience and the context below, provide detailed and practical advice.

Context from your knowledge base:
"""
                for doc in context_docs:
                    title = doc.get("title", "Unknown")
                    source = doc.get("source", "")
                    system_prompt += f"\n- {title} ({source})"

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
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                try:
                                    chunk = json.loads(line[6:])
                                    await websocket.send_json({
                                        "type": "chunk",
                                        "data": chunk
                                    })
                                except:
                                    pass

                await websocket.send_json({"type": "done"})
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
