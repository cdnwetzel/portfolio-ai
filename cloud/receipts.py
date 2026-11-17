"""Verdict persistence + shaping for the per-answer receipts feature.

Two jobs, both deliberately boring:

1. Append every faithfulness verdict (not just flagged ones) to an append-only JSONL
   log, so a receipt panel can answer "was this answer checked?" after the fact and
   the /inside status page can show a 24h verdict distribution.
2. Shape verdict payloads into the wire format the frontend renders, with the
   red-lines.md #2 invariant baked in: METADATA ONLY. No query text, no answer
   content, no chunk content ever enters a record, a push frame, or the read
   endpoint. Scores and counts are the product; content is not.

Stdlib-only by design (like guardrails / rate_limit / verify_gate) so it unit-tests
under CI, which installs only pytest — no fastapi, no httpx.

Store choice: append-only JSONL on the VPS, one line per verdict. Volume is ~1 line
per verified chat; even a heavy day is a few thousand small lines. The read pattern
is "latest record for request_id" and "counts over 24h" — both fine with a full
replay into memory at startup (single-process uvicorn, file is tiny). If volume ever
matters, swap the internals for sqlite without touching call sites.
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone

# request_id values are uuid4().hex from api-proxy.py — validate before using the
# id as a dict key and as a URL path component.
REQUEST_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def is_valid_request_id(request_id: str) -> bool:
    return isinstance(request_id, str) and bool(REQUEST_ID_RE.match(request_id))


def build_verdict_record(verdict_json: dict, *, request_id: str, latency_ms: int,
                         model: str, prompt_version: str, ts: "datetime | None" = None) -> dict:
    """Shape a judge /verify response into a persistence/wire record.

    Defensive .get() throughout: the judge service is on another machine, outside
    this repo, and its response schema has never been pinned in one place. A missing
    field becomes None, never an exception — the same fail-soft posture as the
    fire-and-forget caller.

    red-lines.md #2: metadata only. Never copy query/answer/chunk fields from the
    payload into this record."""
    verdict_json = verdict_json or {}
    flagged = bool(verdict_json.get("flagged"))
    # n_claims must be an int. A "claims" FALLBACK exists for a hypothetical judge
    # that returns a bare count under that name — but the real judge returns
    # per-claim objects under "claims" (content-bearing!). Accept only ints; a
    # list/str under either key becomes None, never persisted (red-lines.md #2 —
    # this exact leak was caught by test_metadata_only_no_content_fields).
    n_claims = verdict_json.get("n_claims")
    if not isinstance(n_claims, int):
        legacy = verdict_json.get("claims")
        n_claims = legacy if isinstance(legacy, int) else None
    return {
        "ts": (ts or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
        "request_id": request_id,
        "state": "flagged" if flagged else "ok",
        "flagged": flagged,
        "faithfulness": verdict_json.get("faithfulness"),
        "n_contradicted": verdict_json.get("n_contradicted"),
        "n_unsupported": verdict_json.get("n_unsupported"),
        "n_supported": verdict_json.get("n_supported"),
        "n_claims": n_claims,
        "judge_model": verdict_json.get("judge_model"),
        "latency_ms": latency_ms,
        "model": model,
        "prompt_version": prompt_version,
    }


def verdict_state(verdict_json: dict) -> str:
    """Map a raw judge response to its receipt-panel state."""
    return "flagged" if (verdict_json or {}).get("flagged") else "ok"


def _parse_ts(ts: str) -> "datetime | None":
    try:
        return datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None


class VerdictStore:
    """Append-only JSONL verdict log with an in-memory index.

    init failure (missing dir, unreadable file) leaves the store disabled:
    every method no-ops safely. Receipts must never become a chat-availability
    dependency — same rule as the verifier itself."""

    def __init__(self, path: "str | None"):
        self.path = path
        self._by_id: dict = {}
        self.enabled = False
        if not path:
            return
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                        except json.JSONDecodeError:
                            continue  # a torn line must not kill the store
                        rid = rec.get("request_id")
                        if rid:
                            self._by_id[rid] = rec
            # Probe writability up front so `enabled` is truthful about append:
            # a store that replays but cannot write would 404 every /api/verdicts
            # lookup while claiming to be on. A missing parent dir or a read-only
            # file disables the store here, before first use.
            with open(path, "a", encoding="utf-8"):
                pass
            self.enabled = True
        except OSError as e:
            # Disabled, not crashed: log-free here (stdlib-only module), caller logs.
            self.path = None

    def append(self, record: dict) -> bool:
        """Append one record; returns False (never raises) on any failure."""
        if not self.enabled:
            return False
        rid = record.get("request_id")
        if not rid:
            return False
        try:
            # Crash-safe enough: a torn final line is skipped on replay (see init),
            # and the in-memory index is updated only after a successful write.
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, separators=(",", ":")) + "\n")
            self._by_id[rid] = record
            return True
        except OSError:
            return False

    def get(self, request_id: str) -> "dict | None":
        if not self.enabled or not is_valid_request_id(request_id):
            return None
        return self._by_id.get(request_id)

    def distribution(self, since_hours: int = 24, now: "datetime | None" = None) -> dict:
        """Faithfulness-score histogram over the trailing window, for /api/status.

        Buckets: <0.6, 0.6-0.8, 0.8-0.95, >=0.95, and unscored. Records whose ts is
        unparseable are counted as unscored rather than dropped."""
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=since_hours)
        buckets = {"lt60": 0, "60to80": 0, "80to95": 0, "95plus": 0, "unscored": 0}
        total = flagged = 0
        for rec in self._by_id.values():
            ts = _parse_ts(rec.get("ts", ""))
            if ts is not None and ts < cutoff:
                continue
            total += 1
            if rec.get("flagged"):
                flagged += 1
            score = rec.get("faithfulness")
            if not isinstance(score, (int, float)):
                buckets["unscored"] += 1
            elif score < 0.6:
                buckets["lt60"] += 1
            elif score < 0.8:
                buckets["60to80"] += 1
            elif score < 0.95:
                buckets["80to95"] += 1
            else:
                buckets["95plus"] += 1
        return {"window_hours": since_hours, "total": total, "flagged": flagged, "buckets": buckets}
