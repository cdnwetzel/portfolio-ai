"""Unit tests for WindowRateLimiter in cloud/rate_limit.py."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cloud"))

from rate_limit import WindowRateLimiter  # noqa: E402


class TestWindowRateLimiter:
    def test_under_budget_allowed(self):
        rl = WindowRateLimiter(max_requests=3, window_seconds=60)
        assert all(rl.try_acquire("1.2.3.4", now=1000.0 + i) for i in range(3))

    def test_over_budget_denied(self):
        rl = WindowRateLimiter(max_requests=3, window_seconds=60)
        for i in range(3):
            rl.try_acquire("1.2.3.4", now=1000.0 + i)
        assert rl.try_acquire("1.2.3.4", now=1003.0) is False

    def test_window_slides(self):
        rl = WindowRateLimiter(max_requests=2, window_seconds=10)
        assert rl.try_acquire("1.2.3.4", now=0.0)
        assert rl.try_acquire("1.2.3.4", now=5.0)
        assert not rl.try_acquire("1.2.3.4", now=6.0)
        # at t=11 the t=0 hit has expired; t=5 remains
        assert rl.try_acquire("1.2.3.4", now=11.0)
        assert not rl.try_acquire("1.2.3.4", now=12.0)

    def test_ips_independent(self):
        rl = WindowRateLimiter(max_requests=1, window_seconds=60)
        assert rl.try_acquire("1.1.1.1", now=0.0)
        assert rl.try_acquire("2.2.2.2", now=0.0)

    def test_localhost_always_allowed_and_untracked(self):
        rl = WindowRateLimiter(max_requests=1, window_seconds=60)
        for i in range(10):
            assert rl.try_acquire("127.0.0.1", now=float(i))
        assert rl._hits == {}
