"""Pydantic schemas for the loan analysis API."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from uuid import UUID


# ─── Company Schemas ────────────────────────────────────────────────

class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    unified_code: Optional[str] = Field(None, max_length=64)
    short_name: Optional[str] = Field(None, max_length=128)
    industry: Optional[str] = Field(None, max_length=128)
    region: Optional[str] = Field(None, max_length=128)
    legal_person: Optional[str] = Field(None, max_length=64)
    registered_capital: Optional[str] = Field(None, max_length=64)
    reg_tags: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=256)
    unified_code: Optional[str] = Field(None, max_length=64)
    short_name: Optional[str] = Field(None, max_length=128)
    industry: Optional[str] = Field(None, max_length=128)
    region: Optional[str] = Field(None, max_length=128)
    legal_person: Optional[str] = Field(None, max_length=64)
    registered_capital: Optional[str] = Field(None, max_length=64)
    is_active: Optional[bool] = None
    reg_tags: Optional[Dict[str, Any]] = None


class CompanyOut(BaseModel):
    id: UUID
    name: str
    unified_code: Optional[str] = None
    short_name: Optional[str] = None
    industry: Optional[str] = None
    region: Optional[str] = None
    legal_person: Optional[str] = None
    registered_capital: Optional[str] = None
    is_active: Optional[bool] = True
    graph_uri: Optional[str] = None
    reg_tags: Dict[str, Any] = {}
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanyListOut(BaseModel):
    items: List[CompanyOut]
    total: int
    page: int
    page_size: int


# ─── Dimension Schemas ───────────────────────────────────────────────

class DimensionOut(BaseModel):
    id: UUID
    code: str
    name: str
    weight: float
    scenario: str
    sort_order: int

    model_config = {"from_attributes": True}


# ─── Indicator Schemas ───────────────────────────────────────────────

class IndicatorOut(BaseModel):
    id: UUID
    code: str
    name: str
    fibo_path: Optional[str]
    formula: Optional[str]
    data_source: Optional[str]
    unit: Optional[str]
    dimension_id: Optional[UUID]
    scenario: str
    weight: Optional[float]
    threshold_warning: Optional[float]
    threshold_alert: Optional[float]
    threshold_direction: str

    model_config = {"from_attributes": True}


class IndicatorWithDimensionOut(IndicatorOut):
    dimension_name: Optional[str] = None
    dimension_code: Optional[str] = None


# ─── Indicator Value Schemas ─────────────────────────────────────────

class IndicatorValueCreate(BaseModel):
    indicator_id: UUID
    value: Optional[float] = None
    value_prev: Optional[float] = None
    calc_date: date
    data_quality: Optional[str] = Field(None, pattern="^(P0|P1|P2)$")


class IndicatorValueOut(BaseModel):
    id: UUID
    company_id: UUID
    indicator_id: UUID
    value: Optional[float]
    value_prev: Optional[float]
    change_pct: Optional[float]
    alert_level: str
    data_quality: Optional[str]
    calc_date: date
    # Enriched fields from joins
    indicator_name: Optional[str] = None
    indicator_code: Optional[str] = None
    unit: Optional[str] = None
    fibo_path: Optional[str] = None
    formula: Optional[str] = None
    data_source: Optional[str] = None
    threshold_warning: Optional[float] = None
    threshold_alert: Optional[float] = None
    threshold_direction: Optional[str] = None
    dimension_code: Optional[str] = None
    dimension_name: Optional[str] = None

    model_config = {"from_attributes": True}


class IndicatorValueBatchCreate(BaseModel):
    company_id: UUID
    calc_date: date
    values: List[IndicatorValueCreate]


# ─── Score Record Schemas ────────────────────────────────────────────

class DimensionScoreDetail(BaseModel):
    score: float
    weight: float
    indicator_count: int
    normal_count: int
    warning_count: int
    alert_count: int


class ScoreRecordOut(BaseModel):
    id: UUID
    company_id: UUID
    scenario: str
    total_score: Optional[float]
    risk_level: Optional[str]
    dimension_scores: Dict[str, Any]
    suggestion: Optional[str]
    calc_date: date
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanyScoreResponse(BaseModel):
    """Complete score response with company info and alert summary."""
    company: CompanyOut
    score_record: Optional[ScoreRecordOut]
    alert_summary: Dict[str, int]  # {"normal": 20, "warning": 6, "alert": 2}
    calc_date: date


# ─── Alert Record Schemas ────────────────────────────────────────────

class AlertRecordOut(BaseModel):
    id: UUID
    company_id: UUID
    indicator_id: UUID
    alert_level: str
    trigger_value: Optional[float]
    threshold_value: Optional[float]
    trigger_date: date
    action_suggestion: Optional[str]
    status: str
    created_at: datetime
    # Enriched
    indicator_name: Optional[str] = None
    indicator_code: Optional[str] = None
    unit: Optional[str] = None

    model_config = {"from_attributes": True}


# ─── Calculate Request ───────────────────────────────────────────────

class CalculateRequest(BaseModel):
    scenario: str = Field(..., pattern="^(pre_loan|post_loan|scf)$")
    calc_date: date
    values: Optional[List[IndicatorValueCreate]] = None  # If None, re-calculate from existing values


# ─── Generic Response ────────────────────────────────────────────────

class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[Any] = None
