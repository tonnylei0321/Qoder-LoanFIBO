"""路由表服务 — 内存 dict + Redis 备份，管理 (org_id, datasource) → WebSocket 连接映射。

设计要点：
- 内存为运行时权威源（读写最快）
- Redis 做持久备份（进程重启后可恢复路由元数据）
- 新连接覆盖同 datasource 旧连接（旧 ws.close）
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """代理连接状态。"""
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"


@dataclass
class AgentConn:
    """一条代理连接的元数据。"""
    ws: Any  # WebSocket 对象（不序列化到 Redis）
    org_id: str
    datasource: str
    version: str = ""
    ip: str = ""
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: AgentStatus = AgentStatus.ONLINE
    # 连接统计
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_tasks: int = 0
    success_tasks: int = 0
    fail_tasks: int = 0

    def to_redis_dict(self) -> dict:
        """序列化为 Redis Hash 字段（不含 ws 对象）。"""
        return {
            "org_id": self.org_id,
            "datasource": self.datasource,
            "version": self.version,
            "ip": self.ip,
            "last_seen": self.last_seen.isoformat(),
            "status": self.status.value,
            "connected_at": self.connected_at.isoformat(),
            "total_tasks": str(self.total_tasks),
            "success_tasks": str(self.success_tasks),
            "fail_tasks": str(self.fail_tasks),
        }

    @classmethod
    def from_redis_dict(cls, data: dict) -> dict:
        """从 Redis Hash 反序列化（仅返回元数据，无 ws 对象）。"""
        return {
            "org_id": data["org_id"],
            "datasource": data["datasource"],
            "version": data.get("version", ""),
            "ip": data.get("ip", ""),
            "last_seen": data.get("last_seen", ""),
            "status": data.get("status", AgentStatus.OFFLINE.value),
            "connected_at": data.get("connected_at", ""),
            "total_tasks": int(data.get("total_tasks", 0)),
            "success_tasks": int(data.get("success_tasks", 0)),
            "fail_tasks": int(data.get("fail_tasks", 0)),
        }


class AgentRouter:
    """代理路由表 — 管理所有活跃的代理 WebSocket 连接。

    线程安全说明：在单线程 asyncio 事件循环中运行，无需加锁。
    """

    def __init__(self, redis_client: aioredis.Redis | None = None):
        self._routes: dict[tuple[str, str], AgentConn] = {}
        self._redis = redis_client

    def add_connection(self, conn: AgentConn) -> AgentConn | None:
        """添加连接。若同 (org_id, datasource) 已有旧连接，覆盖并返回旧连接。

        Returns:
            旧连接对象（调用方应负责 close），或 None 表示无旧连接。
        """
        key = (conn.org_id, conn.datasource)
        old_conn = self._routes.get(key)

        self._routes[key] = conn

        if old_conn is not None:
            logger.info(
                "路由表覆盖: org=%s ds=%s 旧版本=%s 新版本=%s",
                conn.org_id, conn.datasource,
                old_conn.version, conn.version,
            )

        # 异步同步到 Redis（不阻塞）
        if self._redis:
            import asyncio
            asyncio.create_task(self._sync_to_redis(conn))

        return old_conn

    def remove_connection(self, org_id: str, datasource: str) -> AgentConn | None:
        """移除连接，返回被移除的连接（或 None）。"""
        key = (org_id, datasource)
        conn = self._routes.pop(key, None)

        if conn is not None and self._redis:
            import asyncio
            asyncio.create_task(self._remove_from_redis(org_id, datasource))

        return conn

    def get_connection(self, org_id: str, datasource: str) -> AgentConn | None:
        """获取指定连接。"""
        return self._routes.get((org_id, datasource))

    def get_all_for_org(self, org_id: str) -> list[AgentConn]:
        """获取某企业下所有连接。"""
        return [c for c in self._routes.values() if c.org_id == org_id]

    def get_all_connections(self) -> list[AgentConn]:
        """获取所有连接。"""
        return list(self._routes.values())

    def update_last_seen(self, org_id: str, datasource: str) -> None:
        """更新连接的最后心跳时间。"""
        key = (org_id, datasource)
        conn = self._routes.get(key)
        if conn is not None:
            conn.last_seen = datetime.now(timezone.utc)
            conn.status = AgentStatus.ONLINE

    def update_status(self, org_id: str, datasource: str, status: AgentStatus) -> None:
        """更新连接状态。"""
        key = (org_id, datasource)
        conn = self._routes.get(key)
        if conn is not None:
            conn.status = status

    async def _sync_to_redis(self, conn: AgentConn) -> None:
        """将连接元数据同步到 Redis Hash。"""
        if not self._redis:
            return
        try:
            redis_key = f"agent:route:{conn.org_id}"
            await self._redis.hset(
                redis_key,
                conn.datasource,
                json.dumps(conn.to_redis_dict()),
            )
        except Exception as e:
            logger.warning("Redis 路由同步失败: %s", e)

    async def _remove_from_redis(self, org_id: str, datasource: str) -> None:
        """从 Redis 删除连接元数据。"""
        if not self._redis:
            return
        try:
            redis_key = f"agent:route:{org_id}"
            await self._redis.hdel(redis_key, datasource)
        except Exception as e:
            logger.warning("Redis 路由删除失败: %s", e)

    async def get_status_from_redis(self, org_id: str) -> list[dict]:
        """从 Redis 读取某企业的所有代理状态（用于无活跃连接时的回退查询）。"""
        if not self._redis:
            return []
        try:
            redis_key = f"agent:route:{org_id}"
            raw = await self._redis.hgetall(redis_key)
            results = []
            for ds, data in raw.items():
                if isinstance(data, bytes):
                    data = data.decode()
                if isinstance(ds, bytes):
                    ds = ds.decode()
                entry = json.loads(data)
                entry["datasource"] = ds
                results.append(entry)
            return results
        except Exception as e:
            logger.warning("Redis 路由查询失败: %s", e)
            return []


# 全局单例（在 lifespan 中初始化时注入 redis_client）
_agent_router: AgentRouter | None = None


def init_router(redis_client: aioredis.Redis | None = None) -> AgentRouter:
    """初始化全局路由表。"""
    global _agent_router
    _agent_router = AgentRouter(redis_client=redis_client)
    return _agent_router


def get_router() -> AgentRouter:
    """获取全局路由表实例。"""
    global _agent_router
    if _agent_router is None:
        _agent_router = AgentRouter()
    return _agent_router
