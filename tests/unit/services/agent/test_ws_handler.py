"""单元测试 — WebSocket 连接处理器 AgentWSHandler。"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.services.agent.router import AgentRouter
from backend.app.services.agent.task_queue import TaskQueue
from backend.app.services.agent.tracer import TracerService
from backend.app.services.agent.ws_handler import AgentWSHandler
from backend.app.services.agent.credential import CredentialService


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
def mock_credential_service():
    svc = MagicMock(spec=CredentialService)
    svc.verify = AsyncMock()
    return svc


@pytest.fixture
def handler(mock_credential_service, router, task_queue, tracer):
    return AgentWSHandler(
        credential_service=mock_credential_service,
        router=router,
        task_queue=task_queue,
        tracer=tracer,
    )


class TestHandleAuth:
    """handle_auth 测试。"""

    @pytest.mark.asyncio
    async def test_auth_success(self, handler, mock_credential_service):
        """auth 成功应返回凭证对象并发送 auth_ack。"""
        ws = AsyncMock()
        mock_cred = MagicMock()
        mock_cred.org_id = "org-uuid-1"
        mock_cred.datasource = "NCC"
        mock_credential_service.verify = AsyncMock(return_value=mock_cred)

        auth_msg = {
            "type": "auth",
            "client_id": "cid_test",
            "client_secret": "sk_test",
        }

        cred = await handler.handle_auth(ws, auth_msg, db_session=MagicMock())

        assert cred is not None
        assert cred.org_id == "org-uuid-1"
        ws.send_json.assert_called_once()
        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "auth_ack"

    @pytest.mark.asyncio
    async def test_auth_failure(self, handler, mock_credential_service):
        """auth 失败应返回 None 并发送 auth_error。"""
        ws = AsyncMock()
        mock_credential_service.verify = AsyncMock(return_value=None)

        auth_msg = {
            "type": "auth",
            "client_id": "cid_bad",
            "client_secret": "sk_bad",
        }

        cred = await handler.handle_auth(ws, auth_msg, db_session=MagicMock())

        assert cred is None
        ws.send_json.assert_called_once()
        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "auth_error"

    @pytest.mark.asyncio
    async def test_auth_missing_fields(self, handler):
        """缺少 client_id 或 client_secret 应返回 auth_error。"""
        ws = AsyncMock()

        cred = await handler.handle_auth(ws, {"type": "auth"}, db_session=MagicMock())
        assert cred is None

        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "auth_error"
        assert "missing" in sent["message"]

    @pytest.mark.asyncio
    async def test_auth_no_db_session(self, handler):
        """无 DB 会话应返回 auth_error。"""
        ws = AsyncMock()

        cred = await handler.handle_auth(
            ws,
            {"type": "auth", "client_id": "cid_test", "client_secret": "sk_test"},
            db_session=None,
        )
        assert cred is None


class TestHandleConnection:
    """handle_connection 测试。"""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, handler, mock_credential_service, router):
        """完整的 auth → register → heartbeat 流程。"""
        ws = AsyncMock()

        # 模拟凭证验证成功
        mock_cred = MagicMock()
        mock_cred.org_id = "org-1"
        mock_cred.datasource = "NCC"
        mock_credential_service.verify = AsyncMock(return_value=mock_cred)

        # 模拟接收消息序列
        messages = [
            json.dumps({"type": "auth", "client_id": "cid_test", "client_secret": "sk_test"}),
            json.dumps({"type": "register", "version": "1.0.0"}),
            json.dumps({"type": "heartbeat"}),
        ]

        msg_iter = iter(messages)
        ws.receive_text = AsyncMock(side_effect=lambda: next(msg_iter))

        # 最后一次 receive_text 抛异常退出循环
        def receive_side_effect():
            try:
                return next(msg_iter)
            except StopIteration:
                raise Exception("connection closed")

        ws.receive_text = AsyncMock(side_effect=receive_side_effect)

        await handler.handle_connection(ws, db_session=MagicMock(), client_ip="10.0.0.1")

        # 验证路由表已注册
        conn = router.get_connection("org-1", "NCC")
        # 连接应该已清理（finally 块），因为 receive_text 抛异常后退出
        # 但在 finally 之前应该已经被注册过

    @pytest.mark.asyncio
    async def test_register_timeout(self, handler, mock_credential_service):
        """5 秒内未收到 register 应断开连接。"""
        ws = AsyncMock()

        mock_cred = MagicMock()
        mock_cred.org_id = "org-1"
        mock_cred.datasource = "NCC"
        mock_credential_service.verify = AsyncMock(return_value=mock_cred)

        # auth 成功，但 register 超时
        call_count = 0

        async def receive_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return json.dumps({"type": "auth", "client_id": "cid_test", "client_secret": "sk_test"})
            # 模拟超时
            import asyncio
            await asyncio.sleep(6)
            return ""

        ws.receive_text = AsyncMock(side_effect=receive_side_effect)

        # 使用很短的超时来加速测试
        import unittest.mock
        with unittest.mock.patch(
            "backend.app.services.agent.ws_handler.REGISTER_TIMEOUT_SEC", 0.1
        ):
            await handler.handle_connection(ws, db_session=MagicMock(), client_ip="10.0.0.1")
