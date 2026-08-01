"""Per-IP rate limiting for the public /ws/chat WebSocket endpoint.

Anonymous and unauthenticated, the endpoint is otherwise an unthrottled DoS
vector: one scripted loop pins the 14B vLLM at minimum throughput and takes
the site down for everyone. Single-tenant constraint makes the fix trivial —
a human has one chat open at a time, so 1 concurrent connection per IP is a
generous budget that scripts trip immediately.

Storage is an in-memory dict: single-server, single asyncio loop, so no locks
needed (no await between read and write). If the topology ever goes
multi-instance, migrate to Redis.

Stdlib-only by design (like guardrails / context_manager / query_expansion /
sparse_bm25) so it unit-tests without fastapi/httpx — CI installs only pytest.

Per-session token budget (Bucket 2 from tier-1/1-rate-limiting/SPEC.md) is
deliberately deferred: connection-level limiting is the key security win.
"""

# Localhost bypass: local testing and the OpenClaw agent on the LAN Mac Mini
# must never be throttled.
LOCALHOST_IPS = frozenset({"127.0.0.1", "::1", "localhost"})


def client_ip_from_headers(headers: dict, fallback_host: "str | None") -> str:
    """Resolve the effective client IP for rate limiting.

    The proxy sits behind Apache (SSL + reverse proxy on the VPS), so
    websocket.client.host is always 127.0.0.1 in production — keying on it
    directly would either throttle every visitor together or exempt them all
    via the localhost bypass. Apache sets X-Forwarded-For; the leftmost entry
    is the original client. Falls back to the socket peer when absent
    (direct-hit traffic, local tests)."""
    xff = headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return fallback_host or "unknown"


class ConnectionRateLimiter:
    """In-memory per-IP limit of N concurrent open connections."""

    def __init__(self, max_concurrent_per_ip: int = 1):
        self.max_concurrent_per_ip = max_concurrent_per_ip
        self._active: "dict[str, int]" = {}

    def try_acquire(self, ip: str) -> bool:
        """Take a slot for ip. Localhost always succeeds and is never tracked."""
        if ip in LOCALHOST_IPS:
            return True
        count = self._active.get(ip, 0)
        if count >= self.max_concurrent_per_ip:
            return False
        self._active[ip] = count + 1
        return True

    def release(self, ip: str) -> None:
        """Free ip's slot. Idempotent — safe to call even if acquire failed."""
        if ip in LOCALHOST_IPS:
            return
        count = self._active.get(ip, 0)
        if count <= 1:
            self._active.pop(ip, None)
        else:
            self._active[ip] = count - 1

    def active_count(self, ip: str) -> int:
        return self._active.get(ip, 0)
