"""GraphDB 实例管理器单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.models.graphdb_instance import GraphDBInstance
from backend.app.services.sync.instance_manager import InstanceManager


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def instance_manager(mock_db):
    return InstanceManager(mock_db)


@pytest.fixture
def sample_instance():
    return GraphDBInstance(
        id="inst_abc123",
        name="测试实例",
        server_url="http://localhost:7200",
        repo_id="loanfibo",
        namespace_prefix="loanfibo",
    )


class TestInstanceManagerHealthCheck:
    @pytest.mark.asyncio
    async def test_healthy_instance(self, instance_manager, sample_instance):
        """测试健康的 GraphDB 实例"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"total": 12345}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await instance_manager.health_check(sample_instance)

            assert result.status == "healthy"
            assert result.statement_count == 12345
            assert result.instance_id == "inst_abc123"

    @pytest.mark.asyncio
    async def test_unhealthy_instance(self, instance_manager, sample_instance):
        """测试不健康的 GraphDB 实例"""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await instance_manager.health_check(sample_instance)
            assert result.status == "unhealthy"

    @pytest.mark.asyncio
    async def test_unreachable_instance(self, instance_manager, sample_instance):
        """测试不可达的 GraphDB 实例"""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client_cls.return_value = mock_client

            result = await instance_manager.health_check(sample_instance)
            assert result.status == "unreachable"


class TestInstanceManagerGetStatistics:
    @pytest.mark.asyncio
    async def test_get_statistics_accessible(self, instance_manager, sample_instance):
        """测试获取统计信息 - 可访问"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": {"bindings": [{"count": {"value": "5000"}}]}
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await instance_manager.get_statistics(sample_instance)
            assert result["status"] == "accessible"
            assert result["statement_count"] == 5000
