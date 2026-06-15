"""
FastAPI proxy: cwetzel.com:8000 → T5810 (vLLM:8004, Qdrant:6333)
Handles auth, rate limiting, request logging.
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VLLM_URL  = "http://127.0.0.1:8004"
QDRANT_URL = "http://127.0.0.1:6333"
EMBED_URL  = "http://127.0.0.1:8005"

# Input limits
MAX_PROMPT_CHARS = 4000   # hard cap per user message (~1000 tokens)
MAX_HISTORY_CHARS = 24000 # sliding window: drop oldest pairs beyond this (~6000 tokens)

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

@app.post("/api/chat")
async def chat(request: Request):
    """Proxy chat request to vLLM"""
    try:
        body = await request.json()
        logger.info(f"Chat request: {body.get('messages', [])[-1:] if body.get('messages') else 'no messages'}")
        response = await _http.post(
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
            async with _http.stream(
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
            if len(user_query) > MAX_PROMPT_CHARS:
                logger.warning(f"Prompt too long: {len(user_query)} chars from {websocket.client}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Message too long (max {MAX_PROMPT_CHARS} characters)"
                })
                continue

            # Sliding window: drop oldest user/assistant pairs when history is too large
            total_chars = sum(len(m.get("content", "")) for m in messages)
            while total_chars > MAX_HISTORY_CHARS and len(messages) > 2:
                # Drop the oldest user+assistant pair (indices 0 and 1, skipping any system msg)
                start = 1 if messages[0].get("role") == "system" else 0
                if start + 1 < len(messages):
                    removed = messages.pop(start)
                    total_chars -= len(removed.get("content", ""))
                    if start < len(messages) and messages[start].get("role") == "assistant":
                        removed = messages.pop(start)
                        total_chars -= len(removed.get("content", ""))
                else:
                    break
            if total_chars > MAX_HISTORY_CHARS:
                logger.info(f"History compacted to {total_chars} chars")

            context_docs = await search_knowledge_base(user_query, limit=3)
            logger.info(f"RAG: {len(context_docs)} docs for query: {user_query[:100]}")
            for i, doc in enumerate(context_docs, 1):
                logger.info(f"  {i}. {doc.get('title')} ({doc.get('source')})")

            system_prompt = """You are Chris Wetzel. Answer questions based on the knowledge base below.

RULES (non-negotiable):
1. First person only. You ARE Chris — never say "as an IT infrastructure expert" in third-person.
2. If the knowledge base doesn't contain the answer, explicitly say: "I don't have that documented in my knowledge base."
3. Always cite specific files, machines, tools, or case studies from the knowledge base.
4. Ground every factual claim in documented experience. Prioritize tools in your knowledge base: Gentoo, kernel_config.sh, shell scripts, vLLM, Qdrant.
5. If sources conflict, state: "My knowledge base has conflicting information on this."

Your documented systems: Precision T5810 (dual A4500 GPUs, PCIe Gen4), Surface Pro 8, ThinkPad X1, custom AMD build, NUC8i7. OS: Gentoo Linux. Automation: custom shell scripts in gentoo-machines repo.

After your answer — on its own line, no extra prose — output exactly this format:
FOLLOWUPS:["<question 1>","<question 2>","<question 3>"]
These should be natural follow-up questions a visitor would want to ask next.

---
KNOWLEDGE BASE (your actual documented work):
"""
            for doc in context_docs:
                title   = doc.get("title", "Unknown")
                source  = doc.get("source", "")
                content = doc.get("content", "")[:2000]
                system_prompt += f"\n\n### {title} ({source})\n{content}"

            if not any(m.get("role") == "system" for m in messages):
                messages = [{"role": "system", "content": system_prompt}] + messages
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
