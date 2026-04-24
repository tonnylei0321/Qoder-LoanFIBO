"""同步调度器单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.models.sync_task import SyncTask
from backend.app.models.publish_version import PublishVersion, VersionStatus
from backend.app.models.graphdb_instance import GraphDBInstance
from backend.app.services.sync.sync_scheduler import SyncScheduler


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def scheduler(mock_db):
    return SyncScheduler(mock_db)


@pytest.fixture
def published_version():
    return PublishVersion(
        id="ver_published",
        version_tag="v1.0.0",
        status=VersionStatus.PUBLISHED.value,
        snapshot_data={"mappings": [{"table_name": "t1", "fibo_class_uri": "http://fibo/Cls", "fields": []}]},
    )


@pytest.fixture
def active_instance():
    return GraphDBInstance(
        id="inst_active",
        name="测试实例",
        server_url="http://localhost:7200",
        repo_id="loanfibo",
        namespace_prefix="loanfibo",
        is_active=True,
    )


class TestSyncSchedulerCreateTask:
    @pytest.mark.asyncio
    async def test_create_task_success(self, scheduler, mock_db, published_version, active_instance):
        """测试创建同步任务成功"""
        # 模拟版本查询
        version_result = MagicMock()
        version_result.scalar_one_or_none = MagicMock(return_value=published_version)
        # 模拟实例查询
        instance_result = MagicMock()
        instance_result.scalar_one_or_none = MagicMock(return_value=active_instance)

        mock_db.execute = AsyncMock(side_effect=[version_result, instance_result])

        task = await scheduler.create_task("ver_published", "inst_active")
        mock_db.add.assert_called_once()
        added = mock_db.add.call_args[0][0]
        assert added.version_id == "ver_published"
        assert added.instance_id == "inst_active"
        assert added.status == "pending"
        assert added.mode == "upsert"

    @pytest.mark.asyncio
    async def test_create_task_unpublished_version_raises(self, scheduler, mock_db):
        """测试未发布版本创建任务抛出异常"""
        draft_version = PublishVersion(
            id="ver_draft",
            version_tag="v0.1",
            status=VersionStatus.DRAFT.value,
        )
        version_result = MagicMock()
        version_result.scalar_one_or_none = MagicMock(return_value=draft_version)
        mock_db.execute = AsyncMock(return_value=version_result)

        with pytest.raises(ValueError, match="尚未发布"):
            await scheduler.create_task("ver_draft", "inst_active")

    @pytest.mark.asyncio
    async def test_create_task_inactive_instance_raises(self, scheduler, mock_db, published_version):
        """测试停用实例创建任务抛出异常"""
        inactive = GraphDBInstance(
            id="inst_inactive",
            name="停用实例",
            server_url="http://localhost:7200",
            repo_id="loanfibo",
            is_active=False,
        )
        version_result = MagicMock()
        version_result.scalar_one_or_none = MagicMock(return_value=published_version)
        instance_result = MagicMock()
        instance_result.scalar_one_or_none = MagicMock(return_value=inactive)
        mock_db.execute = AsyncMock(side_effect=[version_result, instance_result])

        with pytest.raises(ValueError, match="已停用"):
            await scheduler.create_task("ver_published", "inst_inactive")


class TestSyncSchedulerExecute:
    @pytest.mark.asyncio
    async def test_execute_sync_success(self, scheduler, mock_db, published_version, active_instance):
        """测试同步执行成功"""
        task = SyncTask(
            id="sync_test",
            version_id="ver_published",
            instance_id="inst_active",
            mode="upsert",
            status="pending",
        )

        # 模拟多次 DB 查询
        task_result = MagicMock()
        task_result.scalar_one_or_none = MagicMock(return_value=task)

        version_result = MagicMock()
        version_result.scalar_one_or_none = MagicMock(return_value=published_version)

        instance_result = MagicMock()
        instance_result.scalar_one_or_none = MagicMock(return_value=active_instance)

        mock_db.execute = AsyncMock(side_effect=[task_result, version_result, instance_result])
        mock_db.flush = AsyncMock()

        with patch.object(scheduler, '_write_to_graphdb', new_callable=AsyncMock):
            result = await scheduler.execute_sync("sync_test")

        assert result.status == "completed"
        assert result.progress == 1.0
        assert result.triples_synced > 0

    @pytest.mark.asyncio
    async def test_execute_sync_failure(self, scheduler, mock_db, published_version, active_instance):
        """测试同步执行失败"""
        task = SyncTask(
            id="sync_fail",
            version_id="ver_published",
            instance_id="inst_active",
            mode="upsert",
            status="pending",
        )

        task_result = MagicMock()
        task_result.scalar_one_or_none = MagicMock(return_value=task)
        version_result = MagicMock()
        version_result.scalar_one_or_none = MagicMock(return_value=published_version)
        instance_result = MagicMock()
        instance_result.scalar_one_or_none = MagicMock(return_value=active_instance)

        mock_db.execute = AsyncMock(side_effect=[task_result, version_result, instance_result])
        mock_db.flush = AsyncMock()

        with patch.object(scheduler, '_write_to_graphdb', new_callable=AsyncMock, side_effect=Exception("GraphDB 连接失败")):
            result = await scheduler.execute_sync("sync_fail")

        assert result.status == "failed"
        assert "GraphDB 连接失败" in result.error_message
