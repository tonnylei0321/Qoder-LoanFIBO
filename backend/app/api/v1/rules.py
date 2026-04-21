"""规则管理API"""
from typing import List
from fastapi import APIRouter, HTTPException, status

from backend.app.schemas.rules import RuleCreate, RuleResponse, CompileStatusResponse

router = APIRouter()


@router.post("/rules", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(rule: RuleCreate):
    """创建L2规则"""
    # TODO: 集成规则服务
    raise HTTPException(status_code=501, detail="规则创建功能待实现")


@router.get("/rules/{tenant_id}", response_model=List[RuleResponse])
async def list_rules(tenant_id: str):
    """获取租户规则列表"""
    # TODO: 集成规则服务
    raise HTTPException(status_code=501, detail="规则列表功能待实现")


@router.get("/compile-status/{tenant_id}", response_model=CompileStatusResponse)
async def get_compile_status(tenant_id: str):
    """获取编译状态"""
    # TODO: 集成编译缓存
    raise HTTPException(status_code=501, detail="编译状态查询功能待实现")


@router.post("/compile/{tenant_id}", status_code=status.HTTP_202_ACCEPTED)
async def trigger_compile(tenant_id: str):
    """触发规则编译"""
    # TODO: 集成编译调度器
    raise HTTPException(status_code=501, detail="规则编译功能待实现")
