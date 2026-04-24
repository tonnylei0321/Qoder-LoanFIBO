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

        每条消息独立事务：成功则 commit，失败则 rollback 后继续下一条。
        避免 PG InFailedSQLTransactionError 导致整个批次死循环刷屏。

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
                        # Redis decode_responses=False 时 data 的 key/value 是 bytes
                        def _get(d, key):
                            val = d.get(key) or d.get(key.encode())
                            if isinstance(val, bytes):
                                val = val.decode()
                            return val
            
                        spans_raw = _get(data, "spans")
                        spans = json.loads(spans_raw) if spans_raw else []

                        # asyncpg 需要 datetime 对象，不能传 str
                        created_at_str = _get(data, "created_at")
                        created_at_dt = None
                        if created_at_str:
                            try:
                                from datetime import datetime as dt
                                created_at_dt = dt.fromisoformat(created_at_str)
                            except (ValueError, TypeError):
                                created_at_dt = datetime.now(timezone.utc)

                        await db_session.execute(
                            text("""
                                INSERT INTO agent_trace
                                (trace_id, org_id, datasource, action, status, spans, duration_ms, created_at)
                                VALUES (:trace_id, CAST(:org_id AS uuid), :datasource, :action, :status,
                                        CAST(:spans AS jsonb), :duration_ms, :created_at)
                                ON CONFLICT (trace_id) DO NOTHING
                            """),
                            {
                                "trace_id": _get(data, "trace_id"),
                                "org_id": _get(data, "org_id"),
                                "datasource": _get(data, "datasource"),
                                "action": _get(data, "action"),
                                "status": _get(data, "status"),
                                "spans": json.dumps(spans),
                                "duration_ms": int(_get(data, "duration_ms") or 0),
                                "created_at": created_at_dt,
                            },
                        )
                        # 逐条提交，避免后续失败导致整批回滚
                        await db_session.commit()
                        count += 1
                    except Exception as e:
                        # 回滚中止的事务，确保下一条 INSERT 能正常执行
                        await db_session.rollback()
                        logger.warning("Trace 写入 PG 失败 (msg_id=%s): %s", msg_id, e)

                    # 无论成功失败都确认消费，避免重复刷盘死循环
                    await self._redis.xack(TRACE_STREAM, "pg-flusher", msg_id)

            return count

        except Exception as e:
            # 外层异常也要回滚，防止事务中止状态残留
            try:
                await db_session.rollback()
            except Exception:
                pass
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
