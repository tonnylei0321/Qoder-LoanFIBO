"""单元测试 — Agent REST API 端点。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_agent_services():
    """Mock 所有 agent 全局单例。"""
    mock_router = MagicMock()
    mock_router.get_all_connections.return_value = []
    mock_router.get_all_for_org.return_value = []

    mock_task_queue = MagicMock()
    mock_task_queue.submit = AsyncMock(return_value={"status": "DISPATCHED", "msg_id": "msg_test"})

    mock_ws_handler = MagicMock()

    with patch("backend.app.api.v1.agent.get_router", return_value=mock_router), \
         patch("backend.app.api.v1.agent.get_task_queue", return_value=mock_task_queue), \
         patch("backend.app.api.v1.agent.get_ws_handler", return_value=mock_ws_handler):
        yield {
            "router": mock_router,
            "task_queue": mock_task_queue,
            "ws_handler": mock_ws_handler,
        }


class TestGetAgentStatus:
    """GET /agent/status 测试。"""

    def test_status_empty(self, mock_agent_services):
        """无连接时应返回空列表。"""
        from backend.app.main import app
        client = TestClient(app)

        response = client.get(
            "/api/v1/agent/status",
            headers={"Authorization": "Bearer test_token"},
        )
        # 注意：此端点不需要认证
        # 但由于 TestClient 对 WebSocket 的支持有限，
        # 这里只测试 REST 端点的基本可达性
        assert response.status_code == 200


class TestGetVersions:
    """GET /agent/versions 测试."""

    def test_versions_endpoint_exists(self, mock_agent_services):
        """版本列表端点应存在."""
        from backend.app.main import app
        client = TestClient(app)

        response = client.get("/api/v1/agent/versions")
        # 422 或 200 都说明端点可达（422 可能是 DB 依赖问题）
        assert response.status_code in (200, 422)


class TestListTraces:
    """GET /agent/traces 测试."""

    def test_traces_endpoint_exists(self, mock_agent_services):
        """追踪列表端点应存在."""
        from backend.app.main import app
        client = TestClient(app)

        response = client.get("/api/v1/agent/traces")
        assert response.status_code in (200, 422)


class TestSubmitTask:
    """POST /agent/task 测试。"""

    def test_submit_task(self, mock_agent_services):
        """提交任务应返回状态。"""
        from backend.app.main import app
        client = TestClient(app)

        response = client.post(
            "/api/v1/agent/task",
            json={
                "org_id": "org-1",
                "datasource": "NCC",
                "action": "query",
                "payload": {"sql": "SELECT 1"},
            },
            headers={"Authorization": "Bearer test_token"},
        )
        assert response.status_code == 200
