"""Component-state classification for the public /inside status page.

Pure logic only (stdlib) — the httpx polling that feeds it lives in api-proxy.py,
keeping this module unit-testable under CI's pytest-only environment.

State vocabulary follows the site's fail-open ethos: a component that cannot be
probed is "unknown" (gray), never "down" (red). The portfolio twin keeps answering
through single-component failures, and the status page must not scream about a
failure the chat itself rides through.
"""

# Terminal states shown on /inside. "off" is a stable configuration (component
# intentionally not enabled — e.g. VERIFIER_URL unset), not an error.
STATES = ("ok", "degraded", "unknown", "off")


def classify_probe(answered: bool, *, expected_model: "str | None" = None,
                   served_model: "str | None" = None) -> str:
    """Map one probe result to a state.

    answered        — did the health endpoint return any HTTP response at all
    expected_model  — if set, served_model is compared against it (contract check:
                      a health-200 from a box serving the WRONG model is the exact
                      failure mode that blanked the site on 2026-08-29 — the rename
                      incident that made MODEL_ID server-pinned)
    served_model    — model id from /v1/models when probed
    """
    if not answered:
        return "unknown"
    if expected_model and served_model is not None and served_model != expected_model:
        return "degraded"
    return "ok"


def probe_definitions(vllm_url: str, model_id: str, qdrant_url: str, embed_url: str,
                      rerank_url: str, verifier_url: str,
                      verifier_health_path: str = "/health") -> list:
    """Build the probe table for /api/status from the proxy's resolved config.

    Each entry: {key, label, health_url, models_url|None}. models_url is set only
    where a model-id contract check applies (the vLLM path). The verifier is
    env-gated: with no VERIFIER_URL there is nothing to probe — its state is "off"
    and it is not in the probe list."""
    probes = [
        {"key": "vllm", "label": "vLLM — qwen3.8-27b (T5810, dual A4500)",
         "health_url": f"{vllm_url}/health", "models_url": f"{vllm_url}/v1/models",
         "expected_model": model_id},
        {"key": "qdrant", "label": "Qdrant vector DB (T5810)",
         "health_url": f"{qdrant_url}/healthz", "models_url": None, "expected_model": None},
        {"key": "embedder", "label": "bge-base embeddings (T5810)",
         "health_url": f"{embed_url}/health", "models_url": None, "expected_model": None},
        {"key": "reranker", "label": "bge-reranker (asrock B550, RTX 5060 Ti)",
         "health_url": f"{rerank_url}/health", "models_url": None, "expected_model": None},
    ]
    if verifier_url:
        probes.append({"key": "verifier", "label": "Faithfulness judge (asrock B550)",
                       "health_url": f"{verifier_url}{verifier_health_path}",
                       "models_url": None, "expected_model": None})
    return probes
