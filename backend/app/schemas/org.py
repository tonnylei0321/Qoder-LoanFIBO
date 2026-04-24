"""融资企业 & 授权项 — Pydantic Schemas"""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ─── 融资企业 ─────────────────────────────────────────────

class ApplicantOrgCreate(BaseModel):
    name: str = Field(..., max_length=256, description="企业名称")
    unified_code: Optional[str] = Field(None, max_length=64, description="统一社会信用代码")
    short_name: Optional[str] = Field(None, max_length=128, description="企业简称")
    industry: Optional[str] = Field(None, max_length=128, description="行业分类")
    region: Optional[str] = Field(None, max_length=128, description="注册地区")
    legal_person: Optional[str] = Field(None, max_length=64, description="法定代表人")
    registered_capital: Optional[str] = Field(None, max_length=64, description="注册资本")
    contact_info: Optional[str] = Field(None, description="联系方式(JSON)")
    extra: Optional[dict] = Field(None, description="扩展字段")


class ApplicantOrgUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=256)
    unified_code: Optional[str] = Field(None, max_length=64)
    short_name: Optional[str] = Field(None, max_length=128)
    industry: Optional[str] = Field(None, max_length=128)
    region: Optional[str] = Field(None, max_length=128)
    legal_person: Optional[str] = Field(None, max_length=64)
    registered_capital: Optional[str] = Field(None, max_length=64)
    contact_info: Optional[str] = None
    is_active: Optional[bool] = None
    extra: Optional[dict] = None


class ApplicantOrgResponse(BaseModel):
    id: uuid.UUID
    name: str
    unified_code: Optional[str] = None
    short_name: Optional[str] = None
    industry: Optional[str] = None
    region: Optional[str] = None
    legal_person: Optional[str] = None
    registered_capital: Optional[str] = None
    contact_info: Optional[str] = None
    is_active: bool = True
    security_id_masked: Optional[str] = None
    graph_uri: Optional[str] = None
    extra: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─── 授权项 ───────────────────────────────────────────────

class AuthorizationScopeCreate(BaseModel):
    code: str = Field(..., max_length=64, description="授权项编码，如 ERP_AR")
    label: str = Field(..., max_length=256, description="授权项名称")
    category: Optional[str] = Field(None, max_length=64, description="分类: ERP/财务/征信/税务/银行")
    description: Optional[str] = Field(None, description="详细说明")
    extra: Optional[dict] = Field(None, description="扩展字段")


class AuthorizationScopeUpdate(BaseModel):
    code: Optional[str] = Field(None, max_length=64)
    label: Optional[str] = Field(None, max_length=256)
    category: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    extra: Optional[dict] = None


class AuthorizationScopeResponse(BaseModel):
    id: uuid.UUID
    code: str
    label: str
    category: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    graph_uri: Optional[str] = None
    extra: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
