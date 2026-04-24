"""外键推断器单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from backend.app.models.table_foreign_key import TableForeignKey
from backend.app.services.sync.foreign_key_inferrer import ForeignKeyInferrer


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def inferrer(mock_db):
    return ForeignKeyInferrer(mock_db)


class TestForeignKeyInferrer:
    @pytest.mark.asyncio
    async def test_infer_from_schema_with_llm(self, inferrer, mock_db):
        """测试 LLM 外键推断"""
        mock_schema = "表 t1: id, name, dept_id\n表 t_dept: id, dept_name"
        llm_result = [
            {
                "source_table": "t1",
                "source_column": "dept_id",
                "target_table": "t_dept",
                "target_column": "id",
                "confidence": 0.95,
                "reason": "dept_id 后缀 _id 匹配 t_dept.id",
            }
        ]

        with patch.object(inferrer, '_get_schema_info', new_callable=AsyncMock, return_value=mock_schema), \
             patch.object(inferrer, '_call_llm_infer', new_callable=AsyncMock, return_value=llm_result):
            results = await inferrer.infer_from_schema(["t1", "t_dept"])

            assert len(results) == 1
            mock_db.add.assert_called_once()
            added = mock_db.add.call_args[0][0]
            assert added.source_table == "t1"
            assert added.source_column == "dept_id"
            assert added.target_table == "t_dept"
            assert added.confidence == 0.95
            assert added.status == "pending"
            assert added.inferred_by == "llm"

    @pytest.mark.asyncio
    async def test_approve_foreign_key(self, inferrer, mock_db):
        """测试审核通过外键"""
        fk = TableForeignKey(
            id="fk_test123",
            source_table="t1",
            source_column="dept_id",
            target_table="t_dept",
            target_column="id",
            confidence=0.9,
            status="pending",
            inferred_by="llm",
        )
        mock_db.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=fk)
        )

        result = await inferrer.approve("fk_test123")
        assert result.status == "approved"

    @pytest.mark.asyncio
    async def test_reject_foreign_key(self, inferrer, mock_db):
        """测试审核拒绝外键"""
        fk = TableForeignKey(
            id="fk_test456",
            source_table="t1",
            source_column="name",
            target_table="t_dept",
            target_column="id",
            confidence=0.3,
            status="pending",
            inferred_by="llm",
        )
        mock_db.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=fk)
        )

        result = await inferrer.reject("fk_test456")
        assert result.status == "rejected"

    @pytest.mark.asyncio
    async def test_approve_nonexistent_raises(self, inferrer, mock_db):
        """测试审核不存在的外键抛出异常"""
        mock_db.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=None)
        )

        with pytest.raises(ValueError, match="外键记录不存在"):
            await inferrer.approve("fk_nonexistent")
