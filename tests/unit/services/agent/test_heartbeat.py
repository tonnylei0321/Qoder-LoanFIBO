"""单元测试 — 心跳检测服务 HeartbeatService。"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.services.agent.heartbeat import (
    GRACE_PERIOD_SEC,
    HEARTBEAT_TIMEOUT_SEC,
    OFFLINE_ALERT_SEC,
    HeartbeatService,
)
from backend.app.services.agent.router import AgentConn, AgentRouter, AgentStatus


@pytest.fixture
def router():
    """纯内存路由表。"""
    return AgentRouter(redis_client=None)


@pytest.fixture
def mock_redis():
    return AsyncMock()


def _make_conn(org_id="org-1", datasource="NCC", last_seen=None, ws=None):
    """创建测试用连接。"""
    if ws is None:
        ws = AsyncMock()
    return AgentConn(
        ws=ws,
        org_id=org_id,
        datasource=datasource,
        version="1.0.0",
        ip="127.0.0.1",
        last_seen=last_seen or datetime.now(timezone.utc),
    )


class TestCheckConnections:
    """check_connections 测试。"""

    def test_healthy_connection_no_action(self, router):
        """健康连接不应触发任何状态变更。"""
        conn = _make_conn(last_seen=datetime.now(timezone.utc))
        router.add_connection(conn)

        svc = HeartbeatService(router=router)
        degraded, offline = svc.check_connections()

        assert degraded == []
        assert offline == []
        assert router.get_connection("org-1", "NCC").status == AgentStatus.ONLINE

    def test_91s_triggers_degraded(self, router):
        """91 秒未收到心跳 → DEGRADED。"""
        last_seen = datetime.now(timezone.utc) - timedelta(seconds=HEARTBEAT_TIMEOUT_SEC + 1)
        conn = _make_conn(last_seen=last_seen)
        router.add_connection(conn)

        svc = HeartbeatService(router=router)
        degraded, offline = svc.check_connections()

        assert len(degraded) == 1
        assert degraded[0] == ("org-1", "NCC")
        assert offline == []
        # 连接仍在路由表中
        assert router.get_connection("org-1", "NCC") is not None

    def test_105s_triggers_offline_and_cleanup(self, router):
        """105 秒未收到心跳 → OFFLINE + 清理路由表。"""
        last_seen = datetime.now(timezone.utc) - timedelta(
            seconds=HEARTBEAT_TIMEOUT_SEC + GRACE_PERIOD_SEC + 1
        )
        mock_ws = AsyncMock()
        conn = _make_conn(last_seen=last_seen, ws=mock_ws)
        router.add_connection(conn)

        svc = HeartbeatService(router=router, redis_client=None)
        degraded, offline = svc.check_connections()

        assert degraded == []
        assert len(offline) == 1
        assert offline[0] == ("org-1", "NCC")
        # 路由表已清理
        assert router.get_connection("org-1", "NCC") is None


class TestOfflineAlerts:
    """check_offline_alerts 测试。"""

    @pytest.mark.asyncio
    async def test_offline_over_5min_triggers_alert(self, router, mock_redis):
        """OFFLINE 超 5 分钟应返回告警。"""
        offline_time = (
            datetime.now(timezone.utc) - timedelta(seconds=OFFLINE_ALERT_SEC + 60)
        ).isoformat()

        # 模拟 Redis scan_iter 返回匹配的键
        mock_redis.scan_iter = MagicMock(
            return_value=AsyncIterator(["agent:offline:org-1:NCC"])
        )
        mock_redis.get = AsyncMock(return_value=offline_time.encode())

        svc = HeartbeatService(router=router, redis_client=mock_redis)
        alerts = await svc.check_offline_alerts()

        assert len(alerts) == 1
        assert alerts[0]["org_id"] == "org-1"
        assert alerts[0]["datasource"] == "NCC"
        assert alerts[0]["offline_seconds"] >= OFFLINE_ALERT_SEC

    @pytest.mark.asyncio
    async def test_offline_under_5min_no_alert(self, router, mock_redis):
        """OFFLINE 不足 5 分钟不应触发告警。"""
        offline_time = (
            datetime.now(timezone.utc) - timedelta(seconds=60)
        ).isoformat()

        mock_redis.scan_iter = MagicMock(
            return_value=AsyncIterator(["agent:offline:org-1:NCC"])
        )
        mock_redis.get = AsyncMock(return_value=offline_time.encode())

        svc = HeartbeatService(router=router, redis_client=mock_redis)
        alerts = await svc.check_offline_alerts()

        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_no_redis_returns_empty(self, router):
        """无 Redis 时返回空列表。"""
        svc = HeartbeatService(router=router, redis_client=None)
        alerts = await svc.check_offline_alerts()
        assert alerts == []


class AsyncIterator:
    """辅助类：将列表包装为异步迭代器（用于 mock scan_iter）。"""

    def __init__(self, items):
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration
