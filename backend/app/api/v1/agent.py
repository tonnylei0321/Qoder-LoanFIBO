"""Agent 管理 REST API + WebSocket + SSE 端点。

端点列表：
- WS:  /agent/connect          — ERP 代理接入
- SSE: /agent/events           — 前端实时结果推送
- POST /agent/orgs             — 企业注册
- POST /agent/orgs/{org_id}/credentials — 凭证生成
- PUT  /agent/credentials/{client_id}/revoke — 凭证吊销
- GET  /agent/status           — 代理连接状态
- GET  /agent/downloads        — 安装包下载
- GET  /agent/audit-logs       — 审计日志
- POST /agent/versions         — 版本上传
- GET  /agent/versions         — 版本列表
- GET  /agent/traces           — 追踪列表
- GET  /agent/traces/{trace_id} — 追踪详情
- POST /agent/task             — 提交任务
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.middleware.rate_limit import get_ws_rate_limiter
from backend.app.models.agent_audit_log import AgentAuditLog
from backend.app.models.agent_credential import AgentCredential
from backend.app.models.agent_trace import AgentTrace
from backend.app.models.agent_version import AgentVersion
from backend.app.models.fi_applicant_org import FiApplicantOrg
from backend.app.services.agent.credential import credential_service
from backend.app.services.agent.heartbeat import get_heartbeat_service
from backend.app.services.agent.router import get_router
from backend.app.services.agent.task_queue import get_task_queue
from backend.app.services.agent.tracer import get_tracer
from backend.app.services.agent.ws_handler import get_ws_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


# ---------------------------------------------------------------------------
# Pydantic 模型
# ---------------------------------------------------------------------------

class OrgRegisterRequest(BaseModel):
    name: str
    industry: str = ""
    datasource: str = "NCC"


class VersionUploadRequest(BaseModel):
    version: str
    platform: str  # "windows" or "linux"
    download_url: str
    min_version: str = "1.0.0"


class TaskSubmitRequest(BaseModel):
    org_id: str
    datasource: str
    action: str
    payload: dict
    timeout_ms: int = 30000


# ---------------------------------------------------------------------------
# 管理后台 JWT 认证依赖（Mock 实现，后续替换为真实 JWT）
# ---------------------------------------------------------------------------

async def get_current_admin(request: Request):
    """从 Authorization Bearer token 提取管理员身份。

    当前为 Mock 实现：接受任意 token。
    后续替换为真实 JWT 验证。
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Empty token")

    # Mock: 从 token 解析用户信息
    # TODO: 替换为真实 JWT 解码
    return {
        "username": "admin",
        "role": "admin",
    }


# ---------------------------------------------------------------------------
# 审计日志辅助
# ---------------------------------------------------------------------------

async def _write_audit_log(
    db: AsyncSession,
    org_id: str,
    action: str,
    operator: str,
    ip: str,
    detail: dict | None = None,
) -> None:
    """写入审计日志。"""
    log = AgentAuditLog(
        org_id=org_id,
        action=action,
        operator=operator,
        ip=ip,
        detail=detail or {},
    )
    db.add(log)
    await db.flush()


# ---------------------------------------------------------------------------
# WebSocket 端点（8.1）
# ---------------------------------------------------------------------------

@router.websocket("/connect")
async def ws_connect(websocket: WebSocket):
    """ERP 代理 WebSocket 接入端点。

    安全设计：
    1. IP 速率限制（10次/分钟）
    2. 首条消息 auth 认证（非 query param）
    3. register 5秒超时断开
    """
    # IP 速率限制
    client_ip = websocket.client.host if websocket.client else "unknown"
    limiter = get_ws_rate_limiter()
    if not limiter.is_allowed(client_ip):
        await websocket.close(code=429, reason="rate limit exceeded")
        return

    await websocket.accept()

    # 获取 DB session
    from backend.app.database import async_session_factory
    async with async_session_factory() as db:
        try:
            handler = get_ws_handler()
            await handler.handle_connection(
                websocket, db_session=db, client_ip=client_ip
            )
        finally:
            await db.commit()


# ---------------------------------------------------------------------------
# SSE 端点（9.4 前端结果推送）
# ---------------------------------------------------------------------------

