"""单元测试 — 路由表服务 AgentRouter。"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.services.agent.router import AgentConn, AgentRouter, AgentStatus


@pytest.fixture
def router():
    """无 Redis 的纯内存路由表。"""
    return AgentRouter(redis_client=None)


@pytest.fixture
def mock_redis():
    """模拟 Redis 客户端。"""
    redis = AsyncMock()
    redis.hset = AsyncMock()
    redis.hdel = AsyncMock()
    redis.hgetall = AsyncMock(return_value={})
    return redis


def _make_conn(org_id="org-1", datasource="NCC", version="1.0.0", ws=None):
    """创建测试用 AgentConn。"""
    if ws is None:
        ws = MagicMock()
    return AgentConn(
        ws=ws,
        org_id=org_id,
        datasource=datasource,
        version=version,
        ip="127.0.0.1",
    )


class TestAddConnection:
    """add_connection 测试。"""

    def test_add_connection(self, router):
        """添加连接应能通过 get_connection 查到。"""
        conn = _make_conn()
        old = router.add_connection(conn)

        assert old is None
        assert router.get_connection("org-1", "NCC") is conn

    def test_overwrite_old_connection(self, router):
        """新连接覆盖同 datasource 旧连接，返回旧连接。"""
        old_ws = MagicMock()
        old_conn = _make_conn(version="0.9.0", ws=old_ws)
        router.add_connection(old_conn)

        new_conn = _make_conn(version="1.0.0")
        returned_old = router.add_connection(new_conn)

        assert returned_old is old_conn
        assert router.get_connection("org-1", "NCC") is new_conn
        # 调用方负责 close 旧 ws
        assert returned_old.ws is old_ws

    def test_different_datasource_no_overwrite(self, router):
        """不同 datasource 不互相覆盖。"""
        conn_ncc = _make_conn(datasource="NCC")
        conn_u8 = _make_conn(datasource="U8")

        router.add_connection(conn_ncc)
        router.add_connection(conn_u8)

        assert router.get_connection("org-1", "NCC") is conn_ncc
        assert router.get_connection("org-1", "U8") is conn_u8


class TestRemoveConnection:
    """remove_connection 测试。"""

    def test_remove_connection(self, router):
        """移除连接后 get_connection 应返回 None。"""
        conn = _make_conn()
        router.add_connection(conn)

        removed = router.remove_connection("org-1", "NCC")
        assert removed is conn
        assert router.get_connection("org-1", "NCC") is None

    def test_remove_nonexistent(self, router):
        """移除不存在的连接应返回 None。"""
        removed = router.remove_connection("org-x", "NCC")
        assert removed is None


class TestGetAllForOrg:
    """get_all_for_org 测试。"""

    def test_get_all_for_org(self, router):
        """获取某企业所有连接。"""
        conn1 = _make_conn(org_id="org-1", datasource="NCC")
        conn2 = _make_conn(org_id="org-1", datasource="U8")
        conn3 = _make_conn(org_id="org-2", datasource="NCC")

        router.add_connection(conn1)
        router.add_connection(conn2)
        router.add_connection(conn3)

        org1_conns = router.get_all_for_org("org-1")
        assert len(org1_conns) == 2
        assert conn1 in org1_conns
        assert conn2 in org1_conns


class TestUpdateLastSeen:
    """update_last_seen 测试。"""

    def test_update_last_seen(self, router):
        """更新心跳时间。"""
        conn = _make_conn()
        old_time = conn.last_seen
        router.add_connection(conn)

        router.update_last_seen("org-1", "NCC")

        updated = router.get_connection("org-1", "NCC")
        assert updated.last_seen >= old_time
        assert updated.status == AgentStatus.ONLINE


class TestUpdateStatus:
    """update_status 测试。"""

    def test_update_status_degraded(self, router):
        """设置状态为 DEGRADED。"""
        conn = _make_conn()
        router.add_connection(conn)

        router.update_status("org-1", "NCC", AgentStatus.DEGRADED)

        updated = router.get_connection("org-1", "NCC")
        assert updated.status == AgentStatus.DEGRADED


class TestRedisSync:
    """Redis 同步测试。"""

    @pytest.mark.asyncio
    async def test_add_connection_syncs_to_redis(self, mock_redis):
        """添加连接应同步到 Redis。"""
        router = AgentRouter(redis_client=mock_redis)
        conn = _make_conn()

        router.add_connection(conn)

        # 等待异步任务完成
        import asyncio
        await asyncio.sleep(0.05)

        mock_redis.hset.assert_called_once()
        call_args = mock_redis.hset.call_args
        assert call_args[0][0] == "agent:route:org-1"
        assert call_args[0][1] == "NCC"

    @pytest.mark.asyncio
    async def test_remove_connection_deletes_from_redis(self, mock_redis):
        """移除连接应从 Redis 删除。"""
        router = AgentRouter(redis_client=mock_redis)
        conn = _make_conn()
        router.add_connection(conn)

        # 消费 add 的异步任务
        import asyncio
        await asyncio.sleep(0.05)

        router.remove_connection("org-1", "NCC")
        await asyncio.sleep(0.05)

        mock_redis.hdel.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_status_from_redis(self, mock_redis):
        """从 Redis 读取状态。"""
        redis_data = {
            b"NCC": json.dumps({
                "org_id": "org-1",
                "datasource": "NCC",
                "version": "1.0.0",
                "ip": "10.0.0.1",
                "last_seen": "2026-01-01T00:00:00+00:00",
                "status": "ONLINE",
            }).encode(),
        }
        mock_redis.hgetall = AsyncMock(return_value=redis_data)

        router = AgentRouter(redis_client=mock_redis)
        results = await router.get_status_from_redis("org-1")

        assert len(results) == 1
        assert results[0]["datasource"] == "NCC"
        assert results[0]["status"] == "ONLINE"


class TestAgentConnSerialization:
    """AgentConn 序列化测试。"""

    def test_to_redis_dict(self):
        """AgentConn 序列化应不含 ws 对象。"""
        conn = _make_conn()
        d = conn.to_redis_dict()

        assert "ws" not in d
        assert d["org_id"] == "org-1"
        assert d["datasource"] == "NCC"
        assert d["status"] == "ONLINE"

    def test_from_redis_dict(self):
        """从 Redis 字典反序列化。"""
        data = {
            "org_id": "org-1",
            "datasource": "NCC",
            "version": "1.0.0",
            "ip": "10.0.0.1",
            "last_seen": "2026-01-01T00:00:00+00:00",
            "status": "ONLINE",
        }
        result = AgentConn.from_redis_dict(data)
        assert result["org_id"] == "org-1"
        assert result["status"] == "ONLINE"
