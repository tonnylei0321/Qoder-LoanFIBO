"""Agent 管理 REST API + WebSocket + SSE 端点。

端点列表：
- POST /agent/oauth2/token   — OAuth2 client_credentials 模式获取 access_token
- WS:  /agent/connect          — ERP 代理接入（支持 auth/auth_token 两种认证）
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


def _mask_security_id(sid: str) -> str:
    """掩码展示安全ID：保留前8位+后4位，中间用****替换。"""
    if not sid or len(sid) <= 12:
        return sid or ''
    return sid[:8] + '****' + sid[-4:]


def _extract_bearer_from_headers(websocket: WebSocket) -> str | None:
    """从 WebSocket HTTP 握手 Header 提取 Bearer token。

    支持 RFC 6455 标准的 Sec-WebSocket-Protocol 子协议传递 token，
    也支持标准 Authorization Header（部分客户端/代理支持）。

    Args:
        websocket: FastAPI WebSocket 对象

    Returns:
        Bearer token 字符串，未找到返回 None
    """
    # 方式1: 标准 Authorization Header（浏览器 WebSocket API 不支持自定义 Header，
    # 但后端代理/Python 客户端可以）
    auth = websocket.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return token

    # 方式2: Sec-WebSocket-Protocol 子协议传递
    # 客户端发起: new WebSocket(url, ['access_token', token_value])
    # 服务端提取: sec-websocket-protocol 头
    protocols = websocket.headers.get("sec-websocket-protocol", "")
    parts = [p.strip() for p in protocols.split(",")]
    if len(parts) >= 2 and parts[0] == "access_token":
        token = parts[1].strip()
        if token:
            return token

    return None


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


class OAuth2TokenRequest(BaseModel):
    """RFC 6749 client_credentials 模式请求体。"""
    grant_type: str = "client_credentials"
    client_id: str
    client_secret: str
    scope: str = ""


# ---------------------------------------------------------------------------
# OAuth2 Token 端点（ERP 代理获取 access_token）
# ---------------------------------------------------------------------------

@router.post("/oauth2/token")
async def oauth2_token(req: OAuth2TokenRequest, db: AsyncSession = Depends(get_db)):
    """OAuth2 client_credentials 模式 — ERP 代理通过 client_id + client_secret 换取 access_token。

    流程：
    1. ERP 代理使用 agent_credential 中的 client_id + client_secret 请求 token
    2. 服务端验证凭证，签发短期 JWT (access_token)
    3. ERP 代理携带 access_token 连接 WebSocket

    请求示例（application/x-www-form-urlencoded 或 JSON）：
        grant_type=client_credentials&client_id=cid_xxx&client_secret=sk_xxx

    响应：
        {"access_token": "eyJ...", "token_type": "Bearer", "expires_in": 7200}
    """
    if req.grant_type != "client_credentials":
        raise HTTPException(status_code=400, detail="unsupported_grant_type")

    # 验证凭证
    cred = await credential_service.verify(db, req.client_id, req.client_secret)
    if cred is None:
        raise HTTPException(status_code=401, detail="invalid_client")

    # 签发 JWT access_token
    from backend.app.services.auth import create_token
    access_token = create_token(
        payload={
            "client_id": cred.client_id,
            "org_id": str(cred.org_id),
            "datasource": cred.datasource,
            "sub": "erp-agent",
        },
        expires_sec=7200,
    )

    # 审计日志
    await _write_audit_log(
        db, str(cred.org_id), "token_issued", cred.client_id, "0.0.0.0",
        {"grant_type": "client_credentials"},
    )
    await db.commit()

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 7200,
    }


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
    2. 支持 Authorization: Bearer {token} Header 认证（优先）
    3. 首条消息 auth/auth_token 认证（备选）
    4. register 5秒超时断开
    """
    # IP 速率限制
    client_ip = websocket.client.host if websocket.client else "unknown"
    limiter = get_ws_rate_limiter()
    if not limiter.is_allowed(client_ip):
        await websocket.close(code=429, reason="rate limit exceeded")
        return

    # 尝试从 Authorization Header 提取 Bearer token
    header_token = _extract_bearer_from_headers(websocket)

    await websocket.accept()

    # 获取 DB session
    from backend.app.database import async_session_factory
    async with async_session_factory() as db:
        try:
            handler = get_ws_handler()
            await handler.handle_connection(
                websocket, db_session=db, client_ip=client_ip,
                header_token=header_token,
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
# 企业列表（10.0）
# ---------------------------------------------------------------------------

@router.get("/orgs")
async def list_orgs(
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """查询企业列表（含每个企业的凭证数量和最新凭证信息）。"""
    from sqlalchemy.orm import selectinload

    # 查企业
    stmt = select(FiApplicantOrg).order_by(FiApplicantOrg.created_at.desc())
    count_stmt = select(func.count()).select_from(FiApplicantOrg)

    if search:
        stmt = stmt.where(FiApplicantOrg.name.ilike(f"%{search}%"))
        count_stmt = count_stmt.where(FiApplicantOrg.name.ilike(f"%{search}%"))

    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    orgs = list(result.scalars().all())

    # 查每个企业的凭证
    data = []
    for org in orgs:
        creds = await credential_service.get_by_org(db, str(org.id))
        data.append({
            "org_id": str(org.id),
            "name": org.name,
            "industry": org.industry,
            "datasource": creds[0].datasource if creds else "NCC",
            "security_id_masked": _mask_security_id(org.security_id) if org.security_id else None,
            "credential_count": len(creds),
            "active_credential_count": sum(1 for c in creds if c.revoked_at is None),
            "created_at": org.created_at.isoformat() if org.created_at else None,
        })

    return {"code": 0, "data": data, "total": total}


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
    # 自动生成安全ID
    import secrets
    org.security_id = f"sid_{secrets.token_hex(16)}"
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
            "security_id": org.security_id,
            "credential": cred_result,
        },
    }


# ---------------------------------------------------------------------------
# 凭证管理（10.2）
# ---------------------------------------------------------------------------

@router.get("/orgs/{org_id}/credentials")
async def list_credentials(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    """查询企业下所有凭证（client_secret 不返回，仅显示状态）。"""
    creds = await credential_service.get_by_org(db, org_id)
    data = [
        {
            "client_id": c.client_id,
            "datasource": c.datasource,
            "revoked": c.revoked_at is not None,
            "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in creds
    ]
    return {"code": 0, "data": data}


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


# ---------------------------------------------------------------------------
# 指标采集触发（手动/定时）
# ---------------------------------------------------------------------------

class CollectRequest(BaseModel):
    org_id: str
    datasource: str = "NCC"


@router.post("/collect")
async def trigger_collection(
    req: CollectRequest | None = None,
    admin: dict = Depends(get_current_admin),
):
    """手动触发指标采集（指定企业或全部在线代理）。"""
    from backend.app.services.indicator_collection import IndicatorCollectionPipeline
    pipeline = IndicatorCollectionPipeline()

    if req and req.org_id:
        result = await pipeline.collect_for_org(req.org_id, req.datasource)
    else:
        result = await pipeline.collect_all()

    return {"code": 0, "data": result}

