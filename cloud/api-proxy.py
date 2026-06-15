"""
FastAPI proxy: cwetzel.com:8000 → T5810 (vLLM:8004, Qdrant:6333, embeddings:8005)
WebSocket chat with RAG pipeline: embed → Qdrant search → vLLM stream.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import json
from datetime import datetime
from context_manager import compact_history, inject_system_prompt, prompt_too_long, MAX_PROMPT_CHARS, MAX_HISTORY_CHARS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VLLM_URL  = "http://127.0.0.1:8004"
QDRANT_URL = "http://127.0.0.1:6333"
EMBED_URL  = "http://127.0.0.1:8005"

# Persistent client — avoids TCP hand-shake overhead on every request
_http: httpx.AsyncClient | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http
    _http = httpx.AsyncClient(timeout=120.0)
    yield
    await _http.aclose()

app = FastAPI(title="Portfolio AI Proxy", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dev.cwetzel.com", "https://cwetzel.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/search")
async def search(request: Request):
    """Proxy vector search to Qdrant"""
    try:
        body = await request.json()
        collection = body.get("collection", "documents")
        query = body.get("query", [])
        limit = body.get("limit", 5)
        logger.info(f"Search in {collection}: limit={limit}")
        response = await _http.post(
            f"{QDRANT_URL}/collections/{collection}/points/search",
            json={"vector": query, "limit": limit, "with_payload": True},
            headers={"Content-Type": "application/json"}
        )
        return JSONResponse(response.json())
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def search_knowledge_base(query: str, limit: int = 3) -> list:
    """Embed query then vector-search Qdrant. Uses persistent httpx client."""
    try:
        # Embed
        embed_resp = await _http.post(
            f"{EMBED_URL}/embed",
            json={"text": query},
            timeout=10.0
        )
        if embed_resp.status_code != 200:
            logger.error(f"Embedding failed: {embed_resp.status_code}")
            return []

        query_embedding = embed_resp.json()["embedding"]
        logger.info(f"Query embedded ({len(query_embedding)} dims)")

        # Search
        search_resp = await _http.post(
            f"{QDRANT_URL}/collections/documents/points/search",
            json={"vector": query_embedding, "limit": limit, "with_payload": True},
            timeout=10.0
        )
        if search_resp.status_code != 200:
            logger.error(f"Vector search failed: {search_resp.status_code}")
            return []

        results = search_resp.json().get("result", [])
        payloads = [r.get("payload", {}) for r in results]
        logger.info(f"Search returned {len(payloads)} results")
        return payloads

    except Exception as e:
        logger.error(f"Search error: {e}")
        return []


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket: real-time chat streaming with RAG"""
    await websocket.accept()
    logger.info(f"WebSocket connected from {websocket.client}")

    try:
        while True:
            try:
                data = await websocket.receive_json()
                logger.info(f"Received message type: {data.get('type')}")
            except Exception as receive_error:
                logger.info(f"WebSocket receive ended: {receive_error}")
                break

            if data.get("type") != "chat":
                continue

            body = data.get("payload", {})
            messages = body.get("messages", [])
            body["stream"] = True
            body["temperature"] = 0.35
            body["top_p"] = 0.7
            body["presence_penalty"] = 0.5

            # Guard: hard cap on single prompt length
            user_query = messages[-1].get("content", "") if messages else ""
            if prompt_too_long(user_query):
                logger.warning(f"Prompt too long: {len(user_query)} chars from {websocket.client}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Message too long (max {MAX_PROMPT_CHARS} characters)"
                })
                continue

            # Sliding window: drop oldest user/assistant pairs when history is too large
            before = len(messages)
            messages = compact_history(messages)
            if len(messages) < before:
                logger.info(f"History compacted: {before} → {len(messages)} messages")

            context_docs = await search_knowledge_base(user_query, limit=3)
            logger.info(f"RAG: {len(context_docs)} docs for query: {user_query[:100]}")
            for i, doc in enumerate(context_docs, 1):
                logger.info(f"  {i}. {doc.get('title')} ({doc.get('source')})")

            system_prompt = """You are Chris Wetzel. Answer questions based solely on the knowledge base documents below.

RULES (non-negotiable):
1. First person only. You ARE Chris — never refer to yourself in the third person.
2. All facts must come from the knowledge base below. Do not supplement with general knowledge.
3. If the knowledge base does not contain the answer, say exactly: "I don't have that documented in my knowledge base."
4. If sources conflict, say: "My knowledge base has conflicting information on this."

MANDATORY OUTPUT — append this after every answer, no exceptions:
FOLLOWUPS:["question one","question two","question three"]
Replace the quoted strings with three natural follow-up questions based on your answer. Nothing after the closing bracket.

---
KNOWLEDGE BASE:
"""
            for doc in context_docs:
                title   = doc.get("title", "Unknown")
                source  = doc.get("source", "")
                content = doc.get("content", "")[:2000]
                system_prompt += f"\n\n### {title} ({source})\n{content}"

            system_prompt += '\n\n---\nFOLLOWUPS:["question one","question two","question three"] — replace with three real follow-up questions. This line must appear at the end of your response.'

            messages = inject_system_prompt(messages, system_prompt)
            body["messages"] = messages

            try:
                async with _http.stream(
                    "POST",
                    f"{VLLM_URL}/v1/chat/completions",
                    json=body,
                    timeout=120.0
                ) as response:
                    full_response = ""
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        try:
                            chunk = json.loads(line[6:])
                            if chunk.get("choices"):
                                delta_content = chunk["choices"][0].get("delta", {}).get("content", "")
                                full_response += delta_content
                                await websocket.send_json({"type": "chunk", "data": chunk})
                        except json.JSONDecodeError:
                            pass
                        except Exception as chunk_error:
                            logger.error(f"Chunk error: {chunk_error}")

                if "don't have that documented" in full_response.lower():
                    logger.info("Response: NOT GROUNDED")
                elif "conflicting information" in full_response.lower():
                    logger.info("Response: CONFLICT")
                else:
                    logger.info("Response: GROUNDED")

                await websocket.send_json({"type": "done"})

            except Exception as stream_error:
                logger.error(f"Stream error: {stream_error}")
                try:
                    await websocket.send_json({"type": "error", "message": str(stream_error)})
                except Exception:
                    pass

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
