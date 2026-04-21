"""增量编译器 - 仅重编译变更部分"""
from typing import Any, Dict, List, Optional

from loguru import logger

from backend.app.services.compile_cache import CompileCache


class IncrementalCompiler:
    """增量编译器

    策略：仅当规则变更时触发重编译，复用已有编译结果。
    """

    # 需要重编译的状态
    RECOMPILE_STATES = {"STALE", "L0_UPDATED", "L1_UPDATED"}

    def __init__(self, cache: CompileCache, compiler):
        self.cache = cache
        self.compiler = compiler

    async def needs_recompile(self, tenant_id: str) -> bool:
        """检查是否需要重编译"""
        status = await self.cache.get_compile_status(tenant_id)
        if status is None:
            return True
        return status in self.RECOMPILE_STATES

    async def compile_incremental(
        self, tenant_id: str, changed_rules: List[Dict[str, Any]]
    ) -> Any:
        """增量编译：合并变更规则后重新编译"""
        current = await self.cache.get_compiled_rules(tenant_id)
        existing_rules = []
        if current:
            existing_rules = current.get("rules", [])

        # 合并：变更规则覆盖同 intent_id 的旧规则
        merged = self._merge_with_changes(existing_rules, changed_rules)

        # 调用编译器同步编译
        result = self.compiler.compile_sync(tenant_id, l2_rules=merged)

        if result.success:
            import json
            config_data = {
                "version": result.config.version,
                "rules": result.config.rules,
                "rule_count": result.config.rule_count,
                "compile_time_ms": result.config.compile_time_ms,
            }
            await self.cache.set_compiled_rules(tenant_id, config_data)

        return result

    async def get_current_rules(self, tenant_id: str) -> List[Dict]:
        """获取当前编译后的规则列表"""
        data = await self.cache.get_compiled_rules(tenant_id)
        if data is None:
            return []
        return data.get("rules", [])

    def _merge_with_changes(
        self,
        existing: List[Dict],
        changes: List[Dict],
    ) -> List[Dict]:
        """合并现有规则与变更规则"""
        # 构建变更的 intent_id 索引
        changed_intents = {r.get("intent_id") for r in changes if r.get("intent_id")}

        # 过滤掉被覆盖的旧规则
        kept = [
            r for r in existing
            if r.get("intent_id") not in changed_intents
        ]

        # 加入变更规则
        kept.extend(changes)
        return kept
