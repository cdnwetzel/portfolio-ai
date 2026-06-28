"""
Faithfulness verifier service (verifier-faithfulness-layer.md).

Out-of-band, fail-open judge: for each completed chat answer it scores whether each
claim is supported by the chunks that were actually retrieved, stores a verdict, and
exposes rolling metrics + a review queue. Runs on the spare Ryzen/3060 Ti box, NOT
the T5810. Never sits in the user's response path.

Mirrors the home/rerank-service pattern (FastAPI + OpenRC). Judge model is pluggable:
Ollama (default, low-friction on one 8 GB card) or any OpenAI-compatible endpoint.

Env config:
  VERIFIER_PORT     default 8007
  JUDGE_BACKEND     "ollama" (default) | "openai"
  JUDGE_URL         ollama: http://127.0.0.1:11434/api/chat
                    openai: http://127.0.0.1:11434/v1/chat/completions (or any)
  JUDGE_MODEL       default qwen2.5:7b-instruct-q4_K_M
  THRESHOLD         default 0.8  (faithfulness below this flags)
  SAMPLE_RATE       default 1.0  (verify everything; <1.0 samples under load)
  MAX_INFLIGHT      default 2    (bounded judge concurrency on one GPU)
  DB_PATH           default ~/verifier/verdicts.db
  RETENTION_DAYS    default 90   (rows older than this are pruned on write)
"""
import asyncio
import json
import logging
import os
import random
import sqlite3
import time
from contextlib import asynccontextmanager, closing
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from verifier_core import (
    strip_followups, is_refusal, parse_judge_claims, compute_verdict,
    build_judge_messages,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("verifier")

JUDGE_BACKEND = os.getenv("JUDGE_BACKEND", "ollama").lower()
JUDGE_URL = os.getenv("JUDGE_URL", "http://127.0.0.1:11434/api/chat")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "qwen2.5:7b-instruct-q4_K_M")
THRESHOLD = float(os.getenv("THRESHOLD", "0.8"))
SAMPLE_RATE = float(os.getenv("SAMPLE_RATE", "1.0"))
MAX_INFLIGHT = int(os.getenv("MAX_INFLIGHT", "2"))
DB_PATH = os.path.expanduser(os.getenv("DB_PATH", "~/verifier/verdicts.db"))
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "90"))

_sem = asyncio.Semaphore(MAX_INFLIGHT)
_http: httpx.AsyncClient | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS verdicts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT, request_id TEXT, query TEXT, answer TEXT,
  verdict_type TEXT, n_claims INT, n_supported INT, n_unsupported INT,
  n_contradicted INT, faithfulness REAL, flagged INT,
  claims_json TEXT, judge_model TEXT, latency_s REAL
);
CREATE INDEX IF NOT EXISTS idx_verdicts_ts ON verdicts(ts);
CREATE INDEX IF NOT EXISTS idx_verdicts_flagged ON verdicts(flagged);
"""


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with closing(_db()) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http
    _init_db()
    _http = httpx.AsyncClient(timeout=60.0)
    logger.info(f"verifier up: backend={JUDGE_BACKEND} model={JUDGE_MODEL} threshold={THRESHOLD} db={DB_PATH}")
    yield
    await _http.aclose()


app = FastAPI(title="Faithfulness Verifier", lifespan=lifespan)


class Chunk(BaseModel):
    title: str = ""
    source: str = ""
    content: str = ""


class VerifyRequest(BaseModel):
    request_id: str | None = None
    query: str
    answer: str
    chunks: list[Chunk] = []


async def _call_judge(messages: list[dict]) -> str:
    """Call the judge model; return raw text content. Raises on transport error."""
    if JUDGE_BACKEND == "ollama":
        payload = {"model": JUDGE_MODEL, "messages": messages, "stream": False,
                   "format": "json", "options": {"temperature": 0.0}}
        resp = await _http.post(JUDGE_URL, json=payload)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")
    # openai-compatible
    payload = {"model": JUDGE_MODEL, "messages": messages, "temperature": 0.0,
               "max_tokens": 800}
    resp = await _http.post(JUDGE_URL, json=payload)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _store(rec: dict):
    with closing(_db()) as conn:
        conn.execute(
            """INSERT INTO verdicts (ts, request_id, query, answer, verdict_type,
               n_claims, n_supported, n_unsupported, n_contradicted, faithfulness,
               flagged, claims_json, judge_model, latency_s)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rec["ts"], rec.get("request_id"), rec["query"], rec["answer"],
             rec["verdict_type"], rec.get("n_claims", 0), rec.get("n_supported", 0),
             rec.get("n_unsupported", 0), rec.get("n_contradicted", 0),
             rec.get("faithfulness"), int(rec.get("flagged", 0)),
             json.dumps(rec.get("claims", [])), rec.get("judge_model"),
             rec.get("latency_s")),
        )
        # prune old rows on write (cheap retention)
        cutoff = (datetime.utcnow() - timedelta(days=RETENTION_DAYS)).isoformat()
        conn.execute("DELETE FROM verdicts WHERE ts < ?", (cutoff,))
        conn.commit()


