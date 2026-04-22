"""集成测试 — 完整 WebSocket 生命周期。

测试流程：
创建企业 + 凭证 → WS 连接 + auth → register → heartbeat →
提交 task → 收到 result → 断开连接 → OFFLINE 检测

注意：此测试需要真实数据库连接（标记为 @pytest.mark.integration）。
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.services.agent.credential import CredentialService
from backend.app.services.agent.router import AgentRouter, AgentConn, AgentStatus
from backend.app.services.agent.heartbeat import HeartbeatService
from backend.app.services.agent.task_queue import TaskQueue, TaskStatus
from backend.app.services.agent.tracer import TracerService
from backend.app.services.agent.ws_handler import AgentWSHandler


@pytest.fixture
def router():
    return AgentRouter(redis_client=None)


@pytest.fixture
def tracer():
    return TracerService(redis_client=None)


@pytest.fixture
def task_queue(router, tracer):
    return TaskQueue(router=router, tracer=tracer)


@pytest.fixture
def credential_service():
    return CredentialService()


@pytest.fixture
def ws_handler(credential_service, router, task_queue, tracer):
    return AgentWSHandler(
        credential_service=credential_service,
        router=router,
        task_queue=task_queue,
        tracer=tracer,
    )


@pytest.fixture
def heartbeat_service(router):
    return HeartbeatService(router=router, redis_client=None)


class TestWSLifecycle:
    """完整的 WebSocket 生命周期集成测试。"""

    @pytest.mark.asyncio
    async def test_auth_register_heartbeat_task_result(
        self, ws_handler, router, task_queue, credential_service, heartbeat_service
    ):
        """完整生命周期：auth → register → heartbeat → task → result → disconnect。"""
        # 1. 生成凭证（mock DB）
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()

        cred_result = await credential_service.generate(mock_db, "org-1", "NCC")
        added_cred = mock_db.add.call_args[0][0]

        # 2. 模拟 WS 连接
        ws = AsyncMock()

        # 模拟凭证验证
        mock_db_execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = added_cred
        mock_db_execute.return_value = mock_result
        mock_db.execute = mock_db_execute

        # 3. auth 成功
        auth_msg = {
            "type": "auth",
            "client_id": cred_result["client_id"],
            "client_secret": cred_result["client_secret"],
        }
        cred = await ws_handler.handle_auth(ws, auth_msg, db_session=mock_db)
        assert cred is not None
        assert str(cred.org_id) == cred_result["org_id"]

        # 4. register 成功
        register_msg = {"type": "register", "version": "1.0.0"}
        conn = AgentConn(
            ws=ws,
            org_id=str(cred.org_id),
            datasource=cred.datasource,
            version="1.0.0",
            ip="10.0.0.1",
        )
        old = router.add_connection(conn)
        assert old is None
        assert router.get_connection(str(cred.org_id), "NCC") is not None

        # 5. heartbeat
        router.update_last_seen(str(cred.org_id), "NCC")
        conn_obj = router.get_connection(str(cred.org_id), "NCC")
        assert conn_obj.status == AgentStatus.ONLINE

        # 6. 提交 task
        result = await task_queue.submit(
            org_id=str(cred.org_id),
            datasource="NCC",
            action="query",
            payload={"sql": "SELECT * FROM users"},
        )
        assert result["status"] == TaskStatus.DISPATCHED.value
        assert result["msg_id"] is not None

        # 验证 ws.send_json 被调用
        ws.send_json.assert_called()

        # 7. ack
        task_queue.handle_ack(result["msg_id"])

        # 8. result
        await task_queue.handle_result(result["msg_id"], {"rows": [{"id": 1}]})

        # 9. 断开连接 → 清理路由表
        router.remove_connection(str(cred.org_id), "NCC")
        assert router.get_connection(str(cred.org_id), "NCC") is None

    @pytest.mark.asyncio
    async def test_heartbeat_timeout_flow(
        self, router, heartbeat_service
    ):
        """心跳超时流程：91s → DEGRADED → 105s → OFFLINE。"""
        from datetime import datetime, timedelta, timezone

        # 添加一个 91 秒未心跳的连接
        ws = AsyncMock()
        degraded_conn = AgentConn(
            ws=ws,
            org_id="org-1",
            datasource="NCC",
            version="1.0.0",
            ip="10.0.0.1",
            last_seen=datetime.now(timezone.utc) - timedelta(seconds=92),
        )
        router.add_connection(degraded_conn)

        # 检测
        degraded, offline = heartbeat_service.check_connections()
        assert len(degraded) == 1
        assert len(offline) == 0

        # 推到 105 秒
        degraded_conn.last_seen = datetime.now(timezone.utc) - timedelta(seconds=106)

        degraded, offline = heartbeat_service.check_connections()
        assert len(degraded) == 0
        assert len(offline) == 1
        # 路由表已清理
        assert router.get_connection("org-1", "NCC") is None

    @pytest.mark.asyncio
    async def test_task_offline_datasource(
        self, router, task_queue
    ):
        """数据源离线时提交任务应返回 DATASOURCE_OFFLINE。"""
        result = await task_queue.submit(
            org_id="org-nonexistent",
            datasource="NCC",
            action="query",
            payload={"sql": "SELECT 1"},
        )
        assert result["status"] == TaskStatus.DATASOURCE_OFFLINE.value

    @pytest.mark.asyncio
    async def test_trace_full_lifecycle(self, tracer):
        """全链追踪完整生命周期。"""
        # 创建 trace
        trace = tracer.create_trace("org-1", "NCC", "query_indicator", {"indicator": "营收"})

        # 添加 spans
        tracer.add_span(trace, "graphdb", "sparql_query", {"query": "SELECT ?s ?p ?o"})
        tracer.add_span(trace, "ws_server", "task_dispatched", {"msg_id": "msg_123"})
        tracer.add_span(trace, "erp_agent", "sql_executed", {"sql": "SELECT * FROM rev"})

        # SQL 脱敏
        raw_sql = "SELECT name FROM users WHERE id = '12345'"
        desensitized = tracer.desensitize_sql(raw_sql)
        assert "'12345'" not in desensitized
        assert "'***'" in desensitized

        # 完成
        tracer.update_status(trace, "COMPLETED")
        assert trace["status"] == "COMPLETED"
        assert trace["duration_ms"] >= 0
        assert len(trace["spans"]) == 4  # 初始1 + 3个添加

    @pytest.mark.asyncio
    async def test_sse_client_management(self, task_queue):
        """SSE 客户端注册和注销。"""
        import asyncio

        q1 = task_queue.register_sse_client()
        q2 = task_queue.register_sse_client()

        assert len(task_queue._sse_clients) == 2

        task_queue.unregister_sse_client(q1)
        assert len(task_queue._sse_clients) == 1

        task_queue.unregister_sse_client(q2)
        assert len(task_queue._sse_clients) == 0

    @pytest.mark.asyncio
    async def test_router_overwrite_old_connection(self, router):
        """新连接覆盖旧连接。"""
        old_ws = AsyncMock()
        old_conn = AgentConn(
            ws=old_ws, org_id="org-1", datasource="NCC",
            version="0.9.0", ip="10.0.0.1",
        )
        router.add_connection(old_conn)

        new_ws = AsyncMock()
        new_conn = AgentConn(
            ws=new_ws, org_id="org-1", datasource="NCC",
            version="1.0.0", ip="10.0.0.2",
        )
        returned_old = router.add_connection(new_conn)

        assert returned_old is old_conn
        current = router.get_connection("org-1", "NCC")
        assert current.version == "1.0.0"
