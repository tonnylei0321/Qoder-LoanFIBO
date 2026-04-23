"""指标值历史写入服务 — 双写：先 INSERT history，再 UPSERT value。

设计要点：
- fi_indicator_value_history: insert-only，每次采集追加一条，给趋势分析用
- fi_indicator_value: upsert 语义，只保留最新值，给前端展示用
- 采集时双写：先 INSERT history，再 UPSERT value（保证 value 始终是最新）
- 支持批量写入，共享 batch_id
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.fi_indicator import FiIndicator
from backend.app.models.fi_indicator_value import FiIndicatorValue
from backend.app.models.fi_indicator_value_history import FiIndicatorValueHistory
from backend.app.services.alert_engine import _compute_alert_level


class IndicatorHistoryWriter:
    """指标历史写入服务 — 管理双写逻辑。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def write_values(
        self,
        company_id: UUID,
        calc_date: date,
        values: List[dict],
        source: str = "agent",
        batch_id: UUID | None = None,
    ) -> dict:
        """双写：先 INSERT history，再 UPSERT value。

        Args:
            company_id: 企业 ID
            calc_date: 计算日期
            values: 指标值列表，每项包含 indicator_id, value, value_prev, data_quality 等
            source: 数据来源（agent/manual/import）
            batch_id: 批次 ID（不提供则自动生成）

        Returns:
            {"history_count": int, "upserted_count": int, "batch_id": str}
        """
        if not values:
            return {"history_count": 0, "upserted_count": 0, "batch_id": str(batch_id or uuid.uuid4())}

        if batch_id is None:
            batch_id = uuid.uuid4()

        # Pre-load indicator definitions for thresholds
        indicator_ids = [v["indicator_id"] for v in values]
        ind_stmt = select(FiIndicator).where(FiIndicator.id.in_(indicator_ids))
        indicators = {
            ind.id: ind
            for ind in (await self.db.execute(ind_stmt)).scalars().all()
        }

        # Pre-load existing values for upsert
        existing_stmt = select(FiIndicatorValue).where(
            and_(
                FiIndicatorValue.company_id == company_id,
                FiIndicatorValue.calc_date == calc_date,
                FiIndicatorValue.indicator_id.in_(indicator_ids),
            )
        )
        existing_map = {
            iv.indicator_id: iv
            for iv in (await self.db.execute(existing_stmt)).scalars().all()
        }

        history_count = 0
        upserted_count = 0

        for v in values:
            ind_id = v["indicator_id"]
            raw_value = v.get("value")
            raw_prev = v.get("value_prev")
            quality = v.get("data_quality")

            # Compute change_pct
            change_pct = None
            if raw_value is not None and raw_prev is not None and raw_prev != 0:
                change_pct = round(
                    (float(raw_value) - float(raw_prev)) / abs(float(raw_prev)) * 100, 4
                )

            # Compute alert level
            indicator = indicators.get(ind_id)
            if indicator:
                alert_level = _compute_alert_level(
                    Decimal(str(raw_value)) if raw_value is not None else None,
                    indicator.threshold_warning,
                    indicator.threshold_alert,
                    indicator.threshold_direction or "above",
                )
            else:
                alert_level = "normal"

            # 1. INSERT history (always append)
            history_row = FiIndicatorValueHistory(
                company_id=company_id,
                indicator_id=ind_id,
                value=raw_value,
                value_prev=raw_prev,
                change_pct=change_pct,
                alert_level=alert_level,
                data_quality=quality,
                calc_date=calc_date,
                source=source,
                batch_id=batch_id,
            )
            self.db.add(history_row)
            history_count += 1

            # 2. UPSERT value (keep latest snapshot)
            if ind_id in existing_map:
                row = existing_map[ind_id]
                row.value = raw_value
                row.value_prev = raw_prev
                row.change_pct = change_pct
                row.alert_level = alert_level
                if quality is not None:
                    row.data_quality = quality
            else:
                row = FiIndicatorValue(
                    company_id=company_id,
                    indicator_id=ind_id,
                    value=raw_value,
                    value_prev=raw_prev,
                    change_pct=change_pct,
                    alert_level=alert_level,
                    data_quality=quality,
                    calc_date=calc_date,
                )
                self.db.add(row)
            upserted_count += 1

        await self.db.flush()

        return {
            "history_count": history_count,
            "upserted_count": upserted_count,
            "batch_id": str(batch_id),
        }

    async def get_history_trend(
        self,
        company_id: UUID,
        indicator_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
    ) -> List[dict]:
        """查询指标历史趋势。

        Args:
            company_id: 企业 ID
            indicator_id: 指标 ID
            start_date: 起始日期
            end_date: 结束日期
            limit: 最大返回条数

        Returns:
            按日期升序排列的历史值列表
        """
        stmt = (
            select(FiIndicatorValueHistory)
            .where(
                and_(
                    FiIndicatorValueHistory.company_id == company_id,
                    FiIndicatorValueHistory.indicator_id == indicator_id,
                )
            )
            .order_by(FiIndicatorValueHistory.calc_date.asc())
            .limit(limit)
        )

        if start_date:
            stmt = stmt.where(FiIndicatorValueHistory.calc_date >= start_date)
        if end_date:
            stmt = stmt.where(FiIndicatorValueHistory.calc_date <= end_date)

        rows = (await self.db.execute(stmt)).scalars().all()

        return [
            {
                "id": str(r.id),
                "company_id": str(r.company_id),
                "indicator_id": str(r.indicator_id),
                "value": float(r.value) if r.value is not None else None,
                "value_prev": float(r.value_prev) if r.value_prev is not None else None,
                "change_pct": float(r.change_pct) if r.change_pct is not None else None,
                "alert_level": r.alert_level,
                "data_quality": r.data_quality,
                "calc_date": str(r.calc_date),
                "source": r.source,
                "batch_id": str(r.batch_id) if r.batch_id else None,
                "created_at": str(r.created_at),
            }
            for r in rows
        ]
