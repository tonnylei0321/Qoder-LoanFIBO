"""单元测试 — IP 速率限制中间件 RateLimiter。"""

from backend.app.middleware.rate_limit import RateLimiter


class TestRateLimiter:
    """RateLimiter 滑动窗口测试。"""

    def test_within_limit_allows(self):
        """限额内请求应被允许。"""
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        for _ in range(5):
            assert limiter.is_allowed("192.168.1.1") is True

    def test_over_limit_rejects(self):
        """超限请求应被拒绝。"""
        limiter = RateLimiter(max_requests=3, window_seconds=60)

        for _ in range(3):
            limiter.is_allowed("10.0.0.1")

        assert limiter.is_allowed("10.0.0.1") is False

    def test_different_ips_independent(self):
        """不同 IP 应独立计数。"""
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        limiter.is_allowed("10.0.0.1")
        limiter.is_allowed("10.0.0.1")
        assert limiter.is_allowed("10.0.0.1") is False

        # 不同 IP 仍有配额
        assert limiter.is_allowed("10.0.0.2") is True

    def test_get_remaining(self):
        """get_remaining 应返回剩余可用请求数。"""
        limiter = RateLimiter(max_requests=10, window_seconds=60)

        assert limiter.get_remaining("10.0.0.1") == 10
        limiter.is_allowed("10.0.0.1")
        assert limiter.get_remaining("10.0.0.1") == 9

    def test_reset_specific_ip(self):
        """reset(ip) 应重置指定 IP 的记录。"""
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        limiter.is_allowed("10.0.0.1")
        limiter.is_allowed("10.0.0.1")
        assert limiter.is_allowed("10.0.0.1") is False

        limiter.reset("10.0.0.1")
        assert limiter.is_allowed("10.0.0.1") is True

    def test_reset_all(self):
        """reset() 应重置所有 IP 的记录。"""
        limiter = RateLimiter(max_requests=1, window_seconds=60)

        limiter.is_allowed("10.0.0.1")
        limiter.is_allowed("10.0.0.2")
        assert limiter.is_allowed("10.0.0.1") is False

        limiter.reset()
        assert limiter.is_allowed("10.0.0.1") is True
        assert limiter.is_allowed("10.0.0.2") is True
