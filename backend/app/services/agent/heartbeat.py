"""心跳检测服务 — 检测 DEGRADED/OFFLINE 状态，触发告警。

超时判定：
- 90 秒未收到 heartbeat → DEGRADED
- 再过 15 秒宽限期（共 105 秒）→ OFFLINE，清理路由表
- OFFLINE 超 5 分钟 → 发送告警通知
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import redis.asyncio as aioredis

from backend.app.services.agent.router import AgentStatus

if TYPE_CHECKING:
    from backend.app.services.agent.router import AgentConn, AgentRouter

logger = logging.getLogger(__name__)

# 心跳超时阈值
HEARTBEAT_TIMEOUT_SEC = 90       # 超过此时间标记 DEGRADED
GRACE_PERIOD_SEC = 15            # 宽限期，超过后标记 OFFLINE
OFFLINE_ALERT_SEC = 300          # OFFLINE 超过 5 分钟触发告警


class HeartbeatService:
    """心跳检测服务 — 扫描所有连接，检测超时并更新状态。"""

    def __init__(self, router: AgentRouter, redis_client: aioredis.Redis | None = None):
        self._router = router
        self._redis = redis_client

    def check_connections(self) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        """扫描所有连接，检测超时。

        Returns:
            (degraded_keys, offline_keys) — 两个列表，元素为 (org_id, datasource) 元组。
        """
        now = datetime.now(timezone.utc)
        degraded_keys: list[tuple[str, str]] = []
        offline_keys: list[tuple[str, str]] = []

        for conn in self._router.get_all_connections():
            elapsed = (now - conn.last_seen).total_seconds()

            if elapsed >= HEARTBEAT_TIMEOUT_SEC + GRACE_PERIOD_SEC:
                # 超过 105 秒 → OFFLINE
                offline_keys.append((conn.org_id, conn.datasource))
            elif elapsed >= HEARTBEAT_TIMEOUT_SEC:
                # 超过 90 秒 → DEGRADED
                degraded_keys.append((conn.org_id, conn.datasource))

        # 更新 DEGRADED 状态
        for org_id, datasource in degraded_keys:
            self._router.update_status(org_id, datasource, AgentStatus.DEGRADED)
            logger.warning("代理 DEGRADED: org=%s ds=%s", org_id, datasource)

        # 处理 OFFLINE 连接
        for org_id, datasource in offline_keys:
            self._handle_offline(org_id, datasource)

        return degraded_keys, offline_keys

    def _handle_offline(self, org_id: str, datasource: str) -> None:
        """处理 OFFLINE 连接：关闭 ws、清理路由表、记录 Redis。"""
        conn = self._router.get_connection(org_id, datasource)
        if conn is None:
            return

        # 关闭 WebSocket
        try:
            import asyncio
            asyncio.create_task(self._safe_close_ws(conn))
        except Exception as e:
            logger.warning("关闭 ws 失败: %s", e)

        # 记录 OFFLINE 时间到 Redis
        if self._redis:
            import asyncio
            asyncio.create_task(self._record_offline(org_id, datasource))

        # 清理路由表
        self._router.remove_connection(org_id, datasource)
        logger.warning("代理 OFFLINE: org=%s ds=%s，路由表已清理", org_id, datasource)

    async def _safe_close_ws(self, conn: AgentConn) -> None:
        """安全关闭 WebSocket 连接。"""
        try:
            await conn.ws.close()
        except Exception:
            pass

    async def _record_offline(self, org_id: str, datasource: str) -> None:
        """记录 OFFLINE 状态到 Redis。"""
        try:
            key = f"agent:offline:{org_id}:{datasource}"
            now = datetime.now(timezone.utc).isoformat()
            await self._redis.set(key, now, ex=OFFLINE_ALERT_SEC * 2)
        except Exception as e:
            logger.warning("Redis 记录 OFFLINE 失败: %s", e)

    async def check_offline_alerts(self) -> list[dict]:
        """扫描 Redis 中 OFFLINE 超 5 分钟的代理，返回需告警列表。

        使用 Redis SCAN 扫描 agent:offline:* 键。
        """
        if not self._redis:
            return []

        alerts = []
        now = datetime.now(timezone.utc)

        try:
            async for key in self._redis.scan_iter(match="agent:offline:*"):
                key_str = key if isinstance(key, str) else key.decode()
                parts = key_str.split(":")
                if len(parts) < 4:
                    continue
                org_id = parts[2]
                datasource = parts[3]

                offline_time_str = await self._redis.get(key)
                if offline_time_str is None:
                    continue
                if isinstance(offline_time_str, bytes):
                    offline_time_str = offline_time_str.decode()

                try:
                    offline_time = datetime.fromisoformat(offline_time_str)
                    if offline_time.tzinfo is None:
                        offline_time = offline_time.replace(tzinfo=timezone.utc)

                    elapsed = (now - offline_time).total_seconds()
                    if elapsed >= OFFLINE_ALERT_SEC:
                        alerts.append({
                            "org_id": org_id,
                            "datasource": datasource,
                            "offline_since": offline_time_str,
                            "offline_seconds": int(elapsed),
                        })
                except (ValueError, TypeError):
                    continue

        except Exception as e:
            logger.warning("Redis 扫描 OFFLINE 告警失败: %s", e)

        return alerts


# 全局单例
_heartbeat_service: HeartbeatService | None = None


def init_heartbeat_service(router: AgentRouter, redis_client: aioredis.Redis | None = None) -> HeartbeatService:
    """初始化全局心跳服务。"""
    global _heartbeat_service
    _heartbeat_service = HeartbeatService(router=router, redis_client=redis_client)
    return _heartbeat_service


def get_heartbeat_service() -> HeartbeatService:
    """获取全局心跳服务实例。"""
    global _heartbeat_service
    if _heartbeat_service is None:
        raise RuntimeError("HeartbeatService 未初始化，请先调用 init_heartbeat_service()")
    return _heartbeat_service
