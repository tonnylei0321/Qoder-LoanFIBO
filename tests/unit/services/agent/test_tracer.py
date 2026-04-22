"""单元测试 — 全链追踪服务 TracerService。"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.services.agent.tracer import TracerService


@pytest.fixture
def tracer():
    """无 Redis 的追踪服务。"""
    return TracerService(redis_client=None)


@pytest.fixture
def mock_redis():
    return AsyncMock()


class TestCreateTrace:
    """create_trace 测试。"""

    def test_create_trace_generates_trace_id(self, tracer):
        """create_trace 应生成 trace_id 和首 span。"""
        trace = tracer.create_trace("org-1", "NCC", "query_indicator")

        assert trace["trace_id"].startswith("tr_")
        assert trace["org_id"] == "org-1"
        assert trace["datasource"] == "NCC"
        assert trace["action"] == "query_indicator"
        assert trace["status"] == "PENDING"
        assert len(trace["spans"]) == 1
        assert trace["spans"][0]["node"] == "saas_gateway"
        assert trace["spans"][0]["event"] == "trace_created"

    def test_create_trace_with_detail(self, tracer):
        """create_trace 支持传入 detail。"""
        trace = tracer.create_trace("org-1", "NCC", "query", detail={"indicator": "营收"})
        assert trace["spans"][0]["detail"]["indicator"] == "营收"


class TestAddSpan:
    """add_span 测试。"""

    def test_add_span_appends(self, tracer):
        """add_span 应追加 span。"""
        trace = tracer.create_trace("org-1", "NCC", "query")
        tracer.add_span(trace, "ws_server", "task_dispatched", {"msg_id": "m1"})

        assert len(trace["spans"]) == 2
        assert trace["spans"][1]["node"] == "ws_server"
        assert trace["spans"][1]["event"] == "task_dispatched"
        assert trace["spans"][1]["detail"]["msg_id"] == "m1"


class TestUpdateStatus:
    """update_status 测试。"""

    def test_update_status_computes_duration(self, tracer):
        """update_status 应更新状态并计算耗时。"""
        trace = tracer.create_trace("org-1", "NCC", "query")
        tracer.update_status(trace, "COMPLETED")

        assert trace["status"] == "COMPLETED"
        assert trace["duration_ms"] >= 0


class TestDesensitizeSQL:
    """desensitize_sql 测试。"""

    def test_desensitize_replaces_string_values(self):
        """SQL 脱敏应替换单引号内的值。"""
        sql = "SELECT name FROM users WHERE id = '12345' AND status = 'active'"
        result = TracerService.desensitize_sql(sql)
        assert "'***'" in result
        assert "'12345'" not in result
        assert "'active'" not in result
        assert "SELECT name FROM users WHERE" in result  # 保留结构

    def test_desensitize_preserves_structure(self):
        """脱敏后应保留表名和列名。"""
        sql = "SELECT * FROM fi_indicator WHERE org_id = 'uuid-123'"
        result = TracerService.desensitize_sql(sql)
        assert "fi_indicator" in result
        assert "org_id" in result
        assert "'uuid-123'" not in result

    def test_desensitize_no_strings(self):
        """无字符串值的 SQL 应原样返回。"""
        sql = "SELECT COUNT(*) FROM users"
        result = TracerService.desensitize_sql(sql)
        assert result == sql


class TestSaveToRedis:
    """save_to_redis 测试。"""

    @pytest.mark.asyncio
    async def test_save_to_redis_calls_xadd(self, mock_redis):
        """save_to_redis 应调用 Redis xadd。"""
        tracer = TracerService(redis_client=mock_redis)
        trace = tracer.create_trace("org-1", "NCC", "query")

        await tracer.save_to_redis(trace)

        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == "agent:trace:stream"
        data = call_args[0][1]
        assert data["trace_id"] == trace["trace_id"]

    @pytest.mark.asyncio
    async def test_save_to_redis_no_client(self, tracer):
        """无 Redis 客户端时 save_to_redis 不应报错。"""
        trace = tracer.create_trace("org-1", "NCC", "query")
        await tracer.save_to_redis(trace)  # 不应抛异常
