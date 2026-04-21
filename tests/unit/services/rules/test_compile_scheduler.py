"""编译调度器单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.app.services.rules.compile_scheduler import CompileScheduler, CompileJob


class TestCompileScheduler:
    @pytest.fixture
    def mock_cache(self):
        cache = MagicMock()
        cache.get_compile_status = AsyncMock(return_value="ready")
        cache.set_compile_status = AsyncMock(return_value=True)
        return cache

    @pytest.fixture
    def mock_compiler(self):
        compiler = MagicMock()
        result = MagicMock()
        result.success = True
        result.config = MagicMock(
            version="v1.0.0", tenant_id="t1",
            rules=[], rule_count=0, compile_time_ms=100,
        )
        compiler.compile_sync = MagicMock(return_value=result)
        return compiler

    @pytest.fixture
    def scheduler(self, mock_cache, mock_compiler):
        return CompileScheduler(cache=mock_cache, compiler=mock_compiler)

    def test_create_compile_job(self, scheduler):
        job = scheduler.create_job("tenant_001", priority=5)
        assert job.tenant_id == "tenant_001"
        assert job.priority == 5
        assert job.status == "pending"

    def test_job_ordering_by_priority(self, scheduler):
        j1 = scheduler.create_job("t1", priority=1)
        j2 = scheduler.create_job("t2", priority=10)
        j3 = scheduler.create_job("t3", priority=5)
        scheduler.enqueue(j1)
        scheduler.enqueue(j2)
        scheduler.enqueue(j3)
        next_job = scheduler.dequeue()
        assert next_job.tenant_id == "t2"  # highest priority first

    def test_empty_queue(self, scheduler):
        assert scheduler.dequeue() is None

    @pytest.mark.asyncio
    async def test_submit_and_execute(self, scheduler):
        job = scheduler.create_job("tenant_001", priority=5)
        result = await scheduler.submit(job)
        assert result.success is True


class TestCompileJob:
    def test_job_creation(self):
        job = CompileJob(tenant_id="t1", priority=5)
        assert job.tenant_id == "t1"
        assert job.status == "pending"

    def test_job_status_transitions(self):
        job = CompileJob(tenant_id="t1", priority=1)
        assert job.status == "pending"
        job.status = "running"
        assert job.status == "running"
        job.status = "completed"
        assert job.status == "completed"
