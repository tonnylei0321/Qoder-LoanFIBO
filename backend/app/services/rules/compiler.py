"""RuleCompiler核心编译器 - 统一入口"""
import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from backend.app.services.rules.conflict_resolver import ConflictResolver
from backend.app.services.rules.dsl_parser import DSLParser
from backend.app.services.rules.dsl_executor import DSLExecutor


@dataclass
class CompiledConfig:
    """编译后的配置"""
    version: str
    tenant_id: str
    rules: List[Dict[str, Any]] = field(default_factory=list)
    rule_count: int = 0
    compile_time_ms: int = 0
    compiled_at: str = ""


@dataclass
class CompileResult:
    """编译结果"""
    success: bool
    config: Optional[CompiledConfig] = None
    errors: List[str] = field(default_factory=list)


class RuleCompiler:
    """规则编译器 - 统一入口

    架构说明：
    - 核心逻辑为同步实现（CPU密集型，适合多进程）
    - 提供异步包装器供FastAPI调用
    - Celery Worker直接使用同步接口
    """

    def __init__(
        self,
        graphdb_client,
        cache,
        conflict_resolver: ConflictResolver,
        dsl_parser: DSLParser,
        dsl_executor: DSLExecutor,
    ):
        self.graphdb = graphdb_client
        self.cache = cache
        self.conflict_resolver = conflict_resolver
        self.dsl_parser = dsl_parser
        self.dsl_executor = dsl_executor

    def compile_sync(
        self,
        tenant_id: str,
        l2_rules: Optional[List[Dict]] = None,
    ) -> CompileResult:
        """同步编译入口（供Celery Worker调用）"""
        start_time = time.time()
        errors = []

        try:
            # 1. 加载 L0/L1 规则（从 GraphDB）
            l0_rules = self._load_l0_rules_sync()

            # 2. 加载 L2 规则（参数传入或从数据库加载）
            if l2_rules is None:
                l2_rules = []

            # 3. 合并规则
            merged_rules = self._merge_rules(l0_rules, l2_rules)

            # 4. 冲突检测与解决
            conflicts = self.conflict_resolver.detect(merged_rules)
            critical_conflicts = [
                c for c in conflicts if c.severity.value == "critical"
            ]
            if critical_conflicts:
                return CompileResult(
                    success=False,
                    errors=[c.message for c in critical_conflicts],
                )

            resolved_rules = self.conflict_resolver.resolve(merged_rules)

            # 5. DSL 编译（验证公式语法）
            for rule in resolved_rules:
                conditions = rule.get("conditions", [])
                for cond in conditions:
                    formula_str = cond.get("formula")
                    if formula_str:
                        try:
                            self.dsl_parser.parse(formula_str)
                        except ValueError as e:
                            errors.append(f"Rule {rule.get('id')}: {e}")

            if errors:
                return CompileResult(success=False, errors=errors)

            # 6. 生成版本
            compile_time_ms = int((time.time() - start_time) * 1000)
            version = f"v{datetime.now().strftime('%Y%m%d%H%M%S')}"

            config = CompiledConfig(
                version=version,
                tenant_id=tenant_id,
                rules=resolved_rules,
                rule_count=len(resolved_rules),
                compile_time_ms=compile_time_ms,
                compiled_at=datetime.now().isoformat(),
            )

            return CompileResult(success=True, config=config)

        except Exception as e:
            logger.error(f"Compile error for tenant {tenant_id}: {e}")
            return CompileResult(success=False, errors=[str(e)])

    async def compile(
        self,
        tenant_id: str,
        l2_rules: Optional[List[Dict]] = None,
    ) -> CompileResult:
        """异步编译入口（供FastAPI服务调用）"""
        return await asyncio.to_thread(self.compile_sync, tenant_id, l2_rules)

    def _load_l0_rules_sync(self) -> List[Dict]:
        """从 GraphDB 同步加载 L0/L1 规则"""
        try:
            return self.graphdb.query_rules_sync()
        except Exception as e:
            logger.warning(f"Failed to load L0 rules from GraphDB: {e}")
            return []

    def _merge_rules(
        self, l0_rules: List[Dict], l2_rules: List[Dict]
    ) -> List[Dict]:
        """合并 L0/L1 和 L2 规则"""
        merged = list(l0_rules)
        # L2 rules override L0/L1 with same intent_id
        existing_intents = {r.get("intent_id") for r in merged if r.get("intent_id")}
        for rule in l2_rules:
            if rule.get("intent_id") in existing_intents:
                # Mark L0 rule as overridden
                for existing in merged:
                    if existing.get("intent_id") == rule.get("intent_id"):
                        existing["_overridden"] = True
            merged.append(rule)

        # Filter out overridden L0 rules
        return [r for r in merged if not r.get("_overridden")]
