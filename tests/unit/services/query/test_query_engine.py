"""查询引擎单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.app.services.query.query_engine import QueryEngine, QueryResult, QueryStatus
from backend.app.services.query.intent_classifier import IntentClassifier
from backend.app.services.query.rule_matcher import RuleMatcher, CompiledRule
from backend.app.services.query.sql_generator import SQLGenerator
from backend.app.services.query.semantic_mapping import SemanticMapping, TableMapping
from backend.app.services.compile_cache import CompileCache


@pytest.fixture
def engine():
    mapping = SemanticMapping(
        concept_to_table={"loan:LoanContract": "bd_loan_contract"},
        relation_to_join={},
        table_mappings={
            "bd_loan_contract": TableMapping(
                table_name="bd_loan_contract",
                concept="loan:LoanContract",
                allowed_columns=["loan_amount", "contract_status"],
            )
        },
    )
    classifier = IntentClassifier(
        templates=[
            {"intent_id": "query_loan_amount", "patterns": ["贷款金额"], "slots": []}
        ]
    )
    rule_matcher = RuleMatcher()
    sql_generator = SQLGenerator(mapping=mapping)
    cache = AsyncMock(spec=CompileCache)
    cache.get_compile_status = AsyncMock(return_value="ready")
    cache.get_compiled_rules = AsyncMock(
        return_value={
            "version": "v1.0.0",
            "rules": [
                {
                    "id": "r1",
                    "intent_id": "query_loan_amount",
                    "table": "bd_loan_contract",
                    "columns": ["loan_amount"],
                    "conditions": [],
                    "priority": 10,
                }
            ],
        }
    )
    return QueryEngine(
        classifier=classifier,
        rule_matcher=rule_matcher,
        sql_generator=sql_generator,
        cache=cache,
    )


class TestQueryEngine:
    @pytest.mark.asyncio
    async def test_query_success(self, engine):
        result = await engine.query("tenant_001", "贷款金额", {})
        assert result.status == QueryStatus.SUCCESS or result.status == QueryStatus.REQUIRES_CONFIRMATION

    @pytest.mark.asyncio
    async def test_query_blocked_when_compiling(self, engine):
        engine.cache.get_compile_status = AsyncMock(return_value="L0_CRITICAL")
        result = await engine.query("tenant_001", "贷款金额", {})
        assert result.status == QueryStatus.SERVICE_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_query_blocked_when_compile_failed(self, engine):
        engine.cache.get_compile_status = AsyncMock(return_value="L0_CRITICAL_FAILED")
        result = await engine.query("tenant_001", "贷款金额", {})
        assert result.status == QueryStatus.RULE_COMPILE_FAILED

    @pytest.mark.asyncio
    async def test_unknown_query(self, engine):
        result = await engine.query("tenant_001", "今天天气", {})
        assert result.status == QueryStatus.REJECTED
