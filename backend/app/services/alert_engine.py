"""
Alert engine - evaluates indicator values against thresholds and generates alert records.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.fi_indicator import FiIndicator
from backend.app.models.fi_indicator_value import FiIndicatorValue
from backend.app.models.fi_alert_record import FiAlertRecord


# Action suggestions by alert level (used for loan analysis recommendations)
_ACTION_SUGGESTIONS = {
    "pre_loan": {
        "warning": "该指标处于关注区间，建议补充近期财务报告进行核实",
        "alert": "该指标已触发预警阈值，建议提高授信条件或降低授信额度",
    },
    "post_loan": {
        "warning": "该指标出现关注信号，建议在本月内与企业进行沟通了解",
        "alert": "该指标已触发预警，请在5个工作日内启动现场核查流程",
    },
    "scf": {
        "warning": "供应链指标偏弱，建议审查应收账款账龄和核心企业信用状况",
        "alert": "供应链风险预警触发，建议暂缓放款并启动风险排查",
    },
}


def _compute_alert_level(
    value: Optional[Decimal],
    threshold_warning: Optional[Decimal],
    threshold_alert: Optional[Decimal],
    direction: str,
) -> str:
    """
    Compute alert level based on value vs thresholds.

    direction='above': higher is better (e.g., liquidity ratio)
      - value < threshold_alert  → alert
      - value < threshold_warning → warning
      - else                     → normal

    direction='below': lower is better (e.g., non-performing loan ratio)
      - value > threshold_alert  → alert
      - value > threshold_warning → warning
      - else                     → normal
    """
    if value is None:
        return "normal"

    val = float(value)

    if direction == "above":
        if threshold_alert is not None and val < float(threshold_alert):
            return "alert"
        if threshold_warning is not None and val < float(threshold_warning):
            return "warning"
    else:  # below
        if threshold_alert is not None and val > float(threshold_alert):
            return "alert"
        if threshold_warning is not None and val > float(threshold_warning):
            return "warning"

    return "normal"


class AlertEngine:
    """
    Evaluates indicator values against their configured thresholds
    and manages alert record persistence.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def evaluate_and_update(
        self,
        indicator_value: FiIndicatorValue,
        indicator: FiIndicator,
    ) -> str:
        """
        Compute alert level for a single indicator value and update in-place.
        Returns the computed alert level string.
        """
        level = _compute_alert_level(
            indicator_value.value,
            indicator.threshold_warning,
            indicator.threshold_alert,
            indicator.threshold_direction or "above",
        )
        indicator_value.alert_level = level
        return level

    async def batch_evaluate(
        self,
        company_id: UUID,
        calc_date: date,
        scenario: str,
    ) -> List[FiAlertRecord]:
        """
        Evaluate all indicator values for a company on a given date within a scenario.
        Clears existing alert records for that date, then writes new ones.
        Returns the list of newly created alert records.
        """
        # Fetch indicator values with their indicator definitions
        stmt = (
            select(FiIndicatorValue, FiIndicator)
            .join(FiIndicator, FiIndicatorValue.indicator_id == FiIndicator.id)
            .where(
                and_(
                    FiIndicatorValue.company_id == company_id,
                    FiIndicatorValue.calc_date == calc_date,
                    FiIndicator.scenario == scenario,
                )
            )
        )
        rows = (await self.db.execute(stmt)).all()

        # Delete existing alerts for this company/date/scenario
        existing_alert_ids = (
            select(FiAlertRecord.id)
            .join(FiIndicator, FiAlertRecord.indicator_id == FiIndicator.id)
            .where(
                and_(
                    FiAlertRecord.company_id == company_id,
                    FiAlertRecord.trigger_date == calc_date,
                    FiIndicator.scenario == scenario,
                )
            )
        )
        await self.db.execute(
            delete(FiAlertRecord).where(FiAlertRecord.id.in_(existing_alert_ids))
        )

        new_alerts: List[FiAlertRecord] = []
        suggestions = _ACTION_SUGGESTIONS.get(scenario, {})

        for ind_val, indicator in rows:
            level = _compute_alert_level(
                ind_val.value,
                indicator.threshold_warning,
                indicator.threshold_alert,
                indicator.threshold_direction or "above",
            )
            # Update alert_level on the value row
            ind_val.alert_level = level

            if level in ("warning", "alert"):
                threshold = (
                    indicator.threshold_alert if level == "alert"
                    else indicator.threshold_warning
                )
                alert = FiAlertRecord(
                    company_id=company_id,
                    indicator_id=indicator.id,
                    alert_level=level,
                    trigger_value=ind_val.value,
                    threshold_value=threshold,
                    trigger_date=calc_date,
                    action_suggestion=suggestions.get(level),
                    status="open",
                )
                self.db.add(alert)
                new_alerts.append(alert)

        await self.db.flush()
        return new_alerts

    async def get_alert_summary(
        self,
        company_id: UUID,
        calc_date: date,
        scenario: str,
    ) -> dict:
        """Return counts of normal/warning/alert indicators for a company/date/scenario."""
        stmt = (
            select(FiIndicatorValue.alert_level)
            .join(FiIndicator, FiIndicatorValue.indicator_id == FiIndicator.id)
            .where(
                and_(
                    FiIndicatorValue.company_id == company_id,
                    FiIndicatorValue.calc_date == calc_date,
                    FiIndicator.scenario == scenario,
                )
            )
        )
        levels = (await self.db.execute(stmt)).scalars().all()
        summary = {"normal": 0, "warning": 0, "alert": 0}
        for lv in levels:
            summary[lv] = summary.get(lv, 0) + 1
        return summary
