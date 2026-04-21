"""
Loan Analysis API - endpoints for credit risk analysis (pre-loan, post-loan, supply chain).
"""

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.models.fi_company import FiCompany
from backend.app.models.fi_dimension import FiDimension
from backend.app.models.fi_indicator import FiIndicator
from backend.app.models.fi_indicator_value import FiIndicatorValue
from backend.app.models.fi_score_record import FiScoreRecord
from backend.app.models.fi_alert_record import FiAlertRecord
from backend.app.schemas.loan_analysis import (
    CompanyCreate, CompanyUpdate, CompanyOut, CompanyListOut,
    DimensionOut, IndicatorOut, IndicatorValueOut,
    IndicatorValueBatchCreate, ScoreRecordOut, CompanyScoreResponse,
    AlertRecordOut, CalculateRequest, ApiResponse,
)
from backend.app.services.indicator_engine import IndicatorEngine
from backend.app.services.scoring_engine import ScoringEngine
from backend.app.services.alert_engine import AlertEngine

router = APIRouter(prefix="/loan-analysis", tags=["loan-analysis"])


# ─── Companies ──────────────────────────────────────────────────────

@router.get("/companies", response_model=ApiResponse)
async def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="搜索企业名称"),
    db: AsyncSession = Depends(get_db),
):
    """企业列表（分页+搜索）。"""
    query = select(FiCompany)
    count_query = select(func.count()).select_from(FiCompany)

    if search:
        query = query.where(FiCompany.name.ilike(f"%{search}%"))
        count_query = count_query.where(FiCompany.name.ilike(f"%{search}%"))

    total = (await db.execute(count_query)).scalar_one()
    companies = (
        await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()

    items = [CompanyOut.model_validate(c) for c in companies]
    return ApiResponse(data=CompanyListOut(items=items, total=total, page=page, page_size=page_size))


@router.post("/companies", response_model=ApiResponse, status_code=201)
async def create_company(body: CompanyCreate, db: AsyncSession = Depends(get_db)):
    """新建企业。"""
    company = FiCompany(**body.model_dump())
    db.add(company)
    await db.flush()
    await db.refresh(company)
    return ApiResponse(data=CompanyOut.model_validate(company))


@router.get("/companies/{company_id}", response_model=ApiResponse)
async def get_company(company_id: UUID, db: AsyncSession = Depends(get_db)):
    """企业详情（含监管标签）。"""
    company = await db.get(FiCompany, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="企业不存在")
    return ApiResponse(data=CompanyOut.model_validate(company))


@router.patch("/companies/{company_id}", response_model=ApiResponse)
async def update_company(company_id: UUID, body: CompanyUpdate, db: AsyncSession = Depends(get_db)):
    """更新企业信息。"""
    company = await db.get(FiCompany, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="企业不存在")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(company, field, value)
    await db.flush()
    await db.refresh(company)
    return ApiResponse(data=CompanyOut.model_validate(company))


# ─── Dimensions ──────────────────────────────────────────────────────

@router.get("/dimensions", response_model=ApiResponse)
async def list_dimensions(
    scenario: Optional[str] = Query(None, description="场景过滤：pre_loan / post_loan / scf"),
    db: AsyncSession = Depends(get_db),
):
    """维度列表（按场景过滤）。"""
    stmt = select(FiDimension).order_by(FiDimension.sort_order)
    if scenario:
        stmt = stmt.where(FiDimension.scenario == scenario)
    dims = (await db.execute(stmt)).scalars().all()
    return ApiResponse(data=[DimensionOut.model_validate(d) for d in dims])


# ─── Indicator Definitions ───────────────────────────────────────────

@router.get("/indicators", response_model=ApiResponse)
async def list_indicators(
    scenario: Optional[str] = Query(None),
    dimension_id: Optional[UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """指标定义列表（按场景/维度过滤）。"""
    stmt = select(FiIndicator).order_by(FiIndicator.code)
    if scenario:
        stmt = stmt.where(FiIndicator.scenario == scenario)
    if dimension_id:
        stmt = stmt.where(FiIndicator.dimension_id == dimension_id)
    indicators = (await db.execute(stmt)).scalars().all()
    return ApiResponse(data=[IndicatorOut.model_validate(i) for i in indicators])


@router.get("/indicators/{indicator_id}", response_model=ApiResponse)
async def get_indicator(indicator_id: UUID, db: AsyncSession = Depends(get_db)):
    """指标详情（含FIBO路径）。"""
    indicator = await db.get(FiIndicator, indicator_id)
    if not indicator:
        raise HTTPException(status_code=404, detail="指标不存在")
    return ApiResponse(data=IndicatorOut.model_validate(indicator))


# ─── Indicator Values ────────────────────────────────────────────────

@router.get("/companies/{company_id}/indicators", response_model=ApiResponse)
async def get_company_indicators(
    company_id: UUID,
    scenario: str = Query(..., description="场景：pre_loan / post_loan / scf"),
    calc_date: Optional[date] = Query(None, description="计算日期，默认最新"),
    db: AsyncSession = Depends(get_db),
):
    """企业指标值列表（按场景+日期，含维度分组信息）。"""
    # Verify company exists
    company = await db.get(FiCompany, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="企业不存在")

    # If no date, find the latest available date
    if calc_date is None:
        date_stmt = (
            select(func.max(FiIndicatorValue.calc_date))
            .join(FiIndicator, FiIndicatorValue.indicator_id == FiIndicator.id)
            .where(
                and_(
                    FiIndicatorValue.company_id == company_id,
                    FiIndicator.scenario == scenario,
                )
            )
        )
        calc_date = (await db.execute(date_stmt)).scalar_one_or_none()
        if calc_date is None:
            return ApiResponse(data=[])

    engine = IndicatorEngine(db)
    values = await engine.get_enriched_values(company_id, calc_date, scenario)
    return ApiResponse(data=values)


@router.post("/companies/{company_id}/values", response_model=ApiResponse)
async def upsert_indicator_values(
    company_id: UUID,
    body: IndicatorValueBatchCreate,
    db: AsyncSession = Depends(get_db),
):
    """批量录入/更新企业指标值（自动计算环比和预警级别）。"""
    company = await db.get(FiCompany, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="企业不存在")

    # Determine scenario from the first indicator
    if not body.values:
        return ApiResponse(data=[])

    first_ind = await db.get(FiIndicator, body.values[0].indicator_id)
    scenario = first_ind.scenario if first_ind else "pre_loan"

    engine = IndicatorEngine(db)
    rows = await engine.upsert_values(
        company_id=company_id,
        calc_date=body.calc_date,
        scenario=scenario,
        values=[v.model_dump() for v in body.values],
    )
    return ApiResponse(message=f"已更新 {len(rows)} 条指标值", data={"updated": len(rows)})


# ─── Score ───────────────────────────────────────────────────────────

@router.get("/companies/{company_id}/score", response_model=ApiResponse)
async def get_company_score(
    company_id: UUID,
    scenario: str = Query(..., description="场景：pre_loan / post_loan / scf"),
    calc_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """综合评分（最新或指定日期），含企业信息和预警汇总。"""
    company = await db.get(FiCompany, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="企业不存在")

    # Resolve date
    if calc_date is None:
        date_stmt = (
            select(func.max(FiScoreRecord.calc_date))
            .where(
                and_(
                    FiScoreRecord.company_id == company_id,
                    FiScoreRecord.scenario == scenario,
                )
            )
        )
        calc_date = (await db.execute(date_stmt)).scalar_one_or_none()

    score_record = None
    alert_summary = {"normal": 0, "warning": 0, "alert": 0}

    if calc_date:
        score_stmt = select(FiScoreRecord).where(
            and_(
                FiScoreRecord.company_id == company_id,
                FiScoreRecord.scenario == scenario,
                FiScoreRecord.calc_date == calc_date,
            )
        )
        score_record = (await db.execute(score_stmt)).scalar_one_or_none()

        alert_engine = AlertEngine(db)
        alert_summary = await alert_engine.get_alert_summary(company_id, calc_date, scenario)

    company_out = CompanyOut.model_validate(company)
    score_out = ScoreRecordOut.model_validate(score_record) if score_record else None

    return ApiResponse(data=CompanyScoreResponse(
        company=company_out,
        score_record=score_out,
        alert_summary=alert_summary,
        calc_date=calc_date or date.today(),
    ))


@router.post("/companies/{company_id}/calculate", response_model=ApiResponse)
async def calculate_score(
    company_id: UUID,
    body: CalculateRequest,
    db: AsyncSession = Depends(get_db),
):
    """触发评分和预警计算（批处理）。"""
    company = await db.get(FiCompany, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="企业不存在")

    # Optionally upsert new values if provided
    if body.values:
        ind_engine = IndicatorEngine(db)
        await ind_engine.upsert_values(
            company_id=company_id,
            calc_date=body.calc_date,
            scenario=body.scenario,
            values=[v.model_dump() for v in body.values],
        )

    # Run alert evaluation
    alert_engine = AlertEngine(db)
    alerts = await alert_engine.batch_evaluate(company_id, body.calc_date, body.scenario)

    # Run scoring
    scoring_engine = ScoringEngine(db)
    score_record = await scoring_engine.score(company_id, body.scenario, body.calc_date)

    return ApiResponse(
        message="计算完成",
        data={
            "total_score": float(score_record.total_score) if score_record.total_score else None,
            "risk_level": score_record.risk_level,
            "alert_count": len(alerts),
        },
    )


# ─── Alerts ──────────────────────────────────────────────────────────

@router.get("/companies/{company_id}/alerts", response_model=ApiResponse)
async def get_company_alerts(
    company_id: UUID,
    scenario: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="open / resolved"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """企业预警记录列表。"""
    company = await db.get(FiCompany, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="企业不存在")

    stmt = (
        select(FiAlertRecord, FiIndicator)
        .join(FiIndicator, FiAlertRecord.indicator_id == FiIndicator.id)
        .where(FiAlertRecord.company_id == company_id)
        .order_by(FiAlertRecord.trigger_date.desc())
        .limit(limit)
    )
    if scenario:
        stmt = stmt.where(FiIndicator.scenario == scenario)
    if status:
        stmt = stmt.where(FiAlertRecord.status == status)

    rows = (await db.execute(stmt)).all()

    result = []
    for alert, indicator in rows:
        d = AlertRecordOut.model_validate(alert)
        d.indicator_name = indicator.name
        d.indicator_code = indicator.code
        d.unit = indicator.unit
        result.append(d)

    return ApiResponse(data=result)
