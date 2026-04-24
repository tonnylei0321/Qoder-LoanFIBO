"""同步调度器 - 创建/执行/追踪同步任务"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.sync_task import SyncTask
from backend.app.models.publish_version import PublishVersion, VersionStatus
from backend.app.models.graphdb_instance import GraphDBInstance


class SyncScheduler:
    """同步任务调度服务

    职责：
    - 创建同步任务
    - 执行同步（将 RDF 三元组写入 GraphDB）
    - 追踪进度
    - 支持 upsert / replace 两种模式
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_task(
        self,
        version_id: str,
        instance_id: str,
        mode: str = "upsert",
    ) -> SyncTask:
        """创建同步任务

        验证版本已发布、实例可用后才创建任务。
        """
        # 验证版本
        version = await self.db.execute(
            select(PublishVersion).where(PublishVersion.id == version_id)
        )
        ver = version.scalar_one_or_none()
        if ver is None:
            raise ValueError(f"版本不存在: {version_id}")
        if ver.status != VersionStatus.PUBLISHED.value:
            raise ValueError(f"版本 {version_id} 尚未发布，无法同步")

        # 验证实例
        inst = await self.db.execute(
            select(GraphDBInstance).where(GraphDBInstance.id == instance_id)
        )
        instance = inst.scalar_one_or_none()
        if instance is None:
            raise ValueError(f"实例不存在: {instance_id}")
        if not instance.is_active:
            raise ValueError(f"实例 {instance_id} 已停用")

        task = SyncTask(
            version_id=version_id,
            instance_id=instance_id,
            mode=mode,
            status="pending",
        )
        self.db.add(task)
        await self.db.flush()
        logger.info(f"同步任务已创建: {task.id}")
        return task

    async def execute_sync(self, task_id: str) -> SyncTask:
        """执行同步任务

        将版本快照数据转换为 RDF 三元组并写入 GraphDB。
        """
        task = await self._get_by_id(task_id)
        task.status = "running"
        task.progress = 0.0
        await self.db.flush()

        try:
            # 获取版本数据
            ver_result = await self.db.execute(
                select(PublishVersion).where(PublishVersion.id == task.version_id)
            )
            version = ver_result.scalar_one_or_none()
            if version is None or version.snapshot_data is None:
                raise ValueError("版本数据不存在")

            # 获取实例信息
            inst_result = await self.db.execute(
                select(GraphDBInstance).where(GraphDBInstance.id == task.instance_id)
            )
            instance = inst_result.scalar_one_or_none()
            if instance is None:
                raise ValueError("实例不存在")

            # 生成 RDF 三元组
            from backend.app.services.sync.rdf_generator import RDFGenerator
            generator = RDFGenerator(namespace_prefix=instance.namespace_prefix)
            mappings = version.snapshot_data.get("mappings", [])
            triples = generator.generate_three_layer_triples(mappings)

            task.progress = 0.5
            await self.db.flush()

            # 写入 GraphDB
            turtle_data = generator.generate_turtle(triples)
            await self._write_to_graphdb(instance, turtle_data, task.mode)

            task.status = "completed"
            task.progress = 1.0
            task.triples_synced = len(triples)
            task.completed_at = datetime.now(timezone.utc)

            # 标记版本已同步
            version.status = VersionStatus.SYNCED.value
            version.synced_at = datetime.now(timezone.utc)

            await self.db.flush()
            logger.info(f"同步任务完成: {task_id}, {len(triples)} 条三元组")

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            await self.db.flush()
            logger.error(f"同步任务失败: {task_id} - {e}")

        return task

    async def get_task(self, task_id: str) -> Optional[SyncTask]:
        """获取任务"""
        return await self._get_by_id(task_id)

    # ─── 私有方法 ───────────────────────────────────────────────

    async def _get_by_id(self, task_id: str) -> SyncTask:
        result = await self.db.execute(
            select(SyncTask).where(SyncTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if task is None:
            raise ValueError(f"同步任务不存在: {task_id}")
        return task

    async def _write_to_graphdb(
        self,
        instance: GraphDBInstance,
        turtle_data: str,
        mode: str,
    ) -> None:
        """将 Turtle 数据写入 GraphDB"""
        import httpx

        url = f"{instance.server_url.rstrip('/')}/repositories/{instance.repo_id}/statements"
        headers = {"Content-Type": "text/turtle"}

        if mode == "replace":
            # 先清空仓库
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.delete(url)

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, content=turtle_data, headers=headers)
            resp.raise_for_status()
