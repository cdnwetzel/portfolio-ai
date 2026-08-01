"""
Unit tests for per-IP connection rate limiting (cloud/rate_limit.py).
No infrastructure required — pure function tests, stdlib-only.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "cloud"))
from rate_limit import ConnectionRateLimiter, client_ip_from_headers


# --- try_acquire / release ---

def test_first_connection_allowed():
    rl = ConnectionRateLimiter()
    assert rl.try_acquire("203.0.113.10") is True


def test_second_concurrent_connection_rejected():
    rl = ConnectionRateLimiter()
    assert rl.try_acquire("203.0.113.10") is True
    assert rl.try_acquire("203.0.113.10") is False


def test_slot_freed_on_release():
    rl = ConnectionRateLimiter()
    rl.try_acquire("203.0.113.10")
    rl.release("203.0.113.10")
    assert rl.try_acquire("203.0.113.10") is True


def test_different_ips_independent():
    rl = ConnectionRateLimiter()
    assert rl.try_acquire("203.0.113.10") is True
    assert rl.try_acquire("198.51.100.7") is True
    assert rl.try_acquire("198.51.100.7") is False


def test_localhost_bypass_ipv4():
    rl = ConnectionRateLimiter()
    assert rl.try_acquire("127.0.0.1") is True
    assert rl.try_acquire("127.0.0.1") is True
    assert rl.try_acquire("127.0.0.1") is True


def test_localhost_bypass_ipv6():
    rl = ConnectionRateLimiter()
    assert rl.try_acquire("::1") is True
    assert rl.try_acquire("::1") is True


def test_localhost_not_tracked():
    # Localhost acquisitions must not consume or leave state behind
    rl = ConnectionRateLimiter()
    rl.try_acquire("127.0.0.1")
    rl.release("127.0.0.1")
    assert rl.active_count("127.0.0.1") == 0


def test_release_idempotent():
    # Releasing an IP that holds no slot must not corrupt state
    rl = ConnectionRateLimiter()
    rl.release("203.0.113.10")
    assert rl.active_count("203.0.113.10") == 0
    assert rl.try_acquire("203.0.113.10") is True


def test_active_count_tracks_slots():
    rl = ConnectionRateLimiter(max_concurrent_per_ip=2)
    rl.try_acquire("203.0.113.10")
    rl.try_acquire("203.0.113.10")
    assert rl.active_count("203.0.113.10") == 2
    assert rl.try_acquire("203.0.113.10") is False
    rl.release("203.0.113.10")
    assert rl.active_count("203.0.113.10") == 1


# --- client_ip_from_headers ---

def test_client_ip_prefers_x_forwarded_for():
    # Behind Apache the socket peer is 127.0.0.1; the real client is leftmost XFF
    ip = client_ip_from_headers({"x-forwarded-for": "203.0.113.10"}, "127.0.0.1")
    assert ip == "203.0.113.10"


def test_client_ip_xff_chain_takes_leftmost():
    ip = client_ip_from_headers({"x-forwarded-for": "203.0.113.10, 10.0.0.1, 172.16.0.1"}, "127.0.0.1")
    assert ip == "203.0.113.10"


def test_client_ip_falls_back_to_peer_host():
    assert client_ip_from_headers({}, "198.51.100.7") == "198.51.100.7"


def test_client_ip_unknown_when_no_peer():
    assert client_ip_from_headers({}, None) == "unknown"
