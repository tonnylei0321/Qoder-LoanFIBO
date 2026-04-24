"""版本管理器单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.models.publish_version import PublishVersion, VersionStatus
from backend.app.services.sync.version_manager import VersionManager


@pytest.fixture
def mock_db():
    """模拟 AsyncSession"""
    db = AsyncMock()
    return db


@pytest.fixture
def version_manager(mock_db):
    return VersionManager(mock_db)


@pytest.fixture
def sample_version():
    return PublishVersion(
        id="ver_abc123456789",
        version_tag="v1.0.0",
        description="初始版本",
        status=VersionStatus.DRAFT.value,
        snapshot_data={"table_count": 5, "mappings": []},
        created_by="admin",
    )


class TestVersionManagerCreateSnapshot:
    @pytest.mark.asyncio
    async def test_create_with_explicit_snapshot(self, version_manager, mock_db):
        """测试显式传入快照数据创建版本"""
        snapshot = {"table_count": 3, "mappings": [{"table_name": "t1"}]}

        result = await version_manager.create_snapshot(
            version_tag="v1.0.0",
            description="测试版本",
            snapshot_data=snapshot,
            created_by="admin",
        )

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.version_tag == "v1.0.0"
        assert added_obj.status == VersionStatus.DRAFT.value
        assert added_obj.snapshot_data == snapshot
        assert added_obj.created_by == "admin"
        assert added_obj.id.startswith("ver_")

    @pytest.mark.asyncio
    async def test_create_auto_collects_snapshot(self, version_manager, mock_db):
        """测试不传快照时自动采集映射数据"""
        # 模拟 _collect_current_mappings
        with patch.object(version_manager, '_collect_current_mappings', new_callable=AsyncMock) as mock_collect:
            mock_collect.return_value = {"table_count": 0, "mappings": []}

            await version_manager.create_snapshot(version_tag="v2.0.0")

            mock_collect.assert_called_once()
            added_obj = mock_db.add.call_args[0][0]
            assert added_obj.snapshot_data == {"table_count": 0, "mappings": []}


class TestVersionManagerPublish:
    @pytest.mark.asyncio
    async def test_publish_draft_version(self, version_manager, mock_db, sample_version):
        """测试发布 draft 版本"""
        mock_db.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=sample_version)
        )

        result = await version_manager.publish("ver_abc123456789")

        assert result.status == VersionStatus.PUBLISHED.value
        assert result.published_at is not None
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_non_draft_raises(self, version_manager, mock_db, sample_version):
        """测试非 draft 版本发布抛出异常"""
        sample_version.status = VersionStatus.PUBLISHED.value
        mock_db.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=sample_version)
        )

        with pytest.raises(ValueError, match="无法发布"):
            await version_manager.publish("ver_abc123456789")


class TestVersionManagerMarkSynced:
    @pytest.mark.asyncio
    async def test_mark_synced(self, version_manager, mock_db, sample_version):
        """测试标记同步完成"""
        sample_version.status = VersionStatus.PUBLISHED.value
        mock_db.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=sample_version)
        )

        result = await version_manager.mark_synced("ver_abc123456789")

        assert result.status == VersionStatus.SYNCED.value
        assert result.synced_at is not None

    @pytest.mark.asyncio
    async def test_mark_synced_non_published_raises(self, version_manager, mock_db, sample_version):
        """测试非 published 版本标记同步抛出异常"""
        sample_version.status = VersionStatus.DRAFT.value
        mock_db.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=sample_version)
        )

        with pytest.raises(ValueError, match="无法标记同步"):
            await version_manager.mark_synced("ver_abc123456789")


class TestVersionManagerGetVersion:
    @pytest.mark.asyncio
    async def test_get_existing_version(self, version_manager, mock_db, sample_version):
        """测试获取存在的版本"""
        mock_db.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=sample_version)
        )

        result = await version_manager.get_version("ver_abc123456789")
        assert result is not None
        assert result.version_tag == "v1.0.0"

    @pytest.mark.asyncio
    async def test_get_nonexistent_version(self, version_manager, mock_db):
        """测试获取不存在的版本"""
        mock_db.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=None)
        )

        result = await version_manager.get_version("ver_nonexistent")
        assert result is None


class TestVersionManagerListVersions:
    @pytest.mark.asyncio
    async def test_list_all_versions(self, version_manager, mock_db):
        """测试列出所有版本"""
        mock_db.execute.return_value = MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )

        result = await version_manager.list_versions()
        assert result == []

    @pytest.mark.asyncio
    async def test_list_versions_with_status_filter(self, version_manager, mock_db):
        """测试按状态筛选版本"""
        mock_db.execute.return_value = MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )

        result = await version_manager.list_versions(status="draft")
        assert result == []
        # 验证 execute 被调用了
        mock_db.execute.assert_called_once()
