"""任务队列服务 — 任务分发、超时判定、结果匹配、SSE 推送。

状态机：
  PENDING → DISPATCHED → EXECUTING → COMPLETED
                                   → ERROR
                      → AGENT_UNREACHABLE（ack 超时 500ms）
                      → TASK_TIMEOUT（执行超时 timeout_ms + 5s）
         → DATASOURCE_OFFLINE（路由表无记录）
         → SERVICE_OVERLOAD（pending_tasks 超过 10000）
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from backend.app.services.agent.router import AgentRouter, get_router
from backend.app.services.agent.tracer import TracerService, get_tracer

logger = logging.getLogger(__name__)

# 任务队列容量上限
MAX_PENDING_TASKS = 10000

# 超时阈值
ACK_TIMEOUT_MS = 5000  # ack 超时（5秒，ERP代理执行SQL需要时间确认）
EXEC_TIMEOUT_BUFFER_MS = 5000  # 执行超时额外缓冲


class TaskStatus(str, Enum):
    """任务状态枚举。"""
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    AGENT_UNREACHABLE = "AGENT_UNREACHABLE"
    TASK_TIMEOUT = "TASK_TIMEOUT"
    DATASOURCE_OFFLINE = "DATASOURCE_OFFLINE"
    SERVICE_OVERLOAD = "SERVICE_OVERLOAD"


@dataclass
class PendingTask:
    """等待中的任务。"""
    msg_id: str
    org_id: str
    datasource: str
    action: str
    status: TaskStatus = TaskStatus.PENDING
    future: asyncio.Future = field(default=None)
    trace: dict = field(default=None)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    timeout_ms: int = 30000  # 默认 30 秒
    dispatched_at: datetime | None = None
    acked_at: datetime | None = None


class TaskQueue:
    """任务队列 — 管理任务生命周期。"""

    def __init__(
        self,
        router: AgentRouter | None = None,
        tracer: TracerService | None = None,
    ):
        self._router = router or get_router()
        self._tracer = tracer or get_tracer()
        self._pending_tasks: dict[str, PendingTask] = {}
        self._sse_clients: list[asyncio.Queue] = []

    @property
    def pending_count(self) -> int:
        """当前待处理任务数。"""
        return len(self._pending_tasks)

    async def submit(
        self,
        org_id: str,
        datasource: str,
        action: str,
        payload: dict,
        timeout_ms: int = 30000,
    ) -> dict:
        """提交任务。

        Returns:
            dict: {"status": TaskStatus, "msg_id": str, ...}
        """
        # 容量检查
        if len(self._pending_tasks) >= MAX_PENDING_TASKS:
            return {
                "status": TaskStatus.SERVICE_OVERLOAD.value,
                "msg_id": None,
                "detail": f"pending_tasks 达到上限 {MAX_PENDING_TASKS}",
            }

        # 路由表检查
        conn = self._router.get_connection(org_id, datasource)
        if conn is None:
            return {
                "status": TaskStatus.DATASOURCE_OFFLINE.value,
                "msg_id": None,
                "detail": f"数据源 {datasource} 离线",
            }

        # 创建任务
        msg_id = f"msg_{uuid.uuid4().hex[:16]}"
        trace = self._tracer.create_trace(org_id, datasource, action, {"msg_id": msg_id})

        task = PendingTask(
            msg_id=msg_id,
            org_id=org_id,
            datasource=datasource,
            action=action,
            trace=trace,
            timeout_ms=timeout_ms,
        )
        task.future = asyncio.get_event_loop().create_future()
        self._pending_tasks[msg_id] = task

        # 推送到代理（标准信封格式，不含 timeout_ms / datasource / max_rows）
        try:
            task_msg = {
                "msg_id": msg_id,
                "type": "task",
                "tenant_id": "default",
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                "payload": payload,
            }
            await conn.ws.send_json(task_msg)

            task.status = TaskStatus.DISPATCHED
            task.dispatched_at = datetime.now(timezone.utc)
            self._tracer.add_span(trace, "ws_server", "task_dispatched", {"msg_id": msg_id})
            await self._tracer.save_to_redis(trace)

            # 启动超时监控
            asyncio.create_task(self._monitor_timeout(task))

        except Exception as e:
            logger.error("任务推送失败: %s", e)
            task.status = TaskStatus.AGENT_UNREACHABLE
            self._tracer.update_status(trace, TaskStatus.AGENT_UNREACHABLE.value)
            self._tracer.add_span(trace, "ws_server", "push_failed", {"error": str(e)})
            self._tracer.save_to_redis(trace)

            if not task.future.done():
                task.future.set_result({
                    "status": TaskStatus.AGENT_UNREACHABLE.value,
                    "msg_id": msg_id,
                })

        return {
            "status": task.status.value,
            "msg_id": msg_id,
        }

    def handle_ack(self, msg_id: str) -> None:
        """处理 ack 消息。"""
        task = self._pending_tasks.get(msg_id)
        if task is None:
            logger.warning("收到未知 msg_id 的 ack: %s", msg_id)
            return

        task.status = TaskStatus.EXECUTING
        task.acked_at = datetime.now(timezone.utc)

        if task.trace:
            self._tracer.add_span(task.trace, "ws_server", "ack_received", {"msg_id": msg_id})

    async def handle_result(self, msg_id: str, data: dict) -> None:
        """处理 result 消息 — resolve Future + 通知 SSE。"""
        task = self._pending_tasks.get(msg_id)
        if task is None:
            logger.warning("收到未知 msg_id 的 result: %s", msg_id)
            return

        task.status = TaskStatus.COMPLETED

        if task.trace:
            self._tracer.add_span(
                task.trace, "ws_server", "result_received",
                {"msg_id": msg_id, "data_keys": list(data.keys())},
            )
            self._tracer.update_status(task.trace, TaskStatus.COMPLETED.value)
            await self._tracer.save_to_redis(task.trace)

        result = {
            "status": TaskStatus.COMPLETED.value,
            "msg_id": msg_id,
            "data": data,
        }

        if not task.future.done():
            task.future.set_result(result)

        # 通知 SSE 客户端
        await self._notify_sse(result)

        # 清理
        self._pending_tasks.pop(msg_id, None)

    async def handle_error(self, msg_id: str, error: str) -> None:
        """处理 error 消息。"""
        task = self._pending_tasks.get(msg_id)
        if task is None:
            logger.warning("收到未知 msg_id 的 error: %s", msg_id)
            return

        task.status = TaskStatus.ERROR

        if task.trace:
            self._tracer.add_span(
                task.trace, "ws_server", "error_received",
                {"msg_id": msg_id, "error": error},
            )
            self._tracer.update_status(task.trace, TaskStatus.ERROR.value)
            await self._tracer.save_to_redis(task.trace)

        result = {
            "status": TaskStatus.ERROR.value,
            "msg_id": msg_id,
            "error": error,
        }

        if not task.future.done():
            task.future.set_result(result)

        await self._notify_sse(result)
        self._pending_tasks.pop(msg_id, None)

    async def _monitor_timeout(self, task: PendingTask) -> None:
        """监控任务超时。"""
        # Phase 1: 等待 ack（500ms）
        if task.status == TaskStatus.DISPATCHED:
            await asyncio.sleep(ACK_TIMEOUT_MS / 1000)
            if task.status == TaskStatus.DISPATCHED:
                # ack 超时
                task.status = TaskStatus.AGENT_UNREACHABLE
                if task.trace:
                    self._tracer.update_status(task.trace, TaskStatus.AGENT_UNREACHABLE.value)
                    await self._tracer.save_to_redis(task.trace)
                if not task.future.done():
                    task.future.set_result({
                        "status": TaskStatus.AGENT_UNREACHABLE.value,
                        "msg_id": task.msg_id,
                    })
                await self._notify_sse({
                    "status": TaskStatus.AGENT_UNREACHABLE.value,
                    "msg_id": task.msg_id,
                })
                self._pending_tasks.pop(task.msg_id, None)
                return

        # Phase 2: 等待执行结果（timeout_ms + 5s）
        total_timeout = (task.timeout_ms + EXEC_TIMEOUT_BUFFER_MS) / 1000
        await asyncio.sleep(total_timeout)
        if task.status == TaskStatus.EXECUTING:
            # 执行超时
            task.status = TaskStatus.TASK_TIMEOUT
            if task.trace:
                self._tracer.update_status(task.trace, TaskStatus.TASK_TIMEOUT.value)
                await self._tracer.save_to_redis(task.trace)
            if not task.future.done():
                task.future.set_result({
                    "status": TaskStatus.TASK_TIMEOUT.value,
                    "msg_id": task.msg_id,
                })
            await self._notify_sse({
                "status": TaskStatus.TASK_TIMEOUT.value,
                "msg_id": task.msg_id,
            })
            self._pending_tasks.pop(task.msg_id, None)

    def register_sse_client(self) -> asyncio.Queue:
        """注册 SSE 客户端，返回消息队列。"""
        queue = asyncio.Queue()
        self._sse_clients.append(queue)
        return queue

    def unregister_sse_client(self, queue: asyncio.Queue) -> None:
        """注销 SSE 客户端。"""
        try:
            self._sse_clients.remove(queue)
        except ValueError:
            pass

    async def _notify_sse(self, data: dict) -> None:
        """向所有 SSE 客户端推送消息。"""
        dead_queues = []
        for q in self._sse_clients:
            try:
                q.put_nowait(data)
            except Exception:
                dead_queues.append(q)
        for q in dead_queues:
            self.unregister_sse_client(q)


# 全局单例
_task_queue: TaskQueue | None = None


def init_task_queue(router: AgentRouter | None = None, tracer: TracerService | None = None) -> TaskQueue:
    """初始化全局任务队列。"""
    global _task_queue
    _task_queue = TaskQueue(router=router, tracer=tracer)
    return _task_queue


def get_task_queue() -> TaskQueue:
    """获取全局任务队列实例。"""
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue()
    return _task_queue