@app.post("/verify")
async def verify(req: VerifyRequest):
    t0 = time.time()
    now = datetime.utcnow().isoformat()
    answer = strip_followups(req.answer)

    # 1. Skip refusals — no factual claims to audit.
    if is_refusal(answer) or not answer:
        rec = {"ts": now, "request_id": req.request_id, "query": req.query,
               "answer": answer, "verdict_type": "refusal", "judge_model": JUDGE_MODEL,
               "latency_s": round(time.time() - t0, 3)}
        _store(rec)
        return {"verdict_type": "refusal", "faithfulness": None, "claims": [],
                "flagged": False, "judge_model": JUDGE_MODEL, "latency_s": rec["latency_s"]}

    # 2. Sampling valve (single-user: always on; <1.0 under load).
    if SAMPLE_RATE < 1.0 and random.random() > SAMPLE_RATE:
        return {"verdict_type": "skipped_sampled", "faithfulness": None, "claims": [],
                "flagged": False, "judge_model": JUDGE_MODEL, "latency_s": 0.0}

    # 3. Judge (bounded concurrency; fail-soft — a judge error is recorded, never raised).
    messages = build_judge_messages(req.query, answer, [c.model_dump() for c in req.chunks])
    try:
        async with _sem:
            content = await _call_judge(messages)
        claims = parse_judge_claims(content)
    except Exception as e:
        logger.error(f"judge call failed: {e!r}")
        claims = None

    if claims is None:
        rec = {"ts": now, "request_id": req.request_id, "query": req.query,
               "answer": answer, "verdict_type": "judge_error", "judge_model": JUDGE_MODEL,
               "latency_s": round(time.time() - t0, 3)}
        _store(rec)
        return {"verdict_type": "judge_error", "faithfulness": None, "claims": [],
                "flagged": False, "judge_model": JUDGE_MODEL, "latency_s": rec["latency_s"]}

    agg = compute_verdict(claims, THRESHOLD)
    latency = round(time.time() - t0, 3)
    rec = {"ts": now, "request_id": req.request_id, "query": req.query, "answer": answer,
           "verdict_type": "judged", "claims": claims, "judge_model": JUDGE_MODEL,
           "latency_s": latency, **agg}
    _store(rec)
    if agg["flagged"]:
        logger.warning(f"FLAGGED faithfulness={agg['faithfulness']} contradicted={agg['n_contradicted']}")
    return {"verdict_type": "judged", "claims": claims, "judge_model": JUDGE_MODEL,
            "latency_s": latency, **agg}


@app.get("/metrics")
async def metrics(window: str = "24h"):
    hours = {"24h": 24, "7d": 168, "30d": 720}.get(window, 24)
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    with closing(_db()) as conn:
        rows = conn.execute("SELECT verdict_type, faithfulness, flagged FROM verdicts WHERE ts >= ?",
                            (cutoff,)).fetchall()
    judged = [r for r in rows if r["verdict_type"] == "judged"]
    fvals = [r["faithfulness"] for r in judged if r["faithfulness"] is not None]
    flagged = sum(1 for r in judged if r["flagged"])
    return {
        "window": window, "count": len(rows),
        "refusals": sum(1 for r in rows if r["verdict_type"] == "refusal"),
        "judged": len(judged),
        "mean_faithfulness": round(sum(fvals) / len(fvals), 4) if fvals else None,
        "flagged_count": flagged,
        "flagged_rate": round(flagged / len(judged), 4) if judged else None,
    }


@app.get("/review")
async def review(limit: int = 20):
    with closing(_db()) as conn:
        rows = conn.execute(
            "SELECT * FROM verdicts WHERE flagged = 1 ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["claims"] = json.loads(d.pop("claims_json") or "[]")
        out.append(d)
    return {"count": len(out), "flagged": out}


@app.get("/health")
async def health():
    return {"status": "ok", "backend": JUDGE_BACKEND, "model": JUDGE_MODEL}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("VERIFIER_PORT", "8007")))
