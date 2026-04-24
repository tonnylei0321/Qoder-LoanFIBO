"""规则管理API - 接入编译缓存和调度器"""
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends

from backend.app.schemas.rules import RuleCreate, RuleResponse, CompileStatusResponse
from backend.app.dependencies import get_compile_cache, get_compile_scheduler
from backend.app.services.compile_cache import CompileCache
from backend.app.services.rules.compile_scheduler import CompileScheduler

router = APIRouter()


@router.post("/rules", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(rule: RuleCreate):
    """创建L2规则

    TODO: 持久化到数据库 (L2Rule model)，当前仅返回传入数据
    """
    return RuleResponse(
        id=f"rule_{rule.tenant_id}_{hash(rule.name) % 10000:04d}",
        tenant_id=rule.tenant_id,
        name=rule.name,
        rule_type=rule.rule_type,
        definition=rule.definition,
        priority=rule.priority,
        enabled=rule.enabled,
    )


@router.get("/rules/{tenant_id}", response_model=List[RuleResponse])
async def list_rules(tenant_id: str):
    """获取租户规则列表

    TODO: 从数据库查询 L2Rule，当前返回空列表
    """
    return []


@router.get("/compile-status/{tenant_id}", response_model=CompileStatusResponse)
async def get_compile_status(
    tenant_id: str,
    cache: CompileCache = Depends(get_compile_cache),
):
    """获取编译状态"""
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


@router.post("/compile/{tenant_id}", status_code=status.HTTP_202_ACCEPTED)
async def trigger_compile(
    tenant_id: str,
    scheduler: CompileScheduler = Depends(get_compile_scheduler),
):
    """触发规则编译"""
    job = scheduler.create_job(tenant_id=tenant_id)
    scheduler.enqueue(job)
    # 异步执行编译
    result = await scheduler.submit(job)

    if result.success:
        return {
            "tenant_id": tenant_id,
            "status": "completed",
            "version": result.config.version if result.config else None,
        }
    else:
        return {
            "tenant_id": tenant_id,
            "status": "failed",
            "errors": result.errors,
        }
