"""查询引擎 - 统一查询入口"""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from loguru import logger

from backend.app.services.query.intent_classifier import IntentClassifier
from backend.app.services.query.rule_matcher import RuleMatcher, CompiledRule
from backend.app.services.query.sql_generator import SQLGenerator
from backend.app.services.compile_cache import CompileCache


class QueryStatus(str, Enum):
    SUCCESS = "success"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    SERVICE_UNAVAILABLE = "service_unavailable"
    RULE_COMPILE_FAILED = "rule_compile_failed"
    REJECTED = "rejected"


@dataclass
class QueryResult:
    status: QueryStatus
    data: Optional[Dict] = None
    sql: Optional[str] = None
    message: str = ""
    retry_after: Optional[int] = None
    admin_alert: bool = False


class QueryEngine:
    """查询引擎"""

    def __init__(
        self,
        classifier: IntentClassifier,
        rule_matcher: RuleMatcher,
        sql_generator: SQLGenerator,
        cache: CompileCache,
    ):
        self.classifier = classifier
        self.rule_matcher = rule_matcher
        self.sql_generator = sql_generator
        self.cache = cache

    async def query(
        self,
        tenant_id: str,
        query_text: str,
        context: Dict,
        options: Optional[Dict] = None,
    ) -> QueryResult:
        # 0. 编译状态检查
        compile_status = await self.cache.get_compile_status(tenant_id)
        if compile_status in ("L0_CRITICAL", "L0_HIGH_COMPILING"):
            return QueryResult(
                status=QueryStatus.SERVICE_UNAVAILABLE,
                message="系统规则更新中，请稍后重试",
                retry_after=30,
            )
        elif compile_status in ("L0_CRITICAL_FAILED", "L0_CRITICAL_ERROR"):
            return QueryResult(
                status=QueryStatus.RULE_COMPILE_FAILED,
                message="系统规则更新失败，请联系管理员",
                admin_alert=True,
            )

        # 1. 意图分类
        classification = await self.classifier.classify(query_text, context)

        # 2. 未匹配意图
        if classification.intent_id == "unknown":
            return QueryResult(
                status=QueryStatus.REJECTED,
                message=classification.message or "无法理解的查询",
            )

        # 3. 需要确认
        if classification.requires_confirmation:
            return QueryResult(
                status=QueryStatus.REQUIRES_CONFIRMATION,
                message="请确认查询意图",
                data={"classification": classification},
            )

        # 4. 获取编译规则
        compiled_rules_data = await self.cache.get_compiled_rules(tenant_id)
        if not compiled_rules_data:
            return QueryResult(
                status=QueryStatus.SERVICE_UNAVAILABLE, message="规则未编译"
            )

        rules = [CompiledRule(**r) for r in compiled_rules_data.get("rules", [])]

        # 5. 规则匹配
        matched_rule = self.rule_matcher.match(
            classification.intent_id, classification.slots, rules
        )
        if not matched_rule:
            return QueryResult(
                status=QueryStatus.REJECTED, message="未找到匹配规则"
            )

        # 6. SQL生成
        try:
            sql, params = self.sql_generator.generate_safe(
                table_name=matched_rule.table,
                select_columns=matched_rule.columns,
                conditions=classification.slots,
            )
        except Exception as e:
            return QueryResult(
                status=QueryStatus.REJECTED, message=f"查询生成失败: {e}"
            )

        return QueryResult(
            status=QueryStatus.SUCCESS,
            sql=sql,
            data={"sql": sql, "params": params, "rule_id": matched_rule.id},
        )
