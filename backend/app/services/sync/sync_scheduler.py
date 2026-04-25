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

        验证版本存在、实例可用后才创建任务。不再要求 published 状态。
        """
        # 验证版本
        version = await self.db.execute(
            select(PublishVersion).where(PublishVersion.id == version_id)
        )
        ver = version.scalar_one_or_none()
        if ver is None:
            raise ValueError(f"版本不存在: {version_id}")
        if not ver.ttl_file_path:
            raise ValueError(f"版本 {version_id} 未上传 TTL 文件，无法同步")

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

        直接读取版本关联的 TTL 文件，导入到 GraphDB。
        """
        import os
        import httpx
        from pathlib import Path

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
            if version is None or not version.ttl_file_path:
                raise ValueError("版本数据不存在或未上传 TTL 文件")

            # 获取实例信息
            inst_result = await self.db.execute(
                select(GraphDBInstance).where(GraphDBInstance.id == task.instance_id)
            )
            instance = inst_result.scalar_one_or_none()
            if instance is None:
                raise ValueError("实例不存在")

            # 读取 TTL 文件
            ttl_path = Path(version.ttl_file_path)
            if not ttl_path.exists():
                raise ValueError(f"TTL 文件不存在: {ttl_path}")

            ttl_content = ttl_path.read_text(encoding="utf-8")
            task.progress = 0.1
            await self.db.flush()

            # GraphDB 导入 URL
            url = f"{instance.server_url.rstrip('/')}/repositories/{instance.repo_id}/statements"
            headers = {"Content-Type": "text/turtle"}

            # replace 模式：先清空仓库
            if task.mode == "replace":
                async with httpx.AsyncClient(timeout=30.0) as client:
                    await client.delete(url)
                task.progress = 0.3
                await self.db.flush()

            # 将 TTL 内容分块导入（按行分割，每 500 行一批）
            lines = ttl_content.split("\n")
            total_lines = len(lines)
            batch_size = 500
            total_synced = 0

            for i in range(0, total_lines, batch_size):
                batch = "\n".join(lines[i:i + batch_size])
                if not batch.strip():
                    continue

                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(url, content=batch, headers=headers)
                    resp.raise_for_status()

                total_synced += min(batch_size, total_lines - i)
                # 进度: 0.3 ~ 0.9 按比例
                task.progress = 0.3 + 0.6 * min(1.0, (i + batch_size) / total_lines)
                task.triples_synced = total_synced
                await self.db.flush()

            # 完成
            task.status = "completed"
            task.progress = 1.0
            task.completed_at = datetime.now(timezone.utc)

            # 标记版本已同步
            if version.status == VersionStatus.PUBLISHED.value:
                version.status = VersionStatus.SYNCED.value
                version.synced_at = datetime.now(timezone.utc)

            await self.db.flush()
            logger.info(f"同步任务完成: {task_id}")

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)[:500]
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
