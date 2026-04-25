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

        支持两种 data 格式：
        1. 结构化格式（Agent 主动封装）：
           {"action": "query_indicator", "company_id": "uuid", "calc_date": "...", "values": [...]}
        2. ERP 原始 SQL 结果：
           {"rows": [{"COL_NAME": "value"}], "status": "ok", ...}
           此时从 IndicatorCollectionPipeline._msg_context_map 回查采集上下文。
        """
        # 方式1：结构化格式
        if data.get("action") == "query_indicator":
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
            source = "agent_structured"
        else:
            # 方式2：ERP 原始结果 → 从上下文映射回查
            rows = data.get("rows", [])
            if not rows or data.get("status") != "ok":
                return

            from backend.app.services.indicator_collection import IndicatorCollectionPipeline
            ctx = IndicatorCollectionPipeline.pop_context(msg_id)
            if not ctx:
                return

            company_id = ctx.get("company_id")
            calc_date_str = ctx.get("calc_date")
            if not company_id or not calc_date_str:
                return

            # 将 ERP 组织编码转换为 fi_applicant_org 的 UUID
            company_uuid = await self._resolve_company_uuid(company_id)
            if not company_uuid:
                from loguru import logger as loguru_logger
                loguru_logger.warning("[双写] 未找到企业UUID: org_id={}", company_id)
                return
            company_id = company_uuid

            try:
                from datetime import date as date_type
                calc_date = date_type.fromisoformat(calc_date_str)
            except (ValueError, TypeError):
                return

            # 从 rows 中提取指标值：row 里的每一列对应一个指标
            # 用 notation 匹配 fi_indicator 表中的指标
            row = rows[0] if rows else {}
            values = await self._convert_rows_to_indicator_values(
                row, ctx, company_id
            )
            if not values:
                return
            source = "agent_raw_sql"

        # 执行双写
        try:
            from backend.app.database import async_session_factory
            from backend.app.services.indicator_history import IndicatorHistoryWriter

            async with async_session_factory() as db:
                writer = IndicatorHistoryWriter(db)
                result = await writer.write_values(
                    company_id=company_id,
                    calc_date=calc_date,
                    values=values,
                    source=source,
                )
                await db.commit()
                logger.info(
                    "指标历史双写完成: org=%s msg_id=%s indicators=%d upserted=%d batch=%s values_count=%d",
                    org_id, msg_id, result["history_count"], result["upserted_count"], result["batch_id"], len(values),
                )
        except Exception as e:
            logger.error("指标历史双写失败: org=%s msg_id=%s err=%s", org_id, msg_id, e)

    async def _resolve_company_uuid(self, org_id: str) -> str | None:
        """将 ERP 组织编码或 UUID 转换为 fi_applicant_org 的 UUID。

        优先匹配: unified_code → name → 直接作为 UUID
        """
        # 如果已经是 UUID 格式
        try:
            from uuid import UUID
            UUID(org_id)
            return org_id
        except ValueError:
            pass

        from backend.app.database import async_session_factory
        from sqlalchemy import select
        from backend.app.models.fi_applicant_org import FiApplicantOrg

        async with async_session_factory() as db:
            # 按 unified_code 查找
            stmt = select(FiApplicantOrg).where(FiApplicantOrg.unified_code == org_id).limit(1)
            result = await db.execute(stmt)
            org = result.scalar_one_or_none()
            if org:
                return str(org.id)

            # 按 name 查找
            stmt2 = select(FiApplicantOrg).where(FiApplicantOrg.name == org_id).limit(1)
            result2 = await db.execute(stmt2)
            org2 = result2.scalar_one_or_none()
            if org2:
                return str(org2.id)

        return None

    async def _convert_rows_to_indicator_values(
        self, row: dict, ctx: dict, company_id: str
    ) -> list[dict]:
        """将 ERP 返回的单行 SQL 结果转换为 fi_indicator_value 格式。

        匹配策略（优先级）：
        1. notation → code（SCF-LOAN-01 → SCF_LOAN_01）
        2. indicator_label → name（中文名称模糊匹配）

        返回: [{"indicator_id": "uuid", "value": 0.0, "data_quality": "P0"}, ...]
        """
        from backend.app.database import async_session_factory
        from sqlalchemy import select, or_
        from backend.app.models.fi_indicator import FiIndicator
        from loguru import logger as loguru_logger

        values = []
        notation = ctx.get("notation", "")
        indicator_label = ctx.get("indicator_label", "")

        # 从 row 中取第一个数值列的值
        numeric_value = None
        for col_name, col_value in row.items():
            try:
                numeric_value = float(col_value) if col_value is not None else None
                break
            except (ValueError, TypeError):
                continue

        async with async_session_factory() as db:
            indicator = None

            # 策略1: notation → code
            if notation:
                indicator_code = notation.replace("-", "_")
                stmt = select(FiIndicator).where(FiIndicator.code == indicator_code).limit(1)
                result = await db.execute(stmt)
                indicator = result.scalar_one_or_none()
                if indicator:
                    loguru_logger.info("[双写] matched by code: notation={} → code={}", notation, indicator_code)

            # 策略2: indicator_label → name 模糊匹配
            if not indicator and indicator_label:
                # 去掉中括号标记（如"【交易规模】月均销售额" → "月均销售额"）
                clean_label = indicator_label
                bracket_pairs = [("【", "】"), ("〔", "〕"), ("[", "]")]
                for open_b, close_b in bracket_pairs:
                    if open_b in clean_label:
                        idx = clean_label.find(open_b)
                        end_idx = clean_label.find(close_b, idx)
                        if end_idx >= 0:
                            clean_label = clean_label[end_idx+1:].strip()
                        break

                if clean_label:
                    stmt2 = select(FiIndicator).where(FiIndicator.name.ilike(f"%{clean_label}%")).limit(1)
                    result2 = await db.execute(stmt2)
                    indicator = result2.scalar_one_or_none()
                    if indicator:
                        loguru_logger.info("[双写] matched by name: label={} → name={}", indicator_label, indicator.name)

            if indicator:
                values.append({
                    "indicator_id": str(indicator.id),
                    "value": numeric_value,
                    "data_quality": "P0",
                })
            else:
                # 策略3: 自动创建 fi_indicator 记录（确保数据不丢）
                indicator_code = notation.replace("-", "_") if notation else f"AUTO_{msg_id[:8]}"
                indicator_name = indicator_label or indicator_code
                # 推断 scenario
                scenario = "pre_loan"
                if notation:
                    if notation.startswith("SCF-"):
                        scenario = "scf"
                    elif notation.startswith("POST-"):
                        scenario = "post_loan"
                # 清理名称中的中括号
                clean_name = indicator_name
                bracket_pairs = [("\u3010", "\u3011"), ("\u3014", "\u3015"), ("[", "]")]
                for open_b, close_b in bracket_pairs:
                    if open_b in clean_name:
                        idx = clean_name.find(open_b)
                        end_idx = clean_name.find(close_b, idx)
                        if end_idx >= 0:
                            clean_name = clean_name[end_idx+1:].strip()
                        break

                try:
                    new_indicator = FiIndicator(
                        code=indicator_code,
                        name=clean_name or indicator_code,
                        scenario=scenario,
                        threshold_direction="above",
                    )
                    db.add(new_indicator)
                    await db.commit()
                    await db.refresh(new_indicator)
                    values.append({
                        "indicator_id": str(new_indicator.id),
                        "value": numeric_value,
                        "data_quality": "P0",
                    })
                    loguru_logger.info(
                        "[双写] auto-created indicator: code={} name={} scenario={} value={}",
                        indicator_code, clean_name, scenario, numeric_value,
                    )
                except Exception as e:
                    await db.rollback()
                    loguru_logger.warning("[双写] auto-create indicator failed: code={} err={}", indicator_code, e)
                    loguru_logger.debug("[双写] 未匹配: notation={} label={} row_keys={}", notation, indicator_label, list(row.keys()))

        loguru_logger.info("[双写] _convert_rows: matched={}/1 notation={} label={}",
                          len(values), notation, indicator_label)
        return values


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
