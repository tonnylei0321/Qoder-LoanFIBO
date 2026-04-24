"""定时编译调度 - 基于 APScheduler 的定时规则编译"""
from typing import Optional

from loguru import logger

from backend.app.services.compile_cache import CompileCache
from backend.app.services.rules.compiler import RuleCompiler
from backend.app.services.rules.conflict_resolver import ConflictResolver
from backend.app.services.rules.dsl_parser import DSLParser
from backend.app.services.rules.dsl_executor import DSLExecutor
from backend.app.services.graphdb_client import GraphDBClient
from backend.app.config import settings


# 全局 scheduler 实例
_scheduler: Optional[object] = None


class ScheduledCompileJob:
    """定时编译任务 - 扫描所有租户的 STALE 状态并重编译"""

    def __init__(self):
        self.compiler: Optional[RuleCompiler] = None

    def _ensure_compiler(self):
        """惰性初始化编译器"""
        if self.compiler is not None:
            return
        graphdb_client = GraphDBClient(
            endpoint=settings.GRAPHDB_ENDPOINT,
            repo=settings.GRAPHDB_REPO,
        )
        cache = CompileCache(redis_client=None)  # type: ignore
        conflict_resolver = ConflictResolver()
        dsl_parser = DSLParser()
        dsl_executor = DSLExecutor()
        self.compiler = RuleCompiler(
            graphdb_client=graphdb_client,
            cache=cache,
            conflict_resolver=conflict_resolver,
            dsl_parser=dsl_parser,
            dsl_executor=dsl_executor,
        )

    async def run(self):
        """执行定时编译扫描"""
        logger.info("ScheduledCompileJob: starting compile sweep")
        try:
            self._ensure_compiler()
            # 在实际实现中，应从数据库加载所有租户
            # 目前仅记录日志，编译器在真实 Redis + GraphDB 环境下运行
            logger.info("ScheduledCompileJob: compile sweep completed (no-op without Redis)")
        except Exception as e:
            logger.error(f"ScheduledCompileJob error: {e}")


def start_scheduler():
    """启动 APScheduler"""
    global _scheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("APScheduler not installed, scheduled compile disabled")
        return

    if _scheduler is not None:
        return

    job = ScheduledCompileJob()
    _scheduler = AsyncIOScheduler()
    # 每小时执行一次编译扫描（可配置）
    _scheduler.add_job(
        job.run,
        CronTrigger(hour="*", minute="5"),  # 每小时第5分钟
        id="scheduled_compile",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("APScheduler started: scheduled compile every hour at :05")


def stop_scheduler():
    """停止 APScheduler"""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("APScheduler stopped")
