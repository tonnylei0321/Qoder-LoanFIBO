"""全链追踪服务 — 从前端点击到 ERP Agent SQL 执行的端到端追踪。

存储策略：
- 实时写入 Redis Stream（消费者组确认，防崩溃丢失）
- 定时刷盘到 PostgreSQL（10 秒一批）
- SQL 脱敏：保留表名/列名，替换 WHERE 条件中的值为 '***'
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# Redis Stream 名称
TRACE_STREAM = "agent:trace:stream"


class TracerService:
    """全链追踪服务。"""

    def __init__(self, redis_client: aioredis.Redis | None = None):
        self._redis = redis_client

    def create_trace(
        self, org_id: str, datasource: str, action: str, detail: dict | None = None
    ) -> dict:
        """创建一条新的 Trace 记录。

        Returns:
            trace dict，包含 trace_id、首 span 等。
        """
        trace_id = f"tr_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc)

        trace = {
            "trace_id": trace_id,
            "org_id": org_id,
            "datasource": datasource,
            "action": action,
            "status": "PENDING",
            "spans": [
                {
                    "node": "saas_gateway",
                    "event": "trace_created",
                    "ts": now.isoformat(),
                    "detail": detail or {},
                }
            ],
            "duration_ms": 0,
            "created_at": now.isoformat(),
        }
        return trace

    def add_span(
        self,
        trace: dict,
        node: str,
        event: str,
        detail: dict | None = None,
    ) -> dict:
        """向 Trace 追加一个 Span。"""
        span = {
            "node": node,
            "event": event,
            "ts": datetime.now(timezone.utc).isoformat(),
            "detail": detail or {},
        }
        trace["spans"].append(span)
        return trace

    def update_status(self, trace: dict, status: str) -> dict:
        """更新 Trace 状态，计算耗时。"""
        trace["status"] = status

        # 计算总耗时
        created_at = datetime.fromisoformat(trace["created_at"])
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        trace["duration_ms"] = int((now - created_at).total_seconds() * 1000)

        return trace

    @staticmethod
    def desensitize_sql(sql: str) -> str:
        """SQL 脱敏：替换单引号内的值为 '***'，保留表名/列名。

        Examples:
            >>> TracerService.desensitize_sql("SELECT name FROM users WHERE id = '12345'")
            "SELECT name FROM users WHERE id = '***'"
        """
        # 替换单引号字符串值为 '***'
        result = re.sub(r"'[^']*'", "'***'", sql)
        return result

    async def save_to_redis(self, trace: dict) -> None:
        """将 Trace 写入 Redis Stream。"""
        if not self._redis:
            return

        try:
            import json

            # 将 spans 序列化为 JSON 字符串（Redis Stream 不支持嵌套）
            trace_flat = {
                "trace_id": trace["trace_id"],
                "org_id": trace["org_id"],
                "datasource": trace["datasource"],
                "action": trace["action"],
                "status": trace["status"],
                "spans": json.dumps(trace["spans"]),
                "duration_ms": str(trace["duration_ms"]),
                "created_at": trace["created_at"],
            }
            await self._redis.xadd(TRACE_STREAM, trace_flat)
        except Exception as e:
            logger.warning("Trace 写入 Redis Stream 失败: %s", e)

    async def flush_to_pg(self, db_session) -> int:
        """从 Redis Stream 消费 Trace 并批量写入 PG。

        Returns:
            写入的记录数。
        """
        if not self._redis:
            return 0

        try:
            import json
            from sqlalchemy import text

            # 读取 Stream 中未消费的消息
            messages = await self._redis.xread(
                {TRACE_STREAM: "0-0"}, count=50, block=0
            )

            if not messages:
                return 0

            count = 0
            for stream, msgs in messages:
                for msg_id, data in msgs:
                    try:
                        spans = json.loads(data.get("spans", "[]"))
                        await db_session.execute(
                            text("""
                                INSERT INTO agent_trace
                                (trace_id, org_id, datasource, action, status, spans, duration_ms, created_at)
                                VALUES (:trace_id, :org_id::uuid, :datasource, :action, :status,
                                        :spans::jsonb, :duration_ms, :created_at::timestamptz)
                                ON CONFLICT (trace_id) DO NOTHING
                            """),
                            {
                                "trace_id": data["trace_id"],
                                "org_id": data["org_id"],
                                "datasource": data["datasource"],
                                "action": data["action"],
                                "status": data["status"],
                                "spans": json.dumps(spans),
                                "duration_ms": int(data.get("duration_ms", 0)),
                                "created_at": data["created_at"],
                            },
                        )
                        count += 1
                    except Exception as e:
                        logger.warning("Trace 写入 PG 失败 (msg_id=%s): %s", msg_id, e)

                    # 确认消费
                    await self._redis.xack(TRACE_STREAM, "pg-flusher", msg_id)

            if count > 0:
                await db_session.commit()

            return count

        except Exception as e:
            logger.warning("Trace flush_to_pg 异常: %s", e)
            return 0


# 全局单例
_tracer_service: TracerService | None = None


def init_tracer(redis_client: aioredis.Redis | None = None) -> TracerService:
    """初始化全局追踪服务。"""
    global _tracer_service
    _tracer_service = TracerService(redis_client=redis_client)
    return _tracer_service


def get_tracer() -> TracerService:
    """获取全局追踪服务实例。"""
    global _tracer_service
    if _tracer_service is None:
        _tracer_service = TracerService()
    return _tracer_service
