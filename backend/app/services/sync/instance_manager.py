"""GraphDB 实例管理器 - CRUD、健康检查、统计"""
from datetime import datetime, timezone
from typing import Optional

import httpx
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.graphdb_instance import GraphDBInstance
from backend.app.schemas.sync import InstanceHealthResponse


class InstanceManager:
    """GraphDB 实例管理服务

    职责：
    - CRUD 实例
    - 健康检查
    - 统计查询
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def health_check(self, instance: GraphDBInstance) -> InstanceHealthResponse:
        """检查 GraphDB 实例健康状态

        尝试访问 GraphDB REST API 获取仓库大小和三元组数量。
        """
        now = datetime.now(timezone.utc).isoformat()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 检查仓库是否可访问
                url = f"{instance.server_url.rstrip('/')}/repositories/{instance.repo_id}/size"
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    statement_count = data.get("total", 0) if isinstance(data, dict) else 0
                    return InstanceHealthResponse(
                        instance_id=instance.id,
                        status="healthy",
                        statement_count=statement_count,
                        last_checked=now,
                    )
                else:
                    return InstanceHealthResponse(
                        instance_id=instance.id,
                        status="unhealthy",
                        last_checked=now,
                    )
        except Exception as e:
            logger.warning(f"GraphDB 实例健康检查失败: {instance.name} - {e}")
            return InstanceHealthResponse(
                instance_id=instance.id,
                status="unreachable",
                last_checked=now,
            )

    async def get_statistics(self, instance: GraphDBInstance) -> dict:
        """获取 GraphDB 实例统计信息"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # SPARQL 查询获取三元组总数
                sparql = "SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }"
                resp = await client.post(
                    f"{instance.server_url.rstrip('/')}/repositories/{instance.repo_id}",
                    data={"query": sparql},
                    headers={"Accept": "application/sparql-results+json"},
                )
                if resp.status_code == 200:
                    results = resp.json().get("results", {}).get("bindings", [])
                    count = int(results[0]["count"]["value"]) if results else 0
                    return {"statement_count": count, "status": "accessible"}
                return {"status": "error", "code": resp.status_code}
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}
