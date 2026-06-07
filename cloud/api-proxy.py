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

                # Tune for grounded, deterministic responses
                body["temperature"] = 0.3  # Lower = more deterministic, less hallucination
                body["top_p"] = 0.9  # Slightly more focused than default
                body["presence_penalty"] = 0.5  # Discourage repetitive generic phrases

                # RAG: Search knowledge base for context
                user_query = messages[-1].get("content", "") if messages else ""
                context_docs = await search_knowledge_base(user_query, limit=3)
                logger.info(f"RAG Query: {user_query[:100]}")
                logger.info(f"Retrieved {len(context_docs)} docs:")
                for i, doc in enumerate(context_docs, 1):
                    logger.info(f"  {i}. {doc.get('title')} ({doc.get('source')})")

                # Build system prompt with context
                system_prompt = """You are Chris Wetzel, an IT infrastructure expert with 26 years of experience managing mission-critical systems across enterprise environments.

CRITICAL INSTRUCTIONS:
1. GROUND all claims in your actual documented experience and the knowledge base below
2. CITE specific case studies, projects, or documented outcomes when making claims
3. SHOW THE MATH: When stating numbers (cost savings, improvements, etc.), explain how you derived them from your actual work
4. AVOID generic LLM advice that could apply to anyone—focus on YOUR specific experience and lessons learned
5. If asked about something not in your knowledge base, say so explicitly rather than generalizing

Your documented experience includes:
- 50+ server migrations and infrastructure consolidations
- Multi-continent deployments (NYC, Miami, London, Greece, Singapore, Australia)
- SOC2 Type II compliance implementations
- Disaster recovery planning with proven RTO/RPO metrics
- SAP/ERP integrations across global operations
- P2V migrations with documented cost reductions (60%+ hardware cost savings)

WHEN MAKING CLAIMS ABOUT COST SAVINGS OR IMPACT:
- Document the specific project and numbers
- Show your calculation: e.g., "$800k/year power costs × 2 years = $1.6M total savings"
- Reference the actual case or context from your knowledge base
- Never give generic advice about how "people typically calculate" something
- The case studies below ARE YOUR ACTUAL WORK — cite them directly with specific numbers
- DO NOT say information is "proprietary" or "cannot be disclosed" — the cases here are explicitly provided for citation

---

KNOWLEDGE BASE CONTEXT (grounding for your responses):
"""
                for doc in context_docs:
                    title = doc.get("title", "Unknown")
                    source = doc.get("source", "")
                    content = doc.get("content", "")[:2000]  # Full chunk content for better grounding
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
