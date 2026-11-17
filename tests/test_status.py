"""Unit tests for cloud/status.py — /inside component classification."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cloud"))

from status import classify_probe, probe_definitions  # noqa: E402


class TestClassifyProbe:
    def test_answered_and_model_matches_is_ok(self):
        assert classify_probe(True, expected_model="qwen3.8-27b",
                              served_model="qwen3.8-27b") == "ok"

    def test_answered_wrong_model_is_degraded(self):
        # The 2026-08-29 rename incident: health green, site blank.
        assert classify_probe(True, expected_model="qwen3.8-27b",
                              served_model="old-model") == "degraded"

    def test_unanswered_is_unknown_never_red(self):
        assert classify_probe(False) == "unknown"

    def test_no_contract_check_when_expected_model_none(self):
        assert classify_probe(True, expected_model=None, served_model=None) == "ok"


class TestProbeDefinitions:
    def _defs(self, verifier_url="http://127.0.0.1:8007"):
        return probe_definitions("http://127.0.0.1:8004", "qwen3.8-27b",
                                 "http://127.0.0.1:6333", "http://127.0.0.1:8005",
                                 "http://127.0.0.1:8016", verifier_url)

    def test_core_components_always_present(self):
        keys = [p["key"] for p in self._defs()]
        assert keys == ["vllm", "qdrant", "embedder", "reranker", "verifier"]

    def test_verifier_absent_when_not_configured(self):
        keys = [p["key"] for p in self._defs(verifier_url="")]
        assert "verifier" not in keys

    def test_only_vllm_carries_model_contract(self):
        for p in self._defs():
            if p["key"] == "vllm":
                assert p["expected_model"] == "qwen3.8-27b"
                assert p["models_url"].endswith("/v1/models")
            else:
                assert p["expected_model"] is None
                assert p["models_url"] is None

    def test_urls_composed_from_resolved_config(self):
        probes = {p["key"]: p for p in self._defs()}
        assert probes["qdrant"]["health_url"] == "http://127.0.0.1:6333/healthz"
        assert probes["embedder"]["health_url"] == "http://127.0.0.1:8005/health"
        assert probes["reranker"]["health_url"] == "http://127.0.0.1:8016/health"
        assert probes["verifier"]["health_url"] == "http://127.0.0.1:8007/health"
