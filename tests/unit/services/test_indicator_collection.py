"""单元测试 — 指标采集管道 IndicatorCollectionPipeline。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.services.indicator_collection import IndicatorCollectionPipeline
from backend.app.services.agent.router import AgentRouter, AgentConn, AgentStatus
from backend.app.services.agent.task_queue import TaskQueue, TaskStatus


@pytest.fixture
def router():
    return AgentRouter(redis_client=None)


@pytest.fixture
def mock_task_queue():
    tq = MagicMock(spec=TaskQueue)
    tq.submit = AsyncMock()
    return tq


@pytest.fixture
def pipeline(router, mock_task_queue):
    return IndicatorCollectionPipeline(router=router, task_queue=mock_task_queue)


def _make_conn(org_id="org-1", datasource="NCC", status=AgentStatus.ONLINE):
    ws = AsyncMock()
    return AgentConn(
        ws=ws, org_id=org_id, datasource=datasource,
        version="1.0.0", ip="127.0.0.1", status=status,
    )


class TestCollectAll:
    """collect_all 测试。"""

    @pytest.mark.asyncio
    async def test_no_connections_returns_zeros(self, pipeline):
        """无连接时应返回全零。"""
        result = await pipeline.collect_all()
        assert result["dispatched"] == 0
        assert result["offline"] == 0
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_online_connection_dispatched(self, pipeline, router, mock_task_queue):
        """在线连接应派发采集任务。"""
        conn = _make_conn()
        router.add_connection(conn)

        mock_task_queue.submit.return_value = {
            "status": TaskStatus.DISPATCHED.value,
            "msg_id": "msg_test",
        }

        result = await pipeline.collect_all()
        assert result["dispatched"] == 1
        assert result["offline"] == 0
        mock_task_queue.submit.assert_called_once()

    @pytest.mark.asyncio
    async def test_degraded_connection_counted_as_offline(self, pipeline, router, mock_task_queue):
        """DEGRADED 状态的连接不计为派发。"""
        conn = _make_conn(status=AgentStatus.DEGRADED)
        router.add_connection(conn)

        result = await pipeline.collect_all()
        assert result["dispatched"] == 0
        assert result["offline"] == 1

    @pytest.mark.asyncio
    async def test_offline_connection_counted_as_offline(self, pipeline, router, mock_task_queue):
        """OFFLINE 状态的连接不计为派发。"""
        conn = _make_conn(status=AgentStatus.OFFLINE)
        router.add_connection(conn)

        result = await pipeline.collect_all()
        assert result["dispatched"] == 0
        assert result["offline"] == 1


class TestCollectForOrg:
    """collect_for_org 测试。"""

    @pytest.mark.asyncio
    async def test_offline_org_returns_offline_status(self, pipeline):
        """离线企业应返回 DATASOURCE_OFFLINE。"""
        result = await pipeline.collect_for_org("org-1", "NCC")
        assert result["status"] == TaskStatus.DATASOURCE_OFFLINE.value

    @pytest.mark.asyncio
    async def test_online_org_dispatches_task(self, pipeline, router, mock_task_queue):
        """在线企业应派发采集任务。"""
        conn = _make_conn()
        router.add_connection(conn)

        mock_task_queue.submit.return_value = {
            "status": TaskStatus.DISPATCHED.value,
            "msg_id": "msg_test",
        }

        result = await pipeline.collect_for_org("org-1", "NCC")
        assert result["status"] == TaskStatus.DISPATCHED.value
        mock_task_queue.submit.assert_called_once()
