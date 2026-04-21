"""RuleCompiler核心编译器单元测试"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from backend.app.services.rules.compiler import RuleCompiler, CompileResult, CompiledConfig
from backend.app.services.rules.conflict_resolver import ConflictResolver
from backend.app.services.rules.dsl_parser import DSLParser
from backend.app.services.rules.dsl_executor import DSLExecutor


@pytest.fixture
def mock_graphdb():
    client = MagicMock()
    client.query_rules_sync = MagicMock(return_value=[
        {"rule": "r0", "table": "bd_loan_contract", "field": "loan_amount", "target": "loan:LoanAmount"}
    ])
    return client


@pytest.fixture
def mock_cache():
    cache = MagicMock()
    cache.set_compiled_rules = AsyncMock(return_value=True)
    cache.set_compile_status = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def compiler(mock_graphdb, mock_cache):
    return RuleCompiler(
        graphdb_client=mock_graphdb,
        cache=mock_cache,
        conflict_resolver=ConflictResolver(),
        dsl_parser=DSLParser(),
        dsl_executor=DSLExecutor(),
    )


class TestRuleCompilerSync:
    def test_compile_sync_success(self, compiler):
        l2_rules = [
            {"id": "l2_1", "intent_id": "query_loan", "table": "bd_loan_contract",
             "columns": ["loan_amount"], "conditions": [], "priority": 10}
        ]
        result = compiler.compile_sync("tenant_001", l2_rules=l2_rules)
        assert result.success is True
        assert result.config is not None
        assert result.config.tenant_id == "tenant_001"

    def test_compile_sync_with_conflict(self, compiler):
        l2_rules = [
            {"id": "l2_1", "intent_id": "query_loan", "table": "t1",
             "columns": ["c1"], "conditions": [], "priority": 10},
            {"id": "l2_2", "intent_id": "query_loan", "table": "t2",
             "columns": ["c2"], "conditions": [], "priority": 5},
        ]
        result = compiler.compile_sync("tenant_001", l2_rules=l2_rules)
        assert result.success is True
        # Conflict resolved: only higher priority rule kept
        loan_rules = [r for r in result.config.rules if r.get("intent_id") == "query_loan"]
        assert len(loan_rules) == 1
        assert loan_rules[0]["priority"] == 10

    def test_compile_sync_empty_rules(self, compiler):
        result = compiler.compile_sync("tenant_001", l2_rules=[])
        assert result.success is True


class TestRuleCompilerAsync:
    @pytest.mark.asyncio
    async def test_compile_async(self, compiler):
        l2_rules = [
            {"id": "l2_1", "intent_id": "query_overdue", "table": "bd_loan_contract",
             "columns": ["overdue_amount"], "conditions": [], "priority": 8}
        ]
        result = await compiler.compile("tenant_001", l2_rules=l2_rules)
        assert result.success is True


class TestCompileResult:
    def test_success_result(self):
        config = CompiledConfig(version="v1.0.0", tenant_id="t1", rules=[])
        result = CompileResult(success=True, config=config)
        assert result.success is True
        assert result.config.version == "v1.0.0"

    def test_failure_result(self):
        result = CompileResult(success=False, errors=["conflict detected"])
        assert result.success is False
        assert len(result.errors) == 1
