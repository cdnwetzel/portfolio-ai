"""Unit tests for cloud/receipts.py — verdict persistence and shaping.

red-lines.md #2 is the load-bearing invariant here: no verdict record, push frame,
or read result may ever contain query/answer/chunk content. The first test after
the shaping tests asserts exactly that.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cloud"))

from receipts import (  # noqa: E402
    VerdictStore, build_verdict_record, is_valid_request_id, verdict_state,
)


def _record(**kw):
    base = dict(verdict_json={"flagged": False, "faithfulness": 0.93, "n_contradicted": 0,
                              "n_claims": 7},
                request_id="a" * 32, latency_ms=6800,
                model="qwen3.8-27b", prompt_version="v1")
    base.update(kw)
    return build_verdict_record(**base)


class TestBuildRecord:
    def test_ok_state_when_not_flagged(self):
        assert _record()["state"] == "ok"
        assert _record()["flagged"] is False

    def test_flagged_state(self):
        rec = _record(verdict_json={"flagged": True, "faithfulness": 0.41, "n_contradicted": 2})
        assert rec["state"] == "flagged"
        assert rec["flagged"] is True
        assert rec["n_contradicted"] == 2

    def test_missing_fields_become_none_never_raise(self):
        rec = _record(verdict_json={})
        assert rec["faithfulness"] is None
        assert rec["n_claims"] is None
        assert rec["state"] == "ok"  # missing flagged ≠ flagged

    def test_metadata_only_no_content_fields(self):
        # red-lines.md #2: the judge payload carries query/answer/chunks; none of it
        # may leak into the record. The real judge also returns per-claim objects
        # whose .text IS answer content — those must not be persisted either
        # (schema confirmed against production 2026-11-16).
        payload = {"flagged": False, "faithfulness": 0.9, "n_contradicted": 0,
                   "query": "SECRET QUERY", "answer": "SECRET ANSWER",
                   "chunks": [{"content": "SECRET CHUNK"}],
                   "claims": [{"text": "SECRET CLAIM", "verdict": "supported"}],
                   "judge_model": "qwen2.5:14b-instruct-q4_k_m",
                   "n_supported": 3, "n_unsupported": 0}
        rec = build_verdict_record(payload, request_id="b" * 32, latency_ms=1,
                                   model="m", prompt_version="v")
        blob = json.dumps(rec)
        for secret in ("SECRET QUERY", "SECRET ANSWER", "SECRET CHUNK", "SECRET CLAIM"):
            assert secret not in blob
        assert "claims" not in rec          # the whole array is content-bearing
        assert rec["judge_model"] == "qwen2.5:14b-instruct-q4_k_m"
        assert rec["n_supported"] == 3
        assert rec["n_unsupported"] == 0

    def test_production_schema_fields(self):
        # Captured 2026-11-16 from the live judge (docs/lab pre-flight). The record
        # must carry the useful metadata and tolerate its absence.
        payload = {"verdict_type": "judged",
                   "claims": [{"text": "x", "verdict": "supported", "source": 1}],
                   "judge_model": "qwen2.5:14b-instruct-q4_k_m", "latency_s": 2.109,
                   "n_claims": 1, "n_supported": 1, "n_unsupported": 0,
                   "n_contradicted": 0, "faithfulness": 1.0, "flagged": False}
        rec = build_verdict_record(payload, request_id="c" * 32, latency_ms=2109,
                                   model="qwen3.8-27b", prompt_version="v")
        assert rec["state"] == "ok"
        assert rec["faithfulness"] == 1.0
        assert rec["n_claims"] == 1
        assert rec["n_supported"] == 1
        assert rec["n_contradicted"] == 0
        assert rec["judge_model"] == "qwen2.5:14b-instruct-q4_k_m"

    def test_verdict_state_mapping(self):
        assert verdict_state({"flagged": True}) == "flagged"
        assert verdict_state({"flagged": False}) == "ok"
        assert verdict_state({}) == "ok"
        assert verdict_state(None) == "ok"

    def test_request_id_validation(self):
        assert is_valid_request_id("a" * 32)
        assert not is_valid_request_id("A" * 32)        # uuid4().hex is lowercase
        assert not is_valid_request_id("short")
        assert not is_valid_request_id("../etc/passwd")
        assert not is_valid_request_id(None)
        assert not is_valid_request_id("a" * 31 + "\n")


class TestVerdictStore:
    def test_append_get_roundtrip(self, tmp_path):
        store = VerdictStore(str(tmp_path / "v.jsonl"))
        assert store.enabled
        rec = _record()
        assert store.append(rec) is True
        assert store.get("a" * 32)["faithfulness"] == 0.93

    def test_replay_after_restart(self, tmp_path):
        p = tmp_path / "v.jsonl"
        s1 = VerdictStore(str(p))
        s1.append(_record())
        s2 = VerdictStore(str(p))  # new instance = simulated restart
        assert s2.get("a" * 32)["latency_ms"] == 6800

    def test_torn_line_does_not_kill_replay(self, tmp_path):
        p = tmp_path / "v.jsonl"
        p.write_text(json.dumps(_record()) + "\n" + '{"truncated": true\n')
        store = VerdictStore(str(p))
        assert store.enabled
        assert store.get("a" * 32) is not None

    def test_unwritable_path_disables_store_not_process(self, tmp_path):
        store = VerdictStore(str(tmp_path / "no-such-dir" / "v.jsonl"))
        assert store.enabled is False
        assert store.append(_record()) is False
        assert store.get("a" * 32) is None
        assert store.distribution()["total"] == 0

    def test_empty_path_disables(self):
        store = VerdictStore(None)
        assert not store.enabled
        assert store.append(_record()) is False

    def test_invalid_id_never_returns(self, tmp_path):
        store = VerdictStore(str(tmp_path / "v.jsonl"))
        store.append(_record())
        assert store.get("A" * 32) is None
        assert store.get("../../x") is None

    def test_distribution_windowing(self, tmp_path):
        store = VerdictStore(str(tmp_path / "v.jsonl"))
        now = datetime.now(timezone.utc)
        # Distinct request_ids: the store is a latest-record-per-id index, which is
        # exactly what the read endpoint wants, but it means same-id appends
        # overwrite — real ids are uuid4().hex, one per request.
        store.append(_record(ts=now, request_id="1" * 32))                                    # 0.93 → 80to95
        store.append(_record(verdict_json={"flagged": True, "faithfulness": 0.41,
                                           "n_contradicted": 1},
                             ts=now, request_id="2" * 32))                                    # lt60
        store.append(_record(verdict_json={"faithfulness": 0.99},
                             ts=now, request_id="3" * 32))                                    # 95plus
        store.append(_record(verdict_json={"faithfulness": 0.10},
                             ts=now - timedelta(hours=25), request_id="4" * 32))               # outside window
        d = store.distribution(since_hours=24, now=now)
        assert d["total"] == 3
        assert d["flagged"] == 1
        assert d["buckets"] == {"lt60": 1, "60to80": 0, "80to95": 1, "95plus": 1,
                                "unscored": 0}

    def test_distribution_unscored(self, tmp_path):
        store = VerdictStore(str(tmp_path / "v.jsonl"))
        store.append(_record(verdict_json={"flagged": False}))  # no faithfulness
        assert store.distribution()["buckets"]["unscored"] == 1
