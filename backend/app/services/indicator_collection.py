"""定时指标采集管道 — 通过 Agent TaskQueue 向 ERP Agent 下发指标采集任务。

工作流程：
1. APScheduler 每 20 分钟触发一次采集
2. 扫描路由表中所有在线的代理连接
3. 对每个连接下发 query_indicator 任务
4. 收到 result 后调用 IndicatorHistoryWriter 双写
5. 失败/超时记录采集日志
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from loguru import logger

from backend.app.services.agent.router import AgentRouter, get_router, AgentStatus
from backend.app.services.agent.task_queue import TaskQueue, get_task_queue, TaskStatus


# 全局采集调度器实例
_collection_scheduler = None


class IndicatorCollectionPipeline:
    """指标采集管道 — 定时向 ERP Agent 采集指标数据。"""

    def __init__(
        self,
        router: AgentRouter | None = None,
        task_queue: TaskQueue | None = None,
    ):
        self._router = router or get_router()
        self._task_queue = task_queue or get_task_queue()

    async def collect_all(self) -> dict:
        """对所有在线代理发起指标采集。

        Returns:
            {"dispatched": int, "offline": int, "errors": list}
        """
        connections = self._router.get_all_connections()
        dispatched = 0
        offline = 0
        errors = []

        for conn in connections:
            if conn.status != AgentStatus.ONLINE:
                offline += 1
                continue

            try:
                result = await self._task_queue.submit(
                    org_id=conn.org_id,
                    datasource=conn.datasource,
                    action="query_indicator",
                    payload={
                        "task": "query_indicator",
                        "params": {
                            "calc_date": str(date.today()),
                        },
                    },
                    timeout_ms=60000,  # 指标采集给 60 秒
                )

                status = result.get("status")
                if status == TaskStatus.DISPATCHED.value:
                    dispatched += 1
                    logger.info(
                        f"指标采集任务已派发: org={conn.org_id} ds={conn.datasource} msg_id={result.get('msg_id')}"
                    )
                elif status == TaskStatus.DATASOURCE_OFFLINE.value:
                    offline += 1
                else:
                    errors.append({
                        "org_id": conn.org_id,
                        "datasource": conn.datasource,
                        "status": status,
                        "detail": result.get("detail", ""),
                    })

            except Exception as e:
                logger.error(f"指标采集异常: org={conn.org_id} ds={conn.datasource} err={e}")
                errors.append({
                    "org_id": conn.org_id,
                    "datasource": conn.datasource,
                    "error": str(e),
                })

        logger.info(
            f"指标采集完成: dispatched={dispatched} offline={offline} errors={len(errors)}"
        )
        return {
            "dispatched": dispatched,
            "offline": offline,
            "errors": errors,
        }

    async def collect_for_org(self, org_id: str, datasource: str) -> dict:
        """对指定企业发起指标采集。

        Returns:
            提交结果
        """
        conn = self._router.get_connection(org_id, datasource)
        if conn is None or conn.status != AgentStatus.ONLINE:
            return {
                "status": TaskStatus.DATASOURCE_OFFLINE.value,
                "detail": f"数据源 {datasource} 离线",
            }

        return await self._task_queue.submit(
            org_id=org_id,
            datasource=datasource,
            action="query_indicator",
            payload={
                "task": "query_indicator",
                "params": {
                    "calc_date": str(date.today()),
                },
            },
            timeout_ms=60000,
        )


def start_collection_scheduler():
    """启动指标采集定时调度（APScheduler）。"""
    global _collection_scheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        logger.warning("APScheduler not installed, indicator collection scheduler disabled")
        return

    if _collection_scheduler is not None:
        return

    pipeline = IndicatorCollectionPipeline()

    async def _collect_job():
        """定时采集任务。"""
        try:
            result = await pipeline.collect_all()
            logger.info(f"定时指标采集: {result}")
        except Exception as e:
            logger.error(f"定时指标采集异常: {e}")

    _collection_scheduler = AsyncIOScheduler()
    # 每 20 分钟采集一次
    _collection_scheduler.add_job(
        _collect_job,
        IntervalTrigger(minutes=20),
        id="indicator_collection",
        replace_existing=True,
    )
    _collection_scheduler.start()
    logger.info("Indicator collection scheduler started: every 20 minutes")


def stop_collection_scheduler():
    """停止指标采集定时调度。"""
    global _collection_scheduler
    if _collection_scheduler is not None:
        _collection_scheduler.shutdown(wait=False)
        _collection_scheduler = None
        logger.info("Indicator collection scheduler stopped")
