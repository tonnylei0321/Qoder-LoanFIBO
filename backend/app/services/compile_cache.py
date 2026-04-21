"""编译缓存服务 - Redis存储编译后规则和状态"""
import json
import time
from typing import Any, Dict, Optional

from loguru import logger


class CompileCache:
    """编译缓存（Redis）"""

    KEY_PREFIX = "rules"
    STATUS_PREFIX = "compile_status"
    STALE_PREFIX = "stale"

    def __init__(self, redis_client):
        self.redis = redis_client

    def _rules_key(self, tenant_id: str) -> str:
        return f"{self.KEY_PREFIX}:{tenant_id}:latest"

    def _status_key(self, tenant_id: str) -> str:
        return f"{self.STATUS_PREFIX}:{tenant_id}"

    def _stale_key(self, tenant_id: str) -> str:
        return f"{self.STALE_PREFIX}:{tenant_id}"

    async def get_compiled_rules(self, tenant_id: str) -> Optional[Dict]:
        data = await self.redis.get(self._rules_key(tenant_id))
        if data is None:
            return None
        return json.loads(data)

    async def set_compiled_rules(
        self, tenant_id: str, rules: Dict, ttl: int = 86400
    ) -> bool:
        key = self._rules_key(tenant_id)
        await self.redis.setex(key, ttl, json.dumps(rules, default=str))
        return True

    async def get_compile_status(self, tenant_id: str) -> Optional[str]:
        data = await self.redis.get(self._status_key(tenant_id))
        if data is None:
            return None
        return json.loads(data)

    async def set_compile_status(
        self, tenant_id: str, status: str, ttl: Optional[int] = None
    ) -> bool:
        key = self._status_key(tenant_id)
        value = json.dumps(status)
        if ttl:
            await self.redis.setex(key, ttl, value)
        else:
            await self.redis.set(key, value)
        return True

    async def mark_stale(
        self, tenant_id: str, reason: str, max_staleness: int = 3600
    ) -> bool:
        key = self._stale_key(tenant_id)
        await self.redis.setex(key, max_staleness, str(int(time.time())))
        await self.set_compile_status(tenant_id, "STALE")
        return True

    async def get_staleness_seconds(self, tenant_id: str) -> int:
        data = await self.redis.get(self._stale_key(tenant_id))
        if data is None:
            return 0
        marked_time = int(data)
        return int(time.time()) - marked_time

    async def get_last_compile(self, tenant_id: str) -> Optional[Dict]:
        return await self.get_compiled_rules(tenant_id)

    async def delete(self, tenant_id: str) -> bool:
        keys = [
            self._rules_key(tenant_id),
            self._status_key(tenant_id),
            self._stale_key(tenant_id),
        ]
        for key in keys:
            await self.redis.delete(key)
        return True
