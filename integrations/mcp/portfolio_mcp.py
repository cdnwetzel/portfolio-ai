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
  portfolio_search(question, k=5)            → raw grounded chunks via cwdotcom's /api/retrieve
      seam (embed → dense search → rerank → per-doc cap, server-side) for an agent to reason over.
  portfolio_verify(question, answer, chunks) → faithfulness check via the asrock judge.

The tool LOGIC lives in plain async functions (importable/testable with no `mcp` dep). The
MCP transport is a guarded wrapper so this file imports fine for tests even without the SDK.

Env (all optional):
  CWDOTCOM_WS_URL        default wss://dev.cwetzel.com/ws/chat        (portfolio_answer)
  CWDOTCOM_RETRIEVE_URL  default https://dev.cwetzel.com/api/retrieve (portfolio_search)
  VERIFIER_URL           default http://10.0.1.115:8007              (portfolio_verify; LAN)
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
from run_diagnostic_battery import ask          # WS client: string -> {answer, sources, ...}

WS_URL       = os.environ.get("CWDOTCOM_WS_URL", "wss://dev.cwetzel.com/ws/chat")
# Grounded-chunks REST seam on the VPS proxy. embed/rerank bind 127.0.0.1 on the T5810
# (localhost-only), so search goes through the public endpoint, not the LAN microservices.
RETRIEVE_URL = os.environ.get("CWDOTCOM_RETRIEVE_URL", "https://dev.cwetzel.com/api/retrieve").rstrip("/")
VERIFIER_URL = os.environ.get("VERIFIER_URL", "http://10.0.1.115:8007").rstrip("/")

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
    """Raw grounded chunks via cwdotcom's REST retrieval seam (expand → embed → dense search →
    rerank → per-doc cap, all server-side, guardrailed). Text in, chunks out."""
    async with httpx.AsyncClient(timeout=30.0) as http:
        r = await http.post(RETRIEVE_URL, json={"query": question, "k": k})
        r.raise_for_status()
        return {"chunks": r.json().get("chunks", [])}


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
        system — GROUNDED in his knowledge base. Call this for ANY such question.

        RELAY THE RETURNED `answer` FIELD VERBATIM plus its `sources`. Do NOT rewrite, summarize,
        expand, reorder, paraphrase, or add connecting statements of your own. The `answer` is
        already complete and fact-checked by a grounded pipeline; re-synthesizing it risks
        introducing errors (e.g. conflating which components a bridge/link connects). Send it as-is."""
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
