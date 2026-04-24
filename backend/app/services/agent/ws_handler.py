"""WebSocket 连接处理器 — 管理代理连接生命周期。

生命周期：
1. Authorization: Bearer Header 认证（优先，若 Header 中携带 token）
   或 auth 消息认证（client_id + client_secret）
   或 auth_token 消息认证（OAuth2 access_token）
2. register 消息（5 秒超时未收到则断开）
3. 消息循环（heartbeat/ack/result/error）
4. 断开连接时清理路由表
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from backend.app.services.agent.credential import CredentialService
from backend.app.services.agent.router import AgentConn, AgentRouter, get_router
from backend.app.services.agent.task_queue import TaskQueue, get_task_queue
from backend.app.services.agent.tracer import TracerService, get_tracer

logger = logging.getLogger(__name__)

# register 超时
REGISTER_TIMEOUT_SEC = 5


class AgentWSHandler:
    """WebSocket 连接处理器。"""

    def __init__(
        self,
        credential_service: CredentialService | None = None,
        router: AgentRouter | None = None,
        task_queue: TaskQueue | None = None,
        tracer: TracerService | None = None,
    ):
        self._cred_service = credential_service
        self._router = router or get_router()
        self._task_queue = task_queue or get_task_queue()
        self._tracer = tracer or get_tracer()

    async def handle_auth(
        self, ws: WebSocket, auth_msg: dict, db_session=None
    ) -> AgentCredential | None:
        """处理 auth 消息。

        Args:
            ws: WebSocket 连接
            auth_msg: {"type": "auth", "client_id": "...", "client_secret": "..."}
            db_session: 数据库会话

        Returns:
            认证成功返回 AgentCredential 对象，失败返回 None。
        """
        client_id = auth_msg.get("client_id", "")
        client_secret = auth_msg.get("client_secret", "")

        if not client_id or not client_secret:
            await ws.send_json({
                "type": "auth_error",
                "message": "missing client_id or client_secret",
            })
            return None

        if db_session is None:
            # 无 DB 会话，无法验证
            await ws.send_json({
                "type": "auth_error",
                "message": "internal error: no db session",
            })
            return None

        cred = await self._cred_service.verify(db_session, client_id, client_secret)
        if cred is None:
            await ws.send_json({
                "type": "auth_error",
                "message": "invalid credentials",
            })
            return None

        await ws.send_json({
            "msg_id": auth_msg.get("msg_id", ""),
            "type": "auth_ok",
            "tenant_id": "default",
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "payload": {
                "client_id": client_id,
                "status": "ok",
            },
        })
        return cred

    async def handle_auth_token(
        self, ws: WebSocket, auth_msg: dict, db_session=None
    ) -> AgentCredential | None:
        """处理 auth_token 消息 — 使用 OAuth2 access_token 认证。

        Args:
            ws: WebSocket 连接
            auth_msg: {"type": "auth_token", "access_token": "..."}
            db_session: 数据库会话

        Returns:
            认证成功返回 AgentCredential 对象，失败返回 None。
        """
        from backend.app.services.auth import decode_token

        access_token = auth_msg.get("access_token", "")
        if not access_token:
            await ws.send_json({
                "type": "auth_error",
                "message": "missing access_token",
            })
            return None

        # 解码 JWT
        payload = decode_token(access_token)
        if payload is None:
            await ws.send_json({
                "type": "auth_error",
                "message": "invalid or expired access_token",
            })
            return None

        # 校验 sub == erp-agent
        if payload.get("sub") != "erp-agent":
            await ws.send_json({
                "type": "auth_error",
                "message": "invalid token subject",
            })
            return None

        client_id = payload.get("client_id", "")
        if not client_id or db_session is None:
            await ws.send_json({
                "type": "auth_error",
                "message": "internal error: missing client_id or db session",
            })
            return None

        # 查询凭证（确保未被吊销）
        from sqlalchemy import select
        from backend.app.models.agent_credential import AgentCredential
        stmt = select(AgentCredential).where(AgentCredential.client_id == client_id)
        result = await db_session.execute(stmt)
        cred = result.scalar_one_or_none()

        if cred is None or cred.revoked_at is not None:
            await ws.send_json({
                "type": "auth_error",
                "message": "credential revoked or not found",
            })
            return None

        await ws.send_json({
            "msg_id": auth_msg.get("msg_id", ""),
            "type": "auth_ok",
            "tenant_id": "default",
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "payload": {
                "client_id": client_id,
                "status": "ok",
            },
        })
        return cred

    async def handle_connection(self, ws: WebSocket, db_session=None, client_ip: str = "", header_token: str | None = None) -> None:
        """处理完整的 WebSocket 连接生命周期。

        流程：
        1. 如果 header_token 存在 → 验证 JWT Bearer token 认证（优先）
           否则 → auth / auth_token 消息认证（备选）
        2. register → 注册到路由表（5 秒超时）
        3. 消息循环 → heartbeat/ack/result/error
        4. finally → 清理路由表
        """
        org_id = None
        datasource = None

        try:
            # Phase 1: 认证
            if header_token:
                # 方式一（优先）：从 HTTP Authorization Header 提取的 Bearer token
                cred = await self.handle_auth_token(
                    ws, {"type": "auth_token", "access_token": header_token}, db_session,
                )
                if cred is None:
                    await ws.close(code=4001, reason="auth failed (bearer header)")
                    return
            else:
                # 方式二/三：等待首条 auth/auth_token 消息
                raw = await asyncio.wait_for(ws.receive_text(), timeout=REGISTER_TIMEOUT_SEC)
                auth_msg = json.loads(raw)

                msg_type = auth_msg.get("type", "")
                if msg_type == "auth":
                    # 方式二：client_id + client_secret 直接认证
                    cred = await self.handle_auth(ws, auth_msg, db_session)
                elif msg_type == "auth_token":
                    # 方式三：OAuth2 access_token 消息认证
                    cred = await self.handle_auth_token(ws, auth_msg, db_session)
                else:
                    await ws.send_json({
                        "type": "auth_error",
                        "message": "first message must be auth or auth_token",
                    })
                    await ws.close(code=4001, reason="auth required")
                    return

                if cred is None:
                    await ws.close(code=4001, reason="auth failed")
                    return

            # 从凭证中提取 org_id 和 datasource（安全：不信任客户端）
            org_id = str(cred.org_id)
            datasource = cred.datasource

            # Phase 2: 等待 register 消息（5 秒超时）
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=REGISTER_TIMEOUT_SEC)
            except asyncio.TimeoutError:
                await ws.send_json({
                    "type": "error",
                    "message": "register timeout (5s)",
                })
                await ws.close(code=4002, reason="register timeout")
                return

            register_msg = json.loads(raw)
            if register_msg.get("type") != "register":
                await ws.send_json({
                    "type": "error",
                    "message": "expected register message",
                })
                await ws.close(code=4002, reason="register required")
                return

            # 注册到路由表
            agent_version = register_msg.get("version", "unknown")
            conn = AgentConn(
                ws=ws,
                org_id=org_id,
                datasource=datasource,
                version=agent_version,
                ip=client_ip,
            )

            old_conn = self._router.add_connection(conn)
            if old_conn is not None:
                try:
                    await old_conn.ws.close(code=4003, reason="replaced by new connection")
                except Exception:
                    pass

            await ws.send_json({
                "msg_id": register_msg.get("msg_id", ""),
                "type": "register_ack",
                "tenant_id": "default",
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                "payload": {
                    "msg_id": register_msg.get("msg_id", ""),
                    "status": "ok",
                    "server_time": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "min_version": "1.0.0",
                },
            })

            logger.info(
                "代理已注册: org=%s ds=%s version=%s ip=%s",
                org_id, datasource, agent_version, client_ip,
            )

            # Phase 3: 消息循环
            while True:
                try:
                    raw = await ws.receive_text()
                except Exception:
                    break

                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await ws.send_json({"type": "error", "message": "invalid json"})
                    continue

                msg_type = msg.get("type", "")

                if msg_type == "heartbeat":
                    self._router.update_last_seen(org_id, datasource)
                    await ws.send_json({
                        "msg_id": msg.get("msg_id", ""),
                        "type": "heartbeat_ack",
                        "tenant_id": "default",
                        "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                        "payload": {
                            "status": "ok",
                        },
                    })

                elif msg_type == "ack":
                    msg_id = msg.get("msg_id", "")
                    self._task_queue.handle_ack(msg_id)

                elif msg_type == "result":
                    msg_id = msg.get("msg_id", "")
                    # 兼容标准信封格式(payload)和扁平格式(data)
                    data = msg.get("payload") or msg.get("data", {})
                    if isinstance(data, dict) and "data" in data and "action" not in data:
                        data = data["data"]
                    await self._task_queue.handle_result(msg_id, data)
                    # 对 query_indicator 结果做历史双写
                    await self._write_indicator_history_if_needed(msg_id, data, org_id)

                elif msg_type == "error":
                    msg_id = msg.get("msg_id", "")
                    # 兼容标准信封格式(payload)和扁平格式(error)
                    payload = msg.get("payload") or {}
                    error = payload.get("error") or msg.get("error", "unknown error")
                    await self._task_queue.handle_error(msg_id, error)

                else:
                    await ws.send_json({
                        "type": "error",
                        "message": f"unknown message type: {msg_type}",
                    })

        except asyncio.TimeoutError:
            logger.warning("WebSocket 连接超时: org=%s", org_id)
        except WebSocketDisconnect:
            logger.info("WebSocket 断开: org=%s ds=%s", org_id, datasource)
        except Exception as e:
            logger.error("WebSocket 处理异常: %s", e)
        finally:
            # Phase 4: 清理路由表
            if org_id and datasource:
                self._router.remove_connection(org_id, datasource)
                logger.info("路由表已清理: org=%s ds=%s", org_id, datasource)

    async def _write_indicator_history_if_needed(
        self, msg_id: str, data: dict, org_id: str
    ) -> None:
        """对 query_indicator 结果执行历史双写。

        期望 Agent 返回的 data 格式：
        {
            "action": "query_indicator",
            "company_id": "uuid",
            "calc_date": "2026-04-20",
            "values": [
                {"indicator_id": "uuid", "value": 123.45, "value_prev": 100.0, "data_quality": "P0"},
                ...
            ]
        }
        """
        if data.get("action") != "query_indicator":
            return

        values = data.get("values", [])
        if not values:
            return

        company_id = data.get("company_id")
        calc_date_str = data.get("calc_date")

        if not company_id or not calc_date_str:
            logger.warning("query_indicator result 缺少 company_id 或 calc_date: msg_id=%s", msg_id)
            return

        try:
            from datetime import date as date_type
            calc_date = date_type.fromisoformat(calc_date_str)
        except (ValueError, TypeError):
            logger.warning("query_indicator result calc_date 格式错误: %s", calc_date_str)
            return

        try:
            from backend.app.database import async_session_factory
            from backend.app.services.indicator_history import IndicatorHistoryWriter

            async with async_session_factory() as db:
                writer = IndicatorHistoryWriter(db)
                result = await writer.write_values(
                    company_id=company_id,
                    calc_date=calc_date,
                    values=values,
                    source="agent",
                )
                await db.commit()
                logger.info(
                    "指标历史双写完成: org=%s msg_id=%s indicators=%d upserted=%d batch=%s values_count=%d",
                    org_id, msg_id, result["history_count"], result["upserted_count"], result["batch_id"], len(values),
                )
        except Exception as e:
            logger.error("指标历史双写失败: org=%s msg_id=%s err=%s", org_id, msg_id, e)


# 全局单例
_ws_handler: AgentWSHandler | None = None


def init_ws_handler(
    credential_service: CredentialService | None = None,
    router: AgentRouter | None = None,
    task_queue: TaskQueue | None = None,
    tracer: TracerService | None = None,
) -> AgentWSHandler:
    global _ws_handler
    _ws_handler = AgentWSHandler(
        credential_service=credential_service,
        router=router,
        task_queue=task_queue,
        tracer=tracer,
    )
    return _ws_handler


def get_ws_handler() -> AgentWSHandler:
    global _ws_handler
    if _ws_handler is None:
        _ws_handler = AgentWSHandler()
    return _ws_handler


# 为了类型标注
try:
    from backend.app.models.agent_credential import AgentCredential
except ImportError:
    AgentCredential = None
