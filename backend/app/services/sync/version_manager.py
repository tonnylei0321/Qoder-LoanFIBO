"""版本管理器 - 映射数据版本快照的创建、发布、查询"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.publish_version import PublishVersion, VersionStatus


class VersionManager:
    """发布版本管理服务

    职责：
    - 创建映射数据版本快照（draft）
    - 发布版本（draft → published）
    - 标记同步完成（published → synced）
    - 查询版本详情和列表
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_snapshot(
        self,
        version_tag: str,
        description: Optional[str] = None,
        snapshot_data: Optional[Dict] = None,
        created_by: Optional[str] = None,
    ) -> PublishVersion:
        """创建版本快照

        如果 snapshot_data 为 None，则从当前映射表自动采集。
        """
        version_id = f"ver_{uuid.uuid4().hex[:12]}"

        if snapshot_data is None:
            snapshot_data = await self._collect_current_mappings()

        version = PublishVersion(
            id=version_id,
            version_tag=version_tag,
            description=description,
            status=VersionStatus.DRAFT.value,
            snapshot_data=snapshot_data,
            created_by=created_by,
        )
        self.db.add(version)
        await self.db.flush()
        logger.info(f"版本快照已创建: {version_tag} (id={version_id})")
        return version

    async def publish(self, version_id: str, description: Optional[str] = None) -> PublishVersion:
        """发布版本（draft → published）

        只有 draft 状态的版本可以发布。
        """
        version = await self._get_by_id(version_id)
        if version.status != VersionStatus.DRAFT.value:
            raise ValueError(f"版本 {version_id} 状态为 {version.status}，无法发布（仅 draft 可发布）")

        version.status = VersionStatus.PUBLISHED.value
        version.published_at = datetime.now(timezone.utc)
        if description:
            version.description = description

        await self.db.flush()
        logger.info(f"版本已发布: {version.version_tag} (id={version_id})")
        return version

    async def mark_synced(self, version_id: str) -> PublishVersion:
        """标记版本已同步（published → synced）"""
        version = await self._get_by_id(version_id)
        if version.status != VersionStatus.PUBLISHED.value:
            raise ValueError(f"版本 {version_id} 状态为 {version.status}，无法标记同步")

        version.status = VersionStatus.SYNCED.value
        version.synced_at = datetime.now(timezone.utc)
        await self.db.flush()
        logger.info(f"版本已同步: {version.version_tag} (id={version_id})")
        return version

    async def get_version(self, version_id: str) -> Optional[PublishVersion]:
        """获取版本详情"""
        stmt = select(PublishVersion).where(PublishVersion.id == version_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_versions(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[PublishVersion]:
        """列出版本，可按状态筛选"""
        stmt = select(PublishVersion).order_by(PublishVersion.created_at.desc())
        if status:
            stmt = stmt.where(PublishVersion.status == status)
        stmt = stmt.limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ─── 私有方法 ───────────────────────────────────────────────

    async def _get_by_id(self, version_id: str) -> PublishVersion:
        stmt = select(PublishVersion).where(PublishVersion.id == version_id)
        result = await self.db.execute(stmt)
        version = result.scalar_one_or_none()
        if version is None:
            raise ValueError(f"版本不存在: {version_id}")
        return version

    async def _collect_current_mappings(self) -> Dict[str, Any]:
        """从数据库采集当前映射数据作为快照"""
        # 采集 table_mapping 和 field_mapping 数据
        from backend.app.models.table_mapping import TableMapping, FieldMapping

        table_result = await self.db.execute(
            select(TableMapping).where(TableMapping.is_deleted == False)  # noqa: E712
        )
        tables = table_result.scalars().all()

        mappings = []
        for tm in tables:
            field_result = await self.db.execute(
                select(FieldMapping).where(
                    FieldMapping.table_mapping_id == tm.id,
                    FieldMapping.is_deleted == False,  # noqa: E712
                )
            )
            fields = field_result.scalars().all()
            mappings.append({
                "table_name": tm.table_name,
                "fibo_class_uri": tm.fibo_class_uri,
                "confidence_level": tm.confidence_level,
                "fields": [
                    {
                        "field_name": f.field_name,
                        "fibo_property_uri": f.fibo_property_uri,
                        "proj_ext_uri": f.proj_ext_uri,
                    }
                    for f in fields
                ],
            })

        return {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "table_count": len(mappings),
            "mappings": mappings,
        }
