"""WebSocket 连接处理器 — 管理代理连接生命周期。

生命周期：
1. auth 消息认证（client_id + client_secret）
2. register 消息（5 秒超时未收到则断开）
3. 消息循环（heartbeat/ack/result/error）
4. 断开连接时清理路由表
"""

from __future__ import annotations

import asyncio
import json
import logging
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
            "type": "auth_ok",
            "client_id": client_id,
        })
        return cred

    async def handle_connection(self, ws: WebSocket, db_session=None, client_ip: str = "") -> None:
        """处理完整的 WebSocket 连接生命周期。

        流程：
        1. auth → 验证凭证
        2. register → 注册到路由表（5 秒超时）
        3. 消息循环 → heartbeat/ack/result/error
        4. finally → 清理路由表
        """
        org_id = None
        datasource = None

        try:
            # Phase 1: 等待 auth 消息
            raw = await asyncio.wait_for(ws.receive_text(), timeout=REGISTER_TIMEOUT_SEC)
            auth_msg = json.loads(raw)

            if auth_msg.get("type") != "auth":
                await ws.send_json({
                    "type": "auth_error",
                    "message": "first message must be auth",
                })
                await ws.close(code=4001, reason="auth required")
                return

            cred = await self.handle_auth(ws, auth_msg, db_session)
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
                "type": "register_ack",
                "org_id": org_id,
                "datasource": datasource,
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
                    await ws.send_json({"type": "heartbeat_ack"})

                elif msg_type == "ack":
                    msg_id = msg.get("msg_id", "")
                    self._task_queue.handle_ack(msg_id)

                elif msg_type == "result":
                    msg_id = msg.get("msg_id", "")
                    data = msg.get("data", {})
                    await self._task_queue.handle_result(msg_id, data)

                elif msg_type == "error":
                    msg_id = msg.get("msg_id", "")
                    error = msg.get("error", "unknown error")
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
