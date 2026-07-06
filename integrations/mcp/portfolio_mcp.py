#!/usr/bin/env python3
"""
Portfolio-RAG MCP server — exposes cwdotcom's GROUNDED retrieval to an MCP client
(OpenClaw's `mcporter` skill on the Mac Mini) so a WhatsApp/agent front-end can answer
questions about Chris Wetzel's work WITHOUT hallucinating. See plans/openclaw-portfolio-rag.md.

Design: a thin, READ-ONLY facade over cwdotcom's existing stack. Direction is one-way —
OpenClaw depends on cwdotcom, never the reverse. No new business logic; no writes.

Tools:
  portfolio_answer(question)                 → the SAFE default. Drives cwdotcom's full
      hardened pipeline via the public WS (reusing run_diagnostic_battery.ask): grounding
      system prompt, prompt-extraction guardrail, dense retrieval + rerank, out-of-band
      verifier (fires server-side), FOLLOWUPS. Returns {answer, sources}. Zero proxy change.
  portfolio_search(question, k=5)            → raw grounded chunks (expand → embed → Qdrant →
      rerank) for an agent that wants to reason over facts itself. LAN microservices.
  portfolio_verify(question, answer, chunks) → faithfulness check via the asrock judge.

The tool LOGIC lives in plain async functions (importable/testable with no `mcp` dep). The
MCP transport is a guarded wrapper so this file imports fine for tests even without the SDK.

Env (all optional; defaults suit the Mac Mini on the home LAN):
  CWDOTCOM_WS_URL   default wss://dev.cwetzel.com/ws/chat   (public; works on/off-LAN)
  EMBED_URL         default http://10.0.1.125:8005
  QDRANT_URL        default http://10.0.1.125:6333
  RERANK_URL        default http://10.0.1.125:8006
  VERIFIER_URL      default http://10.0.1.115:8007
  QDRANT_COLLECTION default documents
"""
import asyncio
import os
import re
import sys
from pathlib import Path

import httpx

# --- reuse cwdotcom internals (this file lives at <repo>/integrations/mcp/) ---
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts"))
sys.path.insert(0, str(_REPO / "cloud"))
from run_diagnostic_battery import ask          # WS client: string -> {answer, sources, ...}
from query_expansion import expand_query        # pure recall booster (alias groups)

WS_URL       = os.environ.get("CWDOTCOM_WS_URL", "wss://dev.cwetzel.com/ws/chat")
EMBED_URL    = os.environ.get("EMBED_URL",   "http://10.0.1.125:8005").rstrip("/")
QDRANT_URL   = os.environ.get("QDRANT_URL",  "http://10.0.1.125:6333").rstrip("/")
RERANK_URL   = os.environ.get("RERANK_URL",  "http://10.0.1.125:8006").rstrip("/")
VERIFIER_URL = os.environ.get("VERIFIER_URL","http://10.0.1.115:8007").rstrip("/")
COLLECTION   = os.environ.get("QDRANT_COLLECTION", "documents")

_FOLLOWUPS_RE = re.compile(r"\n*(?:FOLLOWUPS\s*:|\*\*Follow-?ups?:?\*\*).*", re.IGNORECASE | re.DOTALL)


def _clean_answer(text: str) -> str:
    """Strip the trailing FOLLOWUPS/Follow-ups block and any dangling '---' separator."""
    text = _FOLLOWUPS_RE.sub("", text or "")
    return re.sub(r"\n+-{3,}\s*$", "", text.rstrip()).strip()


# --- tool logic (pure async; no MCP dependency) ------------------------------
async def answer_tool(question: str) -> dict:
    """Grounded answer from cwdotcom's full pipeline. The safe default for portfolio Qs."""
    r = await ask(WS_URL, question)
    sources = [{"title": s.get("title"), "source": s.get("source"), "score": s.get("score")}
               for s in (r.get("sources") or [])]
    answer = _clean_answer(r.get("answer", ""))
    return {"answer": answer, "sources": sources,
            "grounded": bool(answer) and not answer.lower().startswith("i don't have")}


async def search_tool(question: str, k: int = 5) -> dict:
    """Raw grounded chunks: expand → embed → Qdrant dense search (top-15) → rerank (top-k).
    Mirrors cwdotcom's retrieval; talks to the LAN microservices (no proxy/tunnel needed)."""
    embed_q = expand_query(question)
    async with httpx.AsyncClient(timeout=15.0) as http:
        e = await http.post(f"{EMBED_URL}/embed", json={"text": embed_q})
        e.raise_for_status()
        vector = e.json()["embedding"]
        s = await http.post(f"{QDRANT_URL}/collections/{COLLECTION}/points/search",
                            json={"vector": vector, "limit": 15, "with_payload": True})
        s.raise_for_status()
        hits = [h.get("payload", {}) for h in s.json().get("result", [])]
        if not hits:
            return {"chunks": []}
        docs = [h.get("content", "") for h in hits]
        rr = await http.post(f"{RERANK_URL}/rerank",
                            json={"query": question, "documents": docs, "top_k": k})
        rr.raise_for_status()
        ranked = rr.json().get("results", [])
    chunks, seen = [], set()
    for item in ranked:
        h = hits[item["index"]]
        doc_id = h.get("doc_id") or h.get("title")
        if doc_id in seen:                       # one chunk per source doc (mirrors the proxy)
            continue
        seen.add(doc_id)
        chunks.append({"title": h.get("title"), "source": h.get("source"),
                       "content": h.get("content", ""), "score": round(item.get("score", 0.0), 4)})
    return {"chunks": chunks}


async def verify_tool(question: str, answer: str, chunks: list) -> dict:
    """Faithfulness check via the out-of-band judge (asrock). Grade any (q, answer, chunks)."""
    payload = {"query": question, "answer": answer,
               "chunks": [{"title": c.get("title", ""), "source": c.get("source", ""),
                           "content": c.get("content", "")} for c in (chunks or [])]}
    async with httpx.AsyncClient(timeout=60.0) as http:
        v = await http.post(f"{VERIFIER_URL}/verify", json=payload)
        v.raise_for_status()
        d = v.json()
    return {"faithfulness": d.get("faithfulness"), "flagged": d.get("flagged"),
            "verdict_type": d.get("verdict_type"), "claims": d.get("claims", [])}


# --- MCP transport (guarded so the module imports without the SDK) ------------
def _build_server():
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("portfolio-rag")

    @mcp.tool()
    async def portfolio_answer(question: str) -> dict:
        """Answer a question about Chris Wetzel's documented work, homelab, projects, or this AI
        system — GROUNDED in his knowledge base (not the model's own knowledge). Use this for
        any portfolio question and relay `answer` + `sources` verbatim; do not embellish."""
        return await answer_tool(question)

    @mcp.tool()
    async def portfolio_search(question: str, k: int = 5) -> dict:
        """Return the top-k grounded knowledge-base chunks for a question (title, source, content,
        score) so you can reason over Chris's documented facts. If you generate from these, answer
        ONLY from the returned chunks; if not covered, say so."""
        return await search_tool(question, k)

    @mcp.tool()
    async def portfolio_verify(question: str, answer: str, chunks: list) -> dict:
        """Check whether an answer is faithfully supported by the given knowledge-base chunks;
        returns a faithfulness score and per-claim verdicts."""
        return await verify_tool(question, answer, chunks)

    return mcp


if __name__ == "__main__":
    _build_server().run()   # stdio transport for the MCP client (OpenClaw mcporter)
