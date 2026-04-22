"""IP 速率限制中间件 — 滑动窗口算法。

用于 WebSocket 连接端点的 IP 级速率限制，
防止暴力破解 client_id/client_secret。

默认配置：每 IP 每分钟最多 10 次连接尝试。
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List


class RateLimiter:
    """滑动窗口速率限制器。

    线程安全说明：在单线程 asyncio 事件循环中运行，无需加锁。
    """

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        """
        Args:
            max_requests: 窗口内最大请求数
            window_seconds: 滑动窗口大小（秒）
        """
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, ip: str) -> bool:
        """检查该 IP 是否允许请求。

        使用滑动窗口算法：移除窗口外的旧记录，检查剩余数量。

        Args:
            ip: 客户端 IP 地址

        Returns:
            True 表示允许，False 表示超限
        """
        now = time.monotonic()
        cutoff = now - self._window_seconds

        # 移除窗口外的旧记录
        self._requests[ip] = [
            ts for ts in self._requests[ip] if ts > cutoff
        ]

        if len(self._requests[ip]) >= self._max_requests:
            return False

        # 记录本次请求
        self._requests[ip].append(now)
        return True

    def get_remaining(self, ip: str) -> int:
        """获取该 IP 剩余可用请求数。"""
        now = time.monotonic()
        cutoff = now - self._window_seconds

        current = len([
            ts for ts in self._requests.get(ip, []) if ts > cutoff
        ])
        return max(0, self._max_requests - current)

    def reset(self, ip: str | None = None) -> None:
        """重置指定 IP 或所有 IP 的记录。"""
        if ip is None:
            self._requests.clear()
        else:
            self._requests.pop(ip, None)


# 全局单例
_ws_rate_limiter: RateLimiter | None = None


def get_ws_rate_limiter() -> RateLimiter:
    """获取 WebSocket 速率限制器全局单例。"""
    global _ws_rate_limiter
    if _ws_rate_limiter is None:
        _ws_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)
    return _ws_rate_limiter
