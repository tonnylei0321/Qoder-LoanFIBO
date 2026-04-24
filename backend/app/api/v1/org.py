"""融资企业 & 授权项 API"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.org import (
    ApplicantOrgCreate, ApplicantOrgUpdate, ApplicantOrgResponse,
    AuthorizationScopeCreate, AuthorizationScopeUpdate, AuthorizationScopeResponse,
)
from backend.app.services.org_service import OrgService

router = APIRouter()


def _org_to_response(org) -> dict:
    """将 FiApplicantOrg 转为响应字典，包含掩码后的 security_id。"""
    data = {
        "id": str(org.id),
        "name": org.name,
        "unified_code": org.unified_code,
        "short_name": org.short_name,
        "industry": org.industry,
        "region": org.region,
        "legal_person": org.legal_person,
        "registered_capital": org.registered_capital,
        "contact_info": org.contact_info,
        "is_active": org.is_active,
        "security_id_masked": OrgService.mask_security_id(org.security_id) if org.security_id else None,
        "graph_uri": org.graph_uri,
        "extra": org.extra,
        "created_at": org.created_at.isoformat() if org.created_at else None,
        "updated_at": org.updated_at.isoformat() if org.updated_at else None,
    }
    return data


# ─── 融资企业 ─────────────────────────────────────────────

@router.get("/orgs")
async def list_orgs(
    active_only: bool = Query(False, description="仅返回有效企业"),
    db: AsyncSession = Depends(get_db),
):
    """融资企业列表"""
    svc = OrgService(db)
    orgs = await svc.list_orgs(active_only=active_only)
    return [_org_to_response(o) for o in orgs]


@router.get("/orgs/{org_id}")
async def get_org(org_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """获取融资企业详情"""
    svc = OrgService(db)
    org = await svc.get_org(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="融资企业不存在")
    return _org_to_response(org)


@router.post("/orgs", status_code=status.HTTP_201_CREATED)
async def create_org(data: ApplicantOrgCreate, db: AsyncSession = Depends(get_db)):
    """新增融资企业"""
    svc = OrgService(db)
    try:
        org = await svc.create_org(data)
        resp = _org_to_response(org)
        # 创建时返回明文 security_id（仅此一次）
        resp["security_id"] = org.security_id
        return resp
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/orgs/{org_id}")
async def update_org(org_id: uuid.UUID, data: ApplicantOrgUpdate, db: AsyncSession = Depends(get_db)):
    """更新融资企业"""
    svc = OrgService(db)
    org = await svc.update_org(org_id, data)
    if not org:
        raise HTTPException(status_code=404, detail="融资企业不存在")
    return _org_to_response(org)


@router.delete("/orgs/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org(org_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """停用融资企业（软删除）"""
    svc = OrgService(db)
    ok = await svc.delete_org(org_id)
    if not ok:
        raise HTTPException(status_code=404, detail="融资企业不存在")


@router.get("/orgs/{org_id}/security-id")
async def get_security_id(org_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """获取企业明文安全ID（仅管理员可用）"""
    svc = OrgService(db)
    org = await svc.get_org(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="融资企业不存在")
    if not org.security_id:
        raise HTTPException(status_code=404, detail="安全ID尚未生成")
    return {"security_id": org.security_id}


@router.get("/orgs/{org_id}/auth-scopes")
async def get_org_auth_scopes(org_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """获取企业已授权的授权项列表"""
    svc = OrgService(db)
    org = await svc.get_org(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="融资企业不存在")
    scope_ids: list = (org.extra or {}).get("auth_scope_ids", [])
    return {"scope_ids": scope_ids}


@router.put("/orgs/{org_id}/auth-scopes")
async def update_org_auth_scopes(
    org_id: uuid.UUID,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """更新企业授权项（覆盖写）"""
    svc = OrgService(db)
    org = await svc.get_org(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="融资企业不存在")
    scope_ids = body.get("scope_ids", [])
    extra = dict(org.extra or {})
    extra["auth_scope_ids"] = scope_ids
    from backend.app.schemas.org import ApplicantOrgUpdate
    await svc.update_org(org_id, ApplicantOrgUpdate(extra=extra))
    await db.commit()
    return {"scope_ids": scope_ids}


@router.post("/orgs/{org_id}/regenerate-security-id")
async def regenerate_security_id(org_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """重新生成安全ID（返回明文，仅展示一次）。"""
    svc = OrgService(db)
    org = await svc.regenerate_security_id(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="融资企业不存在")
    return {
        "code": 0,
        "data": {
            "org_id": str(org.id),
            "security_id": org.security_id,
            "security_id_masked": OrgService.mask_security_id(org.security_id),
        },
    }


# ─── 授权项 ───────────────────────────────────────────────

@router.get("/auth-scopes", response_model=List[AuthorizationScopeResponse])
async def list_auth_scopes(
    active_only: bool = Query(False, description="仅返回有效授权项"),
    db: AsyncSession = Depends(get_db),
):
    """授权项列表"""
    svc = OrgService(db)
    return await svc.list_auth_scopes(active_only=active_only)


@router.get("/auth-scopes/{scope_id}", response_model=AuthorizationScopeResponse)
async def get_auth_scope(scope_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """获取授权项详情"""
    svc = OrgService(db)
    scope = await svc.get_auth_scope(scope_id)
    if not scope:
        raise HTTPException(status_code=404, detail="授权项不存在")
    return scope


@router.post("/auth-scopes", response_model=AuthorizationScopeResponse, status_code=status.HTTP_201_CREATED)
async def create_auth_scope(data: AuthorizationScopeCreate, db: AsyncSession = Depends(get_db)):
    """新增授权项"""
    svc = OrgService(db)
    try:
        return await svc.create_auth_scope(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/auth-scopes/{scope_id}", response_model=AuthorizationScopeResponse)
async def update_auth_scope(scope_id: uuid.UUID, data: AuthorizationScopeUpdate, db: AsyncSession = Depends(get_db)):
    """更新授权项"""
    svc = OrgService(db)
    scope = await svc.update_auth_scope(scope_id, data)
    if not scope:
        raise HTTPException(status_code=404, detail="授权项不存在")
    return scope


@router.delete("/auth-scopes/{scope_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_auth_scope(scope_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """停用授权项（软删除）"""
    svc = OrgService(db)
    ok = await svc.delete_auth_scope(scope_id)
    if not ok:
        raise HTTPException(status_code=404, detail="授权项不存在")


# ─── 种子数据 ─────────────────────────────────────────────

@router.post("/seed", response_model=dict)
async def seed_default_data(db: AsyncSession = Depends(get_db)):
    """初始化 v8 标准授权项种子数据"""
    svc = OrgService(db)
    count = await svc.seed_default_auth_scopes()
    return {"seeded_auth_scopes": count}
