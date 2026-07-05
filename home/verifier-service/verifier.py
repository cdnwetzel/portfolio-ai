"""
Faithfulness verifier service (verifier-faithfulness-layer.md).

Out-of-band, fail-open judge: for each completed chat answer it scores whether each
claim is supported by the chunks that were actually retrieved, stores a verdict, and
exposes rolling metrics + a review queue. Runs on the spare Ryzen/3060 Ti box, NOT
the T5810. Never sits in the user's response path.

Mirrors the home/rerank-service pattern (FastAPI + OpenRC). Judge model is pluggable:
Ollama (default, low-friction on one 8 GB card) or any OpenAI-compatible endpoint.

Env config:
  VERIFIER_BIND     default 127.0.0.1 (localhost-only). Set to the box's LAN IP
                    (e.g. 10.0.1.115) so the T5810's tunnel -L 8007:<ip>:8007 can reach
                    it while nothing else on the LAN can. Avoid 0.0.0.0 (LAN-wide bind).
                    (Distinct from setup-verifier.sh's VERIFIER_HOST, which is the SSH target.)
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
  VERIFIER_DEBUG_CAPTURE  default off. When 1/true, retain query+answer+claims in a
                    SEPARATE debug_captures table to reproduce a specific hallucination.
                    Production keeps this OFF: the verdicts table then holds only an
                    opaque request_id + scores, and no conversation text is stored.
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
# Off by default. When enabled, the query/answer/claims are retained in a SEPARATE
# debug_captures table (never in the verdicts row) so a specific hallucination can be
# reproduced. Kept OFF in production so the verdicts table is scores-only and the public
# "conversations are not stored or logged" claim stays literally true.
DEBUG_CAPTURE = os.getenv("VERIFIER_DEBUG_CAPTURE", "").lower() in ("1", "true", "yes", "on")

_sem = asyncio.Semaphore(MAX_INFLIGHT)
_http: httpx.AsyncClient | None = None

# Lean verdict row: scores keyed by an opaque request_id. NO query/answer/claims text.
# The score is a durable, queryable metric; the content that produced it is not stored.
SCHEMA = """
CREATE TABLE IF NOT EXISTS verdicts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT, request_id TEXT,
  verdict_type TEXT, n_claims INT, n_supported INT, n_unsupported INT,
  n_contradicted INT, faithfulness REAL, flagged INT,
  judge_model TEXT, latency_s REAL
);
CREATE INDEX IF NOT EXISTS idx_verdicts_ts ON verdicts(ts);
CREATE INDEX IF NOT EXISTS idx_verdicts_flagged ON verdicts(flagged);
-- Opt-in only (VERIFIER_DEBUG_CAPTURE=1). Correlates to verdicts by request_id.
CREATE TABLE IF NOT EXISTS debug_captures (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT, request_id TEXT, query TEXT, answer TEXT, claims_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_debug_ts ON debug_captures(ts);
"""

# The legacy schema stored query/answer/claims_json in the verdicts row. On startup we
# migrate in place: copy ONLY the score columns to the lean table and drop the old one,
# which also purges historically stored conversation text.
LEAN_COLS = ("id", "ts", "request_id", "verdict_type", "n_claims", "n_supported",
             "n_unsupported", "n_contradicted", "faithfulness", "flagged",
             "judge_model", "latency_s")


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Scrub freed pages on delete so pruned/migrated rows don't linger in the file.
    conn.execute("PRAGMA secure_delete=ON")
    return conn


def _migrate_legacy(conn):
    """If the verdicts table still carries the old text columns, rebuild it lean.
    Copies score columns only (drops query/answer/claims_json), purging stored text."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(verdicts)").fetchall()}
    if not cols or not ({"query", "answer", "claims_json"} & cols):
        return  # fresh install, or already lean
    logger.warning("migrating verdicts to lean schema (purging stored query/answer/claims text)")
    conn.executescript("DROP INDEX IF EXISTS idx_verdicts_ts; DROP INDEX IF EXISTS idx_verdicts_flagged;")
    conn.execute("ALTER TABLE verdicts RENAME TO verdicts_legacy")
    conn.executescript(SCHEMA)  # create the lean verdicts table (+ indexes + debug table)
    keep = ", ".join(LEAN_COLS)
    conn.execute(f"INSERT INTO verdicts ({keep}) SELECT {keep} FROM verdicts_legacy")
    conn.execute("DROP TABLE verdicts_legacy")
    conn.commit()
    # DROP frees the pages but leaves the bytes on disk until the file is rewritten.
    # VACUUM rebuilds the file so the purged conversation text is physically gone.
    conn.execute("VACUUM")
    conn.commit()


def _init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with closing(_db()) as conn:
        _migrate_legacy(conn)       # rebuild lean + purge text if this is a legacy DB
        conn.executescript(SCHEMA)  # fresh installs; ensure debug table + indexes exist
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
        # Scores only. The query/answer/claims in `rec` are NOT persisted here.
        conn.execute(
            """INSERT INTO verdicts (ts, request_id, verdict_type,
               n_claims, n_supported, n_unsupported, n_contradicted, faithfulness,
               flagged, judge_model, latency_s)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (rec["ts"], rec.get("request_id"), rec["verdict_type"],
             rec.get("n_claims", 0), rec.get("n_supported", 0),
             rec.get("n_unsupported", 0), rec.get("n_contradicted", 0),
             rec.get("faithfulness"), int(rec.get("flagged", 0)),
             rec.get("judge_model"), rec.get("latency_s")),
        )
        # Opt-in only: retain content in a separate table for reproducing a bad answer.
        if DEBUG_CAPTURE:
            conn.execute(
                "INSERT INTO debug_captures (ts, request_id, query, answer, claims_json) VALUES (?,?,?,?,?)",
                (rec["ts"], rec.get("request_id"), rec.get("query", ""),
                 rec.get("answer", ""), json.dumps(rec.get("claims", []))),
            )
        # prune old rows on write (cheap retention)
        cutoff = (datetime.utcnow() - timedelta(days=RETENTION_DAYS)).isoformat()
        conn.execute("DELETE FROM verdicts WHERE ts < ?", (cutoff,))
        if DEBUG_CAPTURE:
            conn.execute("DELETE FROM debug_captures WHERE ts < ?", (cutoff,))
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
        out = [dict(r) for r in rows]
        # Content is available only when opt-in debug capture is enabled; otherwise the
        # review queue is scores + request_id (reproduce the id to see what was said).
        if DEBUG_CAPTURE:
            for d in out:
                cap = conn.execute(
                    "SELECT query, answer, claims_json FROM debug_captures "
                    "WHERE request_id = ? ORDER BY id DESC LIMIT 1",
                    (d.get("request_id"),)).fetchone()
                if cap:
                    d["query"], d["answer"] = cap["query"], cap["answer"]
                    d["claims"] = json.loads(cap["claims_json"] or "[]")
    return {"count": len(out), "flagged": out, "debug_capture": DEBUG_CAPTURE}


@app.get("/health")
async def health():
    return {"status": "ok", "backend": JUDGE_BACKEND, "model": JUDGE_MODEL}


if __name__ == "__main__":
    import uvicorn
    # Default to localhost-only. On the asrock box, set VERIFIER_BIND to its LAN IP
    # (e.g. 10.0.1.115) so the T5810 tunnel can reach it without exposing 8007 LAN-wide.
    uvicorn.run(
        app,
        host=os.getenv("VERIFIER_BIND", "127.0.0.1"),
        port=int(os.getenv("VERIFIER_PORT", "8007")),
    )
