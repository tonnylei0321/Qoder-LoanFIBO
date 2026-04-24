"""租户配置API - 接入编译缓存+租户管理器"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field

from backend.app.schemas.rules import CompileStatusResponse
from backend.app.dependencies import get_compile_cache
from backend.app.services.compile_cache import CompileCache
from backend.app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


class TenantRegisterRequest(BaseModel):
    """租户注册请求"""
    tenant_id: str = Field(..., description="租户ID")
    name: str = Field(..., description="租户名称")
    industry: str = Field(..., description="行业")
    tier: str = Field(default="tier2", description="租户层级")


class TenantResponse(BaseModel):
    """租户响应"""
    id: str
    name: str
    industry: str
    tier: str
    status: str


@router.post("/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def register_tenant(data: TenantRegisterRequest, db: AsyncSession = Depends(get_db)):
    """注册新租户"""
    from backend.app.services.tenant_manager import TenantManager
    mgr = TenantManager(db)
    try:
        tenant = await mgr.register_tenant(
            tenant_id=data.tenant_id,
            name=data.name,
            industry=data.industry,
            tier=data.tier,
        )
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return TenantResponse(
        id=tenant.id, name=tenant.name,
        industry=tenant.industry, tier=tenant.tier, status=tenant.status,
    )


@router.get("/tenants", response_model=List[TenantResponse])
async def list_tenants(db: AsyncSession = Depends(get_db)):
    """列出所有租户"""
    from backend.app.services.tenant_manager import TenantManager
    mgr = TenantManager(db)
    tenants = await mgr.list_tenants()
    return [
        TenantResponse(id=t.id, name=t.name, industry=t.industry, tier=t.tier, status=t.status)
        for t in tenants
    ]


@router.get("/tenants/{tenant_id}/config")
async def get_tenant_config(tenant_id: str, db: AsyncSession = Depends(get_db)):
    """获取租户配置"""
    from backend.app.services.tenant_manager import TenantManager
    mgr = TenantManager(db)
    config = await mgr.get_tenant_config(tenant_id)
    if config is None:
        raise HTTPException(status_code=404, detail="租户配置不存在")
    return {
        "tenant_id": config.tenant_id,
        "db_schema": config.db_schema,
        "compile_priority": config.compile_priority,
        "max_rules": config.max_rules,
        "nlq_enabled": config.nlq_enabled,
        "custom_settings": config.custom_settings,
    }


@router.put("/tenants/{tenant_id}/config")
async def update_tenant_config(tenant_id: str, db: AsyncSession = Depends(get_db)):
    """更新租户配置

    接收 JSON body 更新租户配置字段。
    """
    from backend.app.services.tenant_manager import TenantManager
    mgr = TenantManager(db)
    try:
        config = await mgr.update_tenant_config(tenant_id)
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "tenant_id": config.tenant_id,
        "db_schema": config.db_schema,
        "compile_priority": config.compile_priority,
        "max_rules": config.max_rules,
        "nlq_enabled": config.nlq_enabled,
        "custom_settings": config.custom_settings,
    }


@router.get("/tenants/{tenant_id}/compile-status", response_model=CompileStatusResponse)
async def get_tenant_compile_status(
    tenant_id: str,
    cache: CompileCache = Depends(get_compile_cache),
):
    """获取租户编译状态"""
    compile_status = await cache.get_compile_status(tenant_id)
    staleness = await cache.get_staleness_seconds(tenant_id)
    last_compile = await cache.get_last_compile(tenant_id)

    return CompileStatusResponse(
        tenant_id=tenant_id,
        status=compile_status or "never_compiled",
        current_version=last_compile.get("version") if last_compile else None,
        last_compiled_at=last_compile.get("compiled_at") if last_compile else None,
        staleness_seconds=staleness,
    )
