"""编译调度器 - 优先级队列+异步执行"""
import heapq
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger


@dataclass(order=True)
class CompileJob:
    """编译任务"""
    priority: int = field(compare=True)
    tenant_id: str = field(compare=False)
    status: str = field(default="pending", compare=False)
    l2_rules: List[Dict[str, Any]] = field(default_factory=list, compare=False)

    def __init__(self, tenant_id: str, priority: int = 5, l2_rules: Optional[List[Dict]] = None):
        self.tenant_id = tenant_id
        self.priority = priority
        self.status = "pending"
        self.l2_rules = l2_rules or []


class CompileScheduler:
    """编译调度器

    使用内存优先级队列调度编译任务。
    生产环境可替换为 Celery 等分布式队列。
    """

    def __init__(self, cache, compiler):
        self.cache = cache
        self.compiler = compiler
        self._queue: List[CompileJob] = []

    def create_job(self, tenant_id: str, priority: int = 5, l2_rules: Optional[List[Dict]] = None) -> CompileJob:
        """创建编译任务"""
        return CompileJob(tenant_id=tenant_id, priority=priority, l2_rules=l2_rules)

    def enqueue(self, job: CompileJob) -> None:
        """入队（使用负优先级实现最大堆）"""
        job.priority = -job.priority  # heapq 是最小堆，取反实现最大堆
        heapq.heappush(self._queue, job)

    def dequeue(self) -> Optional[CompileJob]:
        """出队最高优先级任务"""
        if not self._queue:
            return None
        job = heapq.heappop(self._queue)
        job.priority = -job.priority  # 恢复正数
        return job

    async def submit(self, job: CompileJob) -> Any:
        """提交并执行编译任务"""
        job.status = "running"
        await self.cache.set_compile_status(job.tenant_id, "compiling")

        try:
            result = self.compiler.compile_sync(
                job.tenant_id, l2_rules=job.l2_rules
            )
            if result.success:
                job.status = "completed"
                await self.cache.set_compile_status(job.tenant_id, "ready")
            else:
                job.status = "failed"
                await self.cache.set_compile_status(job.tenant_id, "failed")
            return result
        except Exception as e:
            job.status = "failed"
            logger.error(f"Compile job failed for {job.tenant_id}: {e}")
            from backend.app.services.rules.compiler import CompileResult
            return CompileResult(success=False, errors=[str(e)])
