"""增量编译器单元测试"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from backend.app.services.rules.incremental_compiler import IncrementalCompiler
from backend.app.services.compile_cache import CompileCache


@pytest.fixture
def mock_cache():
    cache = MagicMock(spec=CompileCache)
    cache.get_compiled_rules = AsyncMock(return_value={
        "version": "v1.0.0",
        "rules": [
            {"id": "r1", "intent_id": "q1", "table": "t1", "columns": ["c1"], "priority": 10},
            {"id": "r2", "intent_id": "q2", "table": "t2", "columns": ["c2"], "priority": 5},
        ]
    })
    cache.set_compiled_rules = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def mock_compiler():
    compiler = MagicMock()
    compiler.compile_sync = MagicMock(return_value=MagicMock(
        success=True, config=MagicMock(
            version="v2.0.0", tenant_id="t1",
            rules=[{"id": "r1_new", "intent_id": "q1", "priority": 15}],
            rule_count=1, compile_time_ms=50,
        )
    ))
    return compiler


@pytest.fixture
def inc_compiler(mock_cache, mock_compiler):
    return IncrementalCompiler(cache=mock_cache, compiler=mock_compiler)


class TestIncrementalCompiler:
    @pytest.mark.asyncio
    async def test_needs_recompile_when_stale(self, inc_compiler, mock_cache):
        mock_cache.get_compile_status = AsyncMock(return_value="STALE")
        result = await inc_compiler.needs_recompile("tenant_001")
        assert result is True

    @pytest.mark.asyncio
    async def test_no_recompile_when_ready(self, inc_compiler, mock_cache):
        mock_cache.get_compile_status = AsyncMock(return_value="ready")
        result = await inc_compiler.needs_recompile("tenant_001")
        assert result is False

    @pytest.mark.asyncio
    async def test_incremental_compile(self, inc_compiler):
        changed_rules = [
            {"id": "r1_new", "intent_id": "q1", "table": "t1", "columns": ["c1"], "priority": 15}
        ]
        result = await inc_compiler.compile_incremental("tenant_001", changed_rules)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_get_current_rules(self, inc_compiler, mock_cache):
        rules = await inc_compiler.get_current_rules("tenant_001")
        assert len(rules) == 2
        assert rules[0]["id"] == "r1"