@router.get("/events")
async def sse_events(
    org_id: Optional[str] = Query(None),
    last_event_id: Optional[str] = Query(None, alias="Last-Event-ID"),
):
    """SSE 推送端点 — 前端实时获取任务结果。"""
    task_queue = get_task_queue()
    queue = task_queue.register_sse_client()

    async def event_generator():
        try:
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30)
                    # 如果指定了 org_id，只推送匹配的事件
                    if org_id and data.get("org_id") and data["org_id"] != org_id:
                        continue
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    # 心跳帧，保持连接
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            task_queue.unregister_sse_client(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# 企业注册（10.1）
# ---------------------------------------------------------------------------

@router.post("/orgs")
async def register_org(
    req: OrgRegisterRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    """创建企业 + 分配 org_id + 生成首组凭证。"""
    # 创建企业
    org = FiApplicantOrg(
        name=req.name,
        industry=req.industry,
    )
    db.add(org)
    await db.flush()
    org_id = str(org.id)

    # 生成首组凭证
    cred_result = await credential_service.generate(db, org_id, req.datasource)

    # 审计日志
    client_ip = "0.0.0.0"  # 从 request 中获取，此处简化
    await _write_audit_log(
        db, org_id, "org_registered", admin["username"], client_ip,
        {"name": req.name, "datasource": req.datasource},
    )

    await db.commit()

    return {
        "code": 0,
        "data": {
            "org_id": org_id,
            "name": req.name,
            "credential": cred_result,
        },
    }


# ---------------------------------------------------------------------------
# 凭证管理（10.2）
# ---------------------------------------------------------------------------

@router.post("/orgs/{org_id}/credentials")
async def create_credential(
    org_id: str,
    datasource: str = Query("NCC"),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    """生成新凭证（client_id + client_secret，仅展示一次）。"""
    cred_result = await credential_service.generate(db, org_id, datasource)

    await _write_audit_log(
        db, org_id, "credential_generated", admin["username"], "0.0.0.0",
        {"client_id": cred_result["client_id"], "datasource": datasource},
    )

    await db.commit()

    return {"code": 0, "data": cred_result}


@router.put("/credentials/{client_id}/revoke")
async def revoke_credential(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    """吊销凭证。"""
    cred = await credential_service.revoke(db, client_id)
    if cred is None:
        raise HTTPException(status_code=404, detail="Credential not found")

    await _write_audit_log(
        db, str(cred.org_id), "credential_revoked", admin["username"], "0.0.0.0",
        {"client_id": client_id},
    )

    await db.commit()

    return {"code": 0, "data": {"client_id": client_id, "revoked": True}}


# ---------------------------------------------------------------------------
# 代理连接状态（8.5 / 10.4）
# ---------------------------------------------------------------------------

@router.get("/status")
async def get_agent_status(
    org_id: Optional[str] = Query(None),
):
    """查询代理连接状态 — ONLINE/DEGRADED/OFFLINE。"""
    agent_router = get_router()

    if org_id:
        conns = agent_router.get_all_for_org(org_id)
    else:
        conns = agent_router.get_all_connections()

    status_list = []
    for conn in conns:
        status_list.append({
            "org_id": conn.org_id,
            "datasource": conn.datasource,
            "status": conn.status.value,
            "version": conn.version,
            "ip": conn.ip,
            "last_seen": conn.last_seen.isoformat(),
        })

    return {"code": 0, "data": status_list}


# ---------------------------------------------------------------------------
# 安装包下载（10.3）
# ---------------------------------------------------------------------------

@router.get("/downloads")
async def get_download_url(
    platform: str = Query("linux"),
    db: AsyncSession = Depends(get_db),
):
    """获取最新版本代理安装包下载链接。"""
    stmt = (
        select(AgentVersion)
        .where(AgentVersion.platform == platform)
        .order_by(AgentVersion.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    version = result.scalar_one_or_none()

    if version is None:
        raise HTTPException(status_code=404, detail="No version found for platform")

    return {
        "code": 0,
        "data": {
            "version": version.version,
            "platform": version.platform,
            "download_url": version.download_url,
            "min_version": version.min_version,
        },
    }


# ---------------------------------------------------------------------------
# 审计日志（10.5 / 10.7）
# ---------------------------------------------------------------------------

@router.get("/audit-logs")
async def get_audit_logs(
    org_id: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    """查询审计日志（时间范围过滤，超过 1000 条标注 AUDIT_OVERFLOW）。"""
    stmt = select(AgentAuditLog)

    if org_id:
        stmt = stmt.where(AgentAuditLog.org_id == org_id)
    if start:
        stmt = stmt.where(AgentAuditLog.created_at >= start)
    if end:
        stmt = stmt.where(AgentAuditLog.created_at <= end)

    # 先查总数判断是否 overflow
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(AgentAuditLog.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    logs = list(result.scalars().all())

    data = [
        {
            "id": str(log.id),
            "org_id": str(log.org_id),
            "action": log.action,
            "operator": log.operator,
            "ip": log.ip,
            "detail": log.detail,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]

    return {
        "code": 0,
        "data": data,
        "total": total,
        "overflow": total > 1000,
    }


# ---------------------------------------------------------------------------
# 版本管理（10.6）
# ---------------------------------------------------------------------------

@router.post("/versions")
async def upload_version(
    req: VersionUploadRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    """上传代理版本包。"""
    version = AgentVersion(
        version=req.version,
        platform=req.platform,
        download_url=req.download_url,
        min_version=req.min_version,
    )
    db.add(version)

    await _write_audit_log(
        db, "", "version_uploaded", admin["username"], "0.0.0.0",
        {"version": req.version, "platform": req.platform},
    )

    await db.commit()

    return {"code": 0, "data": {"id": str(version.id), "version": req.version}}


@router.get("/versions")
async def list_versions(
    platform: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取版本列表。"""
    stmt = select(AgentVersion).order_by(AgentVersion.created_at.desc())
    if platform:
        stmt = stmt.where(AgentVersion.platform == platform)

    result = await db.execute(stmt)
    versions = list(result.scalars().all())

    data = [
        {
            "id": str(v.id),
            "version": v.version,
            "platform": v.platform,
            "download_url": v.download_url,
            "min_version": v.min_version,
            "created_at": v.created_at.isoformat(),
        }
        for v in versions
    ]

    return {"code": 0, "data": data}


# ---------------------------------------------------------------------------
# 追踪（全链追踪查询）
# ---------------------------------------------------------------------------

@router.get("/traces")
async def list_traces(
    org_id: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """查询追踪列表。"""
    stmt = select(AgentTrace).order_by(AgentTrace.created_at.desc())
    if org_id:
        stmt = stmt.where(AgentTrace.org_id == org_id)
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    traces = list(result.scalars().all())

    data = [
        {
            "trace_id": t.trace_id,
            "org_id": str(t.org_id),
            "datasource": t.datasource,
            "action": t.action,
            "status": t.status,
            "duration_ms": t.duration_ms,
            "created_at": t.created_at.isoformat(),
        }
        for t in traces
    ]

    return {"code": 0, "data": data}


@router.get("/traces/{trace_id}")
async def get_trace_detail(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
):
    """查询追踪详情（含所有 spans）。"""
    stmt = select(AgentTrace).where(AgentTrace.trace_id == trace_id)
    result = await db.execute(stmt)
    trace = result.scalar_one_or_none()

    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")

    return {
        "code": 0,
        "data": {
            "trace_id": trace.trace_id,
            "org_id": str(trace.org_id),
            "datasource": trace.datasource,
            "action": trace.action,
            "status": trace.status,
            "spans": trace.spans,
            "duration_ms": trace.duration_ms,
            "created_at": trace.created_at.isoformat(),
        },
    }


# ---------------------------------------------------------------------------
# 任务提交（9.1）
# ---------------------------------------------------------------------------

@router.post("/task")
async def submit_task(
    req: TaskSubmitRequest,
    admin: dict = Depends(get_current_admin),
):
    """提交任务到代理。"""
    task_queue = get_task_queue()
    result = await task_queue.submit(
        org_id=req.org_id,
        datasource=req.datasource,
        action=req.action,
        payload=req.payload,
        timeout_ms=req.timeout_ms,
    )

    return {"code": 0, "data": result}
