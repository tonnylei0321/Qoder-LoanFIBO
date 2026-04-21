"""
Scoring engine - multi-dimension weighted scoring for loan analysis scenarios.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.fi_indicator import FiIndicator
from backend.app.models.fi_indicator_value import FiIndicatorValue
from backend.app.models.fi_dimension import FiDimension
from backend.app.models.fi_score_record import FiScoreRecord


# Risk level mapping: score range → risk level
_RISK_LEVELS = [
    (90, "AAA"),
    (80, "AA"),
    (70, "A"),
    (60, "BBB"),
    (50, "BB"),
    (40, "B"),
    (0,  "CCC"),
]

# Suggestion templates by risk level
_SUGGESTION_TEMPLATES = {
    "AAA": "企业财务状况优秀，各维度指标表现良好，建议按申请额度予以授信，利率可给予优惠。",
    "AA":  "企业财务状况良好，整体风险可控，建议按申请额度予以授信。",
    "A":   "企业财务状况较好，存在少量关注项，建议在正常条件下予以授信，并持续关注预警指标。",
    "BBB": "企业财务状况一般，存在一定风险点，建议适当缩减授信额度并提高担保要求。",
    "BB":  "企业财务状况偏弱，多项指标处于关注区间，建议谨慎授信，要求提供足额抵押物。",
    "B":   "企业财务风险较高，多项指标触发预警，建议大幅缩减授信额度或要求联保，并加强贷后跟踪。",
    "CCC": "企业财务状况较差，存在重大风险信号，不建议新增授信，建议启动风险处置程序。",
}

_POST_LOAN_SUGGESTIONS = {
    "AAA": "企业运营状况良好，贷后风险低，建议维持正常监控频率（季度）。",
    "AA":  "企业运营状况稳定，建议保持季度监控并关注行业整体趋势。",
    "A":   "企业运营存在轻微波动，建议提升监控至月度，重点关注现金流指标。",
    "BBB": "企业多项指标出现关注信号，建议每月收集财务报告，与企业保持沟通。",
    "BB":  "企业风险有所上升，建议每月现场核查，评估是否需要追加担保。",
    "B":   "企业预警指标较多，建议立即启动现场核查，评估提前收回贷款的必要性。",
    "CCC": "企业存在重大风险信号，建议立即启动不良资产处置程序。",
}


def _score_indicator(
    value: Optional[Decimal],
    threshold_warning: Optional[Decimal],
    threshold_alert: Optional[Decimal],
    direction: str,
) -> float:
    """
    Score a single indicator on a 0-100 scale.

    Scoring logic (for direction='above'):
    - value >= threshold_warning: linear scale 60-100
    - threshold_alert <= value < threshold_warning: linear scale 30-60
    - value < threshold_alert: linear scale 0-30

    For direction='below', thresholds are inverted.
    """
    if value is None:
        return 50.0  # neutral score for missing data

    val = float(value)
    warn = float(threshold_warning) if threshold_warning is not None else None
    alert = float(threshold_alert) if threshold_alert is not None else None

    if warn is None and alert is None:
        return 75.0  # no thresholds configured, assume good

    if direction == "above":
        if warn is not None and val >= warn:
            # Good zone: 60-100
            if alert is not None and warn > alert:
                ratio = min((val - warn) / max(warn - alert, 1e-9), 1.0)
                return 60.0 + 40.0 * ratio
            return 75.0
        elif alert is not None and val < alert:
            # Alert zone: 0-30
            baseline = alert * 0.5
            ratio = max((val - baseline) / max(alert - baseline, 1e-9), 0.0)
            return 30.0 * ratio
        else:
            # Warning zone: 30-60
            low = alert if alert is not None else 0.0
            high = warn if warn is not None else low + 1.0
            ratio = (val - low) / max(high - low, 1e-9)
            return 30.0 + 30.0 * max(0.0, min(ratio, 1.0))
    else:
        # direction='below': lower is better
        if warn is not None and val <= warn:
            if alert is not None and warn < alert:
                ratio = min((warn - val) / max(alert - warn, 1e-9), 1.0)
                return 60.0 + 40.0 * ratio
            return 75.0
        elif alert is not None and val > alert:
            # Alert zone
            ceiling = alert * 1.5
            ratio = max((ceiling - val) / max(ceiling - alert, 1e-9), 0.0)
            return 30.0 * ratio
        else:
            high = alert if alert is not None else float("inf")
            low = warn if warn is not None else 0.0
            ratio = (high - val) / max(high - low, 1e-9)
            return 30.0 + 30.0 * max(0.0, min(ratio, 1.0))


def _map_risk_level(score: float) -> str:
    for threshold, level in _RISK_LEVELS:
        if score >= threshold:
            return level
    return "CCC"


class ScoringEngine:
    """
    Multi-dimension weighted scoring engine for loan analysis.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def score(
        self,
        company_id: UUID,
        scenario: str,
        calc_date: date,
    ) -> FiScoreRecord:
        """
        Calculate comprehensive score for a company/scenario/date.
        Persists result to fi_score_record (upsert by company/scenario/date).
        Returns the FiScoreRecord instance.
        """
        # Load dimensions for this scenario
        dim_stmt = (
            select(FiDimension)
            .where(FiDimension.scenario == scenario)
            .order_by(FiDimension.sort_order)
        )
        dimensions: List[FiDimension] = (await self.db.execute(dim_stmt)).scalars().all()

        # Load indicator values with indicator definitions
        val_stmt = (
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
        rows = (await self.db.execute(val_stmt)).all()

        # Group by dimension
        dim_values: Dict[UUID, List[Tuple[FiIndicatorValue, FiIndicator]]] = {}
        for iv, ind in rows:
            dim_id = ind.dimension_id
            if dim_id not in dim_values:
                dim_values[dim_id] = []
            dim_values[dim_id].append((iv, ind))

        # Compute dimension scores
        dimension_scores: Dict[str, dict] = {}
        total_weighted_score = 0.0
        total_weight = 0.0

        for dim in dimensions:
            items = dim_values.get(dim.id, [])
            if not items:
                dimension_scores[dim.code] = {
                    "name": dim.name,
                    "score": 0.0,
                    "weight": float(dim.weight),
                    "indicator_count": 0,
                    "normal_count": 0,
                    "warning_count": 0,
                    "alert_count": 0,
                }
                continue

            # Weighted average of indicator scores within dimension
            dim_weighted_score = 0.0
            dim_total_weight = 0.0
            normal_cnt = warning_cnt = alert_cnt = 0

            for iv, ind in items:
                ind_score = _score_indicator(
                    iv.value,
                    ind.threshold_warning,
                    ind.threshold_alert,
                    ind.threshold_direction or "above",
                )
                w = float(ind.weight) if ind.weight is not None else 1.0
                dim_weighted_score += ind_score * w
                dim_total_weight += w

                level = iv.alert_level or "normal"
                if level == "normal":
                    normal_cnt += 1
                elif level == "warning":
                    warning_cnt += 1
                else:
                    alert_cnt += 1

            dim_score = dim_weighted_score / dim_total_weight if dim_total_weight > 0 else 0.0
            dim_weight = float(dim.weight)

            dimension_scores[dim.code] = {
                "name": dim.name,
                "score": round(dim_score, 2),
                "weight": dim_weight,
                "indicator_count": len(items),
                "normal_count": normal_cnt,
                "warning_count": warning_cnt,
                "alert_count": alert_cnt,
            }

            total_weighted_score += dim_score * dim_weight
            total_weight += dim_weight

        total_score = round(total_weighted_score / total_weight, 2) if total_weight > 0 else 0.0
        risk_level = _map_risk_level(total_score)

        # Get suggestion template
        if scenario == "post_loan":
            suggestion = _POST_LOAN_SUGGESTIONS.get(risk_level, "")
        else:
            suggestion = _SUGGESTION_TEMPLATES.get(risk_level, "")

        # Upsert score record
        existing_stmt = select(FiScoreRecord).where(
            and_(
                FiScoreRecord.company_id == company_id,
                FiScoreRecord.scenario == scenario,
                FiScoreRecord.calc_date == calc_date,
            )
        )
        existing = (await self.db.execute(existing_stmt)).scalar_one_or_none()

        if existing:
            existing.total_score = total_score
            existing.risk_level = risk_level
            existing.dimension_scores = dimension_scores
            existing.suggestion = suggestion
            score_record = existing
        else:
            score_record = FiScoreRecord(
                company_id=company_id,
                scenario=scenario,
                total_score=total_score,
                risk_level=risk_level,
                dimension_scores=dimension_scores,
                suggestion=suggestion,
                calc_date=calc_date,
            )
            self.db.add(score_record)

        await self.db.flush()
        return score_record
