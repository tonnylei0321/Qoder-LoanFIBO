"""单元测试 — 指标历史写入服务 IndicatorHistoryWriter。"""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.services.indicator_history import IndicatorHistoryWriter


@pytest.fixture
def mock_db():
    """模拟 AsyncSession。"""
    db = AsyncMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def writer(mock_db):
    return IndicatorHistoryWriter(db=mock_db)


@pytest.fixture
def fake_company_id():
    return uuid.uuid4()


@pytest.fixture
def fake_indicator_id():
    return uuid.uuid4()


class TestWriteValues:
    """write_values 双写测试。"""

    @pytest.mark.asyncio
    async def test_empty_values_returns_zero(self, writer, fake_company_id):
        """空值列表应返回零计数。"""
        result = await writer.write_values(
            company_id=fake_company_id,
            calc_date=date.today(),
            values=[],
        )
        assert result["history_count"] == 0
        assert result["upserted_count"] == 0

    @pytest.mark.asyncio
    async def test_creates_batch_id_if_not_provided(self, writer, fake_company_id, fake_indicator_id):
        """未提供 batch_id 时应自动生成。"""
        # Mock indicator lookup
        mock_indicator = MagicMock()
        mock_indicator.id = fake_indicator_id
        mock_indicator.threshold_warning = None
        mock_indicator.threshold_alert = None
        mock_indicator.threshold_direction = "above"

        mock_db = writer.db
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_indicator]
        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = []
        mock_db.execute.side_effect = [mock_result, mock_result2]

        result = await writer.write_values(
            company_id=fake_company_id,
            calc_date=date.today(),
            values=[{"indicator_id": fake_indicator_id, "value": 100.0}],
        )
        assert result["history_count"] == 1
        assert result["upserted_count"] == 1
        assert result["batch_id"] is not None

    @pytest.mark.asyncio
    async def test_uses_provided_batch_id(self, writer, fake_company_id, fake_indicator_id):
        """提供 batch_id 时应使用它。"""
        batch_id = uuid.uuid4()

        mock_indicator = MagicMock()
        mock_indicator.id = fake_indicator_id
        mock_indicator.threshold_warning = None
        mock_indicator.threshold_alert = None
        mock_indicator.threshold_direction = "above"

        mock_db = writer.db
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_indicator]
        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = []
        mock_db.execute.side_effect = [mock_result, mock_result2]

        result = await writer.write_values(
            company_id=fake_company_id,
            calc_date=date.today(),
            values=[{"indicator_id": fake_indicator_id, "value": 100.0}],
            batch_id=batch_id,
        )
        assert result["batch_id"] == str(batch_id)

    @pytest.mark.asyncio
    async def test_change_pct_computation(self, writer, fake_company_id, fake_indicator_id):
        """change_pct 应正确计算。"""
        mock_indicator = MagicMock()
        mock_indicator.id = fake_indicator_id
        mock_indicator.threshold_warning = None
        mock_indicator.threshold_alert = None
        mock_indicator.threshold_direction = "above"

        mock_db = writer.db
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_indicator]
        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = []
        mock_db.execute.side_effect = [mock_result, mock_result2]

        # spy on db.add to capture history row
        added_objects = []
        mock_db.add.side_effect = lambda obj: added_objects.append(obj)

        await writer.write_values(
            company_id=fake_company_id,
            calc_date=date.today(),
            values=[{
                "indicator_id": fake_indicator_id,
                "value": 120.0,
                "value_prev": 100.0,
            }],
        )

        # history row should have change_pct = 20.0
        history_rows = [
            o for o in added_objects
            if hasattr(o, '__tablename__') and o.__tablename__ == 'fi_indicator_value_history'
        ]
        assert len(history_rows) == 1
        assert float(history_rows[0].change_pct) == 20.0

    @pytest.mark.asyncio
    async def test_source_is_stored_in_history(self, writer, fake_company_id, fake_indicator_id):
        """source 应存入历史记录。"""
        mock_indicator = MagicMock()
        mock_indicator.id = fake_indicator_id
        mock_indicator.threshold_warning = None
        mock_indicator.threshold_alert = None
        mock_indicator.threshold_direction = "above"

        mock_db = writer.db
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_indicator]
        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = []
        mock_db.execute.side_effect = [mock_result, mock_result2]

        added_objects = []
        mock_db.add.side_effect = lambda obj: added_objects.append(obj)

        await writer.write_values(
            company_id=fake_company_id,
            calc_date=date.today(),
            values=[{"indicator_id": fake_indicator_id, "value": 100.0}],
            source="agent",
        )

        history_rows = [
            o for o in added_objects
            if hasattr(o, '__tablename__') and o.__tablename__ == 'fi_indicator_value_history'
        ]
        assert history_rows[0].source == "agent"


class TestGetHistoryTrend:
    """get_history_trend 查询测试。"""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_data(self, writer, fake_company_id, fake_indicator_id):
        """无数据时应返回空列表。"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        writer.db.execute.return_value = mock_result

        result = await writer.get_history_trend(
            company_id=fake_company_id,
            indicator_id=fake_indicator_id,
        )
        assert result == []
