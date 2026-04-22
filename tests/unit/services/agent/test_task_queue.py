"""单元测试 — 任务队列 + 状态机 TaskQueue。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.services.agent.router import AgentConn, AgentRouter, AgentStatus
from backend.app.services.agent.task_queue import (
    MAX_PENDING_TASKS,
    TaskQueue,
    TaskStatus,
)
from backend.app.services.agent.tracer import TracerService


@pytest.fixture
def router():
    return AgentRouter(redis_client=None)


@pytest.fixture
def tracer():
    return TracerService(redis_client=None)


@pytest.fixture
def queue(router, tracer):
    return TaskQueue(router=router, tracer=tracer)


def _make_conn(org_id="org-1", datasource="NCC"):
    ws = AsyncMock()
    return AgentConn(
        ws=ws, org_id=org_id, datasource=datasource,
        version="1.0.0", ip="127.0.0.1",
    )


class TestTaskStatusEnum:
    """TaskStatus 枚举值测试。"""

    def test_all_status_values(self):
        """应有 9 种状态。"""
        expected = {
            "PENDING", "DISPATCHED", "EXECUTING", "COMPLETED",
            "ERROR", "AGENT_UNREACHABLE", "TASK_TIMEOUT",
            "DATASOURCE_OFFLINE", "SERVICE_OVERLOAD",
        }
        actual = {s.value for s in TaskStatus}
        assert actual == expected


class TestSubmit:
    """submit() 测试。"""

    @pytest.mark.asyncio
    async def test_submit_offline_returns_datasource_offline(self, queue, router):
        """路由表无记录时 submit 应立即返回 DATASOURCE_OFFLINE。"""
        result = await queue.submit(
            org_id="org-1", datasource="NCC",
            action="query", payload={"sql": "SELECT 1"},
        )

        assert result["status"] == TaskStatus.DATASOURCE_OFFLINE.value
        assert result["msg_id"] is None

    @pytest.mark.asyncio
    async def test_submit_dispatches_to_agent(self, queue, router):
        """路由表有记录时 submit 应推送 task 到代理。"""
        conn = _make_conn()
        router.add_connection(conn)

        result = await queue.submit(
            org_id="org-1", datasource="NCC",
            action="query", payload={"sql": "SELECT 1"},
        )

        assert result["status"] == TaskStatus.DISPATCHED.value
        assert result["msg_id"] is not None
        conn.ws.send_json.assert_called_once()

        # 验证发送的消息
        sent_msg = conn.ws.send_json.call_args[0][0]
        assert sent_msg["type"] == "task"
        assert sent_msg["action"] == "query"

    @pytest.mark.asyncio
    async def test_submit_overload_returns_service_overload(self, router, tracer):
        """pending_tasks 超过上限时返回 SERVICE_OVERLOAD。"""
        queue = TaskQueue(router=router, tracer=tracer)

        # 填满 pending_tasks
        for i in range(MAX_PENDING_TASKS + 1):
            queue._pending_tasks[f"msg_{i}"] = MagicMock()

        result = await queue.submit(
            org_id="org-1", datasource="NCC",
            action="query", payload={},
        )

        assert result["status"] == TaskStatus.SERVICE_OVERLOAD.value


class TestHandleAck:
    """handle_ack() 测试。"""

    @pytest.mark.asyncio
    async def test_handle_ack_updates_status(self, queue, router):
        """handle_ack 应更新任务状态为 EXECUTING。"""
        conn = _make_conn()
        router.add_connection(conn)

        result = await queue.submit(
            org_id="org-1", datasource="NCC",
            action="query", payload={},
        )
        msg_id = result["msg_id"]

        queue.handle_ack(msg_id)

        task = queue._pending_tasks.get(msg_id)
        assert task.status == TaskStatus.EXECUTING

    def test_handle_ack_unknown_msg_id(self, queue):
        """未知 msg_id 的 ack 不应报错。"""
        queue.handle_ack("msg_nonexistent")  # 不应抛异常


class TestHandleResult:
    """handle_result() 测试。"""

    @pytest.mark.asyncio
    async def test_handle_result_resolves_future(self, queue, router):
        """handle_result 应 resolve Future 并返回数据。"""
        conn = _make_conn()
        router.add_connection(conn)

        result = await queue.submit(
            org_id="org-1", datasource="NCC",
            action="query", payload={},
        )
        msg_id = result["msg_id"]
        queue.handle_ack(msg_id)

        await queue.handle_result(msg_id, {"rows": [{"id": 1}]})

        task = queue._pending_tasks.get(msg_id)
        assert task is None  # 已清理


class TestSSE:
    """SSE 客户端注册/注销测试。"""

    def test_register_sse_client(self, queue):
        """注册 SSE 客户端应返回 asyncio.Queue。"""
        q = queue.register_sse_client()
        assert isinstance(q, asyncio.Queue)
        assert q in queue._sse_clients

    def test_unregister_sse_client(self, queue):
        """注销 SSE 客户端应从列表中移除。"""
        q = queue.register_sse_client()
        queue.unregister_sse_client(q)
        assert q not in queue._sse_clients
