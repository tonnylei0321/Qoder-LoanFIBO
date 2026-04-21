"""
Indicator engine - manages indicator value ingestion and change_pct computation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.fi_indicator import FiIndicator
from backend.app.models.fi_indicator_value import FiIndicatorValue
from backend.app.services.alert_engine import _compute_alert_level


class IndicatorEngine:
    """
    Handles batch ingestion and recalculation of indicator values.

    V1: Values are provided externally (manually entered or from ERP export).
    The engine computes change_pct from the previous value and determines alert_level.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert_values(
        self,
        company_id: UUID,
        calc_date: date,
        scenario: str,
        values: List[dict],
    ) -> List[FiIndicatorValue]:
        """
        Upsert indicator values for a company/date.

        Each item in `values` should have:
          - indicator_id: UUID
          - value: Optional[float]
          - value_prev: Optional[float]
          - data_quality: Optional[str]

        Computes change_pct and alert_level automatically.
        Returns all upserted FiIndicatorValue rows.
        """
        # Pre-load indicator definitions for thresholds
        indicator_ids = [v["indicator_id"] for v in values]
        ind_stmt = select(FiIndicator).where(FiIndicator.id.in_(indicator_ids))
        indicators = {
            ind.id: ind
            for ind in (await self.db.execute(ind_stmt)).scalars().all()
        }

        # Pre-load existing values for this company/date
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

        result_rows: List[FiIndicatorValue] = []

        for v in values:
            ind_id = v["indicator_id"]
            raw_value = v.get("value")
            raw_prev = v.get("value_prev")
            quality = v.get("data_quality")

            # Compute change_pct
            change_pct = None
            if raw_value is not None and raw_prev is not None and raw_prev != 0:
                change_pct = round((float(raw_value) - float(raw_prev)) / abs(float(raw_prev)) * 100, 4)

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

            if ind_id in existing_map:
                # Update existing
                row = existing_map[ind_id]
                row.value = raw_value
                row.value_prev = raw_prev
                row.change_pct = change_pct
                row.alert_level = alert_level
                if quality is not None:
                    row.data_quality = quality
            else:
                # Insert new
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

            result_rows.append(row)

        await self.db.flush()
        return result_rows

    async def get_enriched_values(
        self,
        company_id: UUID,
        calc_date: date,
        scenario: str,
    ) -> List[dict]:
        """
        Return indicator values enriched with indicator metadata and dimension info.
        """
        from backend.app.models.fi_dimension import FiDimension

        stmt = (
            select(FiIndicatorValue, FiIndicator, FiDimension)
            .join(FiIndicator, FiIndicatorValue.indicator_id == FiIndicator.id)
            .outerjoin(FiDimension, FiIndicator.dimension_id == FiDimension.id)
            .where(
                and_(
                    FiIndicatorValue.company_id == company_id,
                    FiIndicatorValue.calc_date == calc_date,
                    FiIndicator.scenario == scenario,
                )
            )
            .order_by(FiDimension.sort_order, FiIndicator.code)
        )
        rows = (await self.db.execute(stmt)).all()

        result = []
        for iv, ind, dim in rows:
            result.append({
                "id": str(iv.id),
                "company_id": str(iv.company_id),
                "indicator_id": str(iv.indicator_id),
                "value": float(iv.value) if iv.value is not None else None,
                "value_prev": float(iv.value_prev) if iv.value_prev is not None else None,
                "change_pct": float(iv.change_pct) if iv.change_pct is not None else None,
                "alert_level": iv.alert_level,
                "data_quality": iv.data_quality,
                "calc_date": str(iv.calc_date),
                "indicator_name": ind.name,
                "indicator_code": ind.code,
                "unit": ind.unit,
                "fibo_path": ind.fibo_path,
                "formula": ind.formula,
                "data_source": ind.data_source,
                "threshold_warning": float(ind.threshold_warning) if ind.threshold_warning is not None else None,
                "threshold_alert": float(ind.threshold_alert) if ind.threshold_alert is not None else None,
                "threshold_direction": ind.threshold_direction,
                "dimension_code": dim.code if dim else None,
                "dimension_name": dim.name if dim else None,
            })
        return result
