"""编译缓存服务单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.app.services.compile_cache import CompileCache


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=0)
    return redis


@pytest.fixture
def cache(mock_redis):
    return CompileCache(redis_client=mock_redis)


class TestCompileCache:
    @pytest.mark.asyncio
    async def test_get_compiled_rules_cache_miss(self, cache, mock_redis):
        mock_redis.get.return_value = None
        result = await cache.get_compiled_rules("tenant_001")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_compiled_rules(self, cache, mock_redis):
        rules = {"version": "v1.0.0", "rules": []}
        await cache.set_compiled_rules("tenant_001", rules, ttl=3600)
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_compile_status(self, cache, mock_redis):
        mock_redis.get.return_value = b'"ready"'
        status = await cache.get_compile_status("tenant_001")
        assert status == "ready"

    @pytest.mark.asyncio
    async def test_set_compile_status_with_ttl(self, cache, mock_redis):
        await cache.set_compile_status("tenant_001", "L0_HIGH_COMPILING", ttl=300)
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_stale(self, cache, mock_redis):
        await cache.mark_stale("tenant_001", reason="L0_UPDATED", max_staleness=3600)
        mock_redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_get_staleness_seconds_no_stale(self, cache, mock_redis):
        mock_redis.get.return_value = None
        seconds = await cache.get_staleness_seconds("tenant_001")
        assert seconds == 0

    @pytest.mark.asyncio
    async def test_get_staleness_seconds_with_stale(self, cache, mock_redis):
        import time
        past_time = int(time.time()) - 1800
        mock_redis.get.return_value = str(past_time).encode()
        seconds = await cache.get_staleness_seconds("tenant_001")
        assert seconds == 1800
