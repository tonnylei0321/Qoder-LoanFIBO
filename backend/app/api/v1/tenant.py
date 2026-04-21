"""租户配置API"""
from typing import List
from fastapi import APIRouter, HTTPException, status

from backend.app.schemas.rules import CompileStatusResponse

router = APIRouter()


@router.get("/tenants/{tenant_id}/config")
async def get_tenant_config(tenant_id: str):
    """获取租户配置"""
    # TODO: 集成数据库查询
    raise HTTPException(status_code=501, detail="租户配置查询功能待实现")


@router.put("/tenants/{tenant_id}/config")
async def update_tenant_config(tenant_id: str):
    """更新租户配置"""
    # TODO: 集成数据库更新
    raise HTTPException(status_code=501, detail="租户配置更新功能待实现")


@router.get("/tenants/{tenant_id}/compile-status", response_model=CompileStatusResponse)
async def get_tenant_compile_status(tenant_id: str):
    """获取租户编译状态"""
    # TODO: 集成编译缓存
    raise HTTPException(status_code=501, detail="编译状态查询功能待实现")
