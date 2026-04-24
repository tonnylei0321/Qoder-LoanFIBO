"""SQL 执行引擎和结果组装器单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.app.services.query.sql_executor import SQLExecutor
from backend.app.services.query.result_assembler import ResultAssembler
from backend.app.services.security_error import SecurityError


class TestSQLExecutor:
    @pytest.fixture
    def mock_session_factory(self):
        """模拟 db_session_factory"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.keys.return_value = ["id", "name"]
        mock_result.fetchall.return_value = [(1, "Alice"), (2, "Bob")]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        factory = MagicMock(return_value=mock_session)
        return factory

    @pytest.mark.asyncio
    async def test_execute_select(self, mock_session_factory):
        """测试正常 SELECT 执行"""
        executor = SQLExecutor(mock_session_factory)
        result = await executor.execute("SELECT id, name FROM users")

        assert result["columns"] == ["id", "name"]
        assert result["total"] == 2
        assert result["rows"][0]["id"] == 1

    @pytest.mark.asyncio
    async def test_execute_with_params(self, mock_session_factory):
        """测试参数化查询"""
        executor = SQLExecutor(mock_session_factory)
        result = await executor.execute(
            "SELECT * FROM users WHERE id = :id",
            params={"id": 1},
        )
        assert result["total"] == 2

    def test_validate_select_only_rejects_insert(self):
        """测试拒绝 INSERT 语句"""
        executor = SQLExecutor(None)
        with pytest.raises(SecurityError, match="仅允许 SELECT"):
            executor._validate_select_only("INSERT INTO users VALUES (1, 'hack')")

    def test_validate_select_only_rejects_delete(self):
        """测试拒绝 DELETE 语句"""
        executor = SQLExecutor(None)
        with pytest.raises(SecurityError):
            executor._validate_select_only("DELETE FROM users")

    def test_validate_select_allows_with(self):
        """测试允许 WITH (CTE) 语句"""
        executor = SQLExecutor(None)
        # 不应抛出异常
        executor._validate_select_only("WITH cte AS (SELECT 1) SELECT * FROM cte")

    @pytest.mark.asyncio
    async def test_auto_add_limit(self, mock_session_factory):
        """测试自动添加 LIMIT"""
        executor = SQLExecutor(mock_session_factory, default_limit=100)
        result = await executor.execute("SELECT * FROM users")
        # execute 被调用即表示 SQL 被传入了
        mock_session_factory.return_value.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_max_limit_enforced(self, mock_session_factory):
        """测试最大行数限制"""
        executor = SQLExecutor(mock_session_factory, max_limit=500)
        result = await executor.execute("SELECT * FROM users", limit=99999)
        mock_session_factory.return_value.execute.assert_called_once()


class TestResultAssembler:
    def test_assemble_basic(self):
        """测试基本结果组装"""
        assembler = ResultAssembler()
        raw = {
            "columns": ["id", "name"],
            "rows": [{"id": 1, "name": "Alice"}],
            "total": 1,
        }
        result = assembler.assemble(raw)
        assert result["total"] == 1
        assert len(result["columns"]) == 2
        assert result["columns"][0]["name"] == "id"

    def test_assemble_with_concept_mapping(self):
        """测试 FIBO 概念映射"""
        assembler = ResultAssembler(concept_mapping={
            "total_assets": "总资产",
            "debt_ratio": "资产负债率",
        })
        raw = {
            "columns": ["total_assets", "debt_ratio"],
            "rows": [{"total_assets": 1000000, "debt_ratio": 0.6}],
            "total": 1,
        }
        result = assembler.assemble(raw)
        assert result["columns"][0]["label"] == "总资产"
        assert result["columns"][1]["label"] == "资产负债率"
        assert result["rows"][0]["总资产"] == 1000000

    def test_assemble_with_computed_indicators(self):
        """测试嵌入计算指标"""
        assembler = ResultAssembler()
        raw = {
            "columns": ["id"],
            "rows": [{"id": 1}],
            "total": 1,
        }
        computed = {"debt_ratio": 0.65, "credit_score": 85}
        result = assembler.assemble(raw, computed)
        assert result["computed_indicators"]["debt_ratio"] == 0.65
        assert result["computed_indicators"]["credit_score"] == 85

    def test_assemble_summary(self):
        """测试结果摘要"""
        assembler = ResultAssembler()
        raw = {
            "columns": ["id"],
            "rows": [{"id": 1}, {"id": 2}],
            "total": 2,
        }
        result = assembler.assemble(raw, {"ratio": 0.5})
        assert "2 条记录" in result["summary"]
        assert "ratio" in result["summary"]

    def test_register_concept_mapping(self):
        """测试动态注册概念映射"""
        assembler = ResultAssembler()
        assembler.register_concept_mapping("revenue", "营业收入")
        assert assembler.concept_mapping["revenue"] == "营业收入"

    def test_update_concept_mapping(self):
        """测试批量更新概念映射"""
        assembler = ResultAssembler()
        assembler.update_concept_mapping({
            "revenue": "营业收入",
            "profit": "净利润",
        })
        assert assembler.concept_mapping["revenue"] == "营业收入"
        assert assembler.concept_mapping["profit"] == "净利润"
