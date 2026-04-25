"""定时指标采集管道 — GraphDB 驱动：从 GraphDB 获取融资企业清单 → 关联实例 → 获取指标SQL → 下发ERP代理。

工作流程：
1. APScheduler 每 20 分钟触发一次采集
2. 从 GraphDB SPARQL 查询融资企业清单
3. 逐个查询企业关联的 ERPInstance → 获取指标SQL列表
4. 将 SQL 中的 :org_id 占位符替换为企业的 ERP 组织编码
5. 通过 WebSocket 将 SQL 发给对应的 ERP 代理
6. 链路离线的记录日志
7. 采集指令记录到全链跟踪
8. 收到 result 后调用 IndicatorHistoryWriter 双写
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from loguru import logger

from backend.app.services.agent.router import AgentRouter, get_router, AgentStatus
from backend.app.services.agent.task_queue import TaskQueue, get_task_queue, TaskStatus
from backend.app.services.agent.tracer import TracerService, get_tracer
from backend.app.services.graphdb_client import GraphDBClient


# 全局采集调度器实例
_collection_scheduler = None


class IndicatorCollectionPipeline:
    """指标采集管道 — GraphDB 驱动：融资企业→实例→指标SQL→ERP代理。

    核心链路：
    ApplicantOrg → linkedToInstance → ERPInstance → CalculationRule → hasSQL → ERP代理
    """

    # 类级别 msg_id→context 映射，供 ws_handler 回查采集上下文
    _msg_context_map: dict[str, dict] = {}

    def __init__(
        self,
        router: AgentRouter | None = None,
        task_queue: TaskQueue | None = None,
        tracer: TracerService | None = None,
        graphdb_client: GraphDBClient | None = None,
    ):
        self._router = router or get_router()
        self._task_queue = task_queue or get_task_queue()
        self._tracer = tracer or get_tracer()
        if graphdb_client is None:
            from backend.app.config import settings
            self._graphdb = GraphDBClient(
                endpoint=settings.GRAPHDB_ENDPOINT,
                repo=settings.GRAPHDB_REPO,
            )
        else:
            self._graphdb = graphdb_client

    @classmethod
    def pop_context(cls, msg_id: str) -> dict | None:
        """取出 msg_id 对应的采集上下文（取出后删除）。"""
        return cls._msg_context_map.pop(msg_id, None)

    async def _fetch_orgs_from_graphdb(self) -> list[dict]:
        """从 GraphDB SPARQL 查询融资企业清单。

        Returns:
            [{"uri": "...", "name": "...", "org_id": "..."}, ...]
        """
        try:
            return await self._graphdb.query_applicant_orgs()
        except Exception as e:
            logger.error(f"GraphDB 查询融资企业清单失败: {e}")
            return []

    async def _fetch_org_indicator_sqls(self, org_uri: str) -> list[dict]:
        """从 GraphDB 查询企业关联的指标SQL列表。

        链路: ApplicantOrg → linkedToInstance → ERPInstance → CalculationRule → hasSQL

        Returns:
            [{"rule_uri": "...", "sql": "...", "erp_agent_datasource": "ncc_erp",
              "org_key_field": "PK_ORG", ...}, ...]
        """
        try:
            return await self._graphdb.query_org_indicator_sqls(org_uri)
        except Exception as e:
            logger.error(f"GraphDB 查询企业指标SQL失败: org_uri={org_uri}, err={e}")
            return []

    @staticmethod
    def _render_sql(sql_template: str, org_key_field: str, org_id: str,
                    start_date: str = "", asof_date: str = "") -> str:
        """将 SQL 模板中的占位符替换为实际值。

        替换规则：
        - :org_id → org_id 值
        - :start_date → 开始日期
        - :asof_date → 截止日期
        """
        sql = sql_template.replace(":org_id", f"'{org_id}'")
        if start_date:
            sql = sql.replace(":start_date", f"'{start_date}'")
        if asof_date:
            sql = sql.replace(":asof_date", f"'{asof_date}'")
        # 移除 SQL 中的注释行（以 -- 开头）
        lines = [line for line in sql.split("\n") if not line.strip().startswith("--")]
        sql = "\n".join(lines).strip()
        # 移除末尾分号（ERP代理可能不需要）
        sql = sql.rstrip(";").strip()
        return sql

    async def collect_all(self) -> dict:
        """GraphDB 驱动的指标采集。

        流程：
        1. 从 GraphDB 获取融资企业清单
        2. 逐个查询企业关联的 ERPInstance → 指标SQL
        3. 将 SQL 中 :org_id 替换为企业的 ERP 组织编码
        4. 通过 WebSocket 发给对应的 ERP 代理
        5. 离线的记录日志
        6. 记录采集轨迹到全链跟踪

        Returns:
            {"dispatched": int, "offline": int, "skipped": int, "graphdb_total": int, "errors": list}
        """
        # 1. 从 GraphDB 获取融资企业清单
        graphdb_orgs = await self._fetch_orgs_from_graphdb()
        graphdb_total = len(graphdb_orgs)

        if not graphdb_orgs:
            logger.warning("GraphDB 中无融资企业记录，跳过本次采集")
            return {
                "dispatched": 0,
                "offline": 0,
                "skipped": 0,
                "graphdb_total": 0,
                "errors": [],
            }

        # 创建采集批次 trace
        batch_trace = self._tracer.create_trace(
            org_id="*",
            datasource="*",
            action="indicator_collection_batch",
            detail={"graphdb_total": graphdb_total},
        )

        dispatched = 0
        offline = 0
        skipped = 0
        errors = []
        today = str(date.today())

        # 2. 逐个企业采集
        for org_info in graphdb_orgs:
            org_id = org_info.get("org_id", "")
            org_name = org_info.get("name", "")
            org_uri = org_info.get("uri", "")

            if not org_id:
                logger.warning(f"GraphDB 企业记录缺少 org_id: {org_info}")
                continue

            # 查询企业关联的指标SQL列表
            indicator_sqls = await self._fetch_org_indicator_sqls(org_uri)

            if not indicator_sqls:
                skipped += 1
                self._tracer.add_span(
                    batch_trace,
                    "collection_scheduler",
                    "org_no_indicators",
                    {"org_id": org_id, "name": org_name, "reason": "未关联ERPInstance或无指标SQL"},
                )
                logger.debug(f"企业 {org_name}({org_id}) 未关联ERPInstance或无指标SQL，跳过")
                continue

            # 获取 ERP 代理 datasource（从第一条规则中获取）
            erp_datasource = indicator_sqls[0].get("erp_agent_datasource", "")
            org_key_field = indicator_sqls[0].get("org_key_field", "PK_ORG")

            if not erp_datasource:
                skipped += 1
                logger.warning(f"企业 {org_name}({org_id}) 的ERPInstance缺少 erpAgentDatasource")
                continue

            # 检查该企业是否有在线的 ERP 代理连接
            org_conns = self._router.get_all_for_org(org_id)
            online_conns = [c for c in org_conns if c.status == AgentStatus.ONLINE]

            # 也尝试通过 datasource 匹配（当 org_id 不匹配时，从所有连接中找对应数据源的在线代理）
            if not online_conns:
                all_conns = self._router.get_all_connections()
                online_conns = [c for c in all_conns
                                if c.datasource == erp_datasource and c.status == AgentStatus.ONLINE]

            if not online_conns:
                offline += 1
                self._tracer.add_span(
                    batch_trace,
                    "collection_scheduler",
                    "org_offline",
                    {"org_id": org_id, "name": org_name, "reason": f"ERP代理 {erp_datasource} 离线"},
                )
                logger.debug(f"企业 {org_name}({org_id}) ERP代理 {erp_datasource} 离线，跳过采集")
                continue

            # 对每条指标SQL，替换占位符后下发给 ERP 代理
            for rule_info in indicator_sqls:
                sql_template = rule_info.get("sql", "")
                if not sql_template:
                    continue

                try:
                    # 替换 SQL 中的占位符
                    rendered_sql = self._render_sql(
                        sql_template,
                        org_key_field=org_key_field,
                        org_id=org_id,
                        start_date=f"{today[:4]}-01-01",  # 年初
                        asof_date=today,
                    )

                    conn = online_conns[0]  # 使用第一个在线连接
                    result = await self._task_queue.submit(
                        org_id=conn.org_id,
                        datasource=conn.datasource,
                        action="query_indicator",
                        payload={"sql": rendered_sql},
                        timeout_ms=60000,
                    )

                    status = result.get("status")
                    if status == TaskStatus.DISPATCHED.value:
                        dispatched += 1
                        # 保存采集上下文，供 result 回来时双写
                        msg_id = result.get("msg_id")
                        if msg_id:
                            self._msg_context_map[msg_id] = {
                                "org_id": org_id,  # ERP组织编码
                                "company_id": org_id,  # 需要在双写时转换为UUID
                                "calc_date": today,
                                "indicator_uri": rule_info.get("indicator_uri", ""),
                                "indicator_label": rule_info.get("indicator_label", ""),
                                "rule_label": rule_info.get("rule_label", ""),
                                "notation": rule_info.get("notation", ""),
                                "scenario_id": rule_info.get("scenario_id", ""),
                            }
                        self._tracer.add_span(
                            batch_trace,
                            "collection_scheduler",
                            "task_dispatched",
                            {
                                "org_id": org_id,
                                "name": org_name,
                                "datasource": conn.datasource,
                                "msg_id": result.get("msg_id"),
                                "rule": rule_info.get("rule_label", ""),
                                "indicator": rule_info.get("indicator_label", ""),
                            },
                        )
                        logger.info(
                            f"指标采集任务已派发: org={org_name}({org_id}) "
                            f"indicator={rule_info.get('indicator_label', '')} "
                            f"ds={conn.datasource} msg_id={result.get('msg_id')}"
                        )
                    elif status == TaskStatus.DATASOURCE_OFFLINE.value:
                        offline += 1
                    else:
                        errors.append({
                            "org_id": org_id,
                            "name": org_name,
                            "datasource": conn.datasource,
                            "status": status,
                            "detail": result.get("detail", ""),
                            "rule": rule_info.get("rule_label", ""),
                        })

                except Exception as e:
                    logger.error(
                        f"指标采集异常: org={org_name}({org_id}) "
                        f"rule={rule_info.get('rule_label', '')} err={e}"
                    )
                    errors.append({
                        "org_id": org_id,
                        "name": org_name,
                        "error": str(e),
                        "rule": rule_info.get("rule_label", ""),
                    })

        # 更新批次 trace 状态
        self._tracer.update_status(batch_trace, TaskStatus.COMPLETED.value)
        await self._tracer.save_to_redis(batch_trace)

        logger.info(
            f"GraphDB驱动指标采集完成: graphdb_total={graphdb_total} "
            f"dispatched={dispatched} offline={offline} skipped={skipped} errors={len(errors)}"
        )
        return {
            "dispatched": dispatched,
            "offline": offline,
            "skipped": skipped,
            "graphdb_total": graphdb_total,
            "errors": errors,
        }

    async def collect_for_org(self, org_id: str, datasource: str,
                               scenario: str | None = None) -> dict:
        """对指定企业发起指标采集（GraphDB驱动）。

        流程：
        1. 从 GraphDB 查找该企业 → 获取关联的 ERPInstance → 获取指标SQL列表
        2. 替换 SQL 占位符 → 通过 WebSocket 下发给 ERP 代理

        Args:
            org_id: 企业ID（支持 GraphDB unified_code、GraphDB URI、PG UUID）
            datasource: ERP代理数据源标识
            scenario: 场景过滤（可选）

        Returns:
            {"dispatched": int, "total_indicators": int, "errors": list}
        """
        # 从 GraphDB 查找该企业的 URI
        # 支持三种传入方式：
        # 1. 直接传 graph_uri（完整 HTTP URI）
        # 2. 传 unified_code（GraphDB Org_ 后的部分）
        # 3. 传 PG-UUID（与 PG 主键一致，目前不支持，需要外部传 unified_code）
        if org_id.startswith("http"):
            # 直接是 GraphDB URI
            org_uri = org_id
            graphdb_org_id = org_uri.split("Org_")[-1] if "Org_" in org_uri else org_id
        else:
            # 尝试匹配
            orgs = await self._fetch_orgs_from_graphdb()
            org_uri = ""
            graphdb_org_id = ""
            for org in orgs:
                if org.get("org_id") == org_id or org.get("uri") == org_id:
                    org_uri = org.get("uri", "")
                    graphdb_org_id = org.get("org_id", "")
                    break

            if not org_uri:
                return {
                    "status": "ERROR",
                    "detail": f"企业 {org_id} 在 GraphDB 中未找到（支持传入 unified_code 或完整 GraphDB URI）",
                    "total_indicators": 0,
                }

        # 查询企业关联的指标SQL
        indicator_sqls = await self._fetch_org_indicator_sqls(org_uri)
        if not indicator_sqls:
            return {
                "status": "ERROR",
                "detail": f"企业 {org_id} 未关联ERPInstance或无指标SQL",
                "total_indicators": 0,
            }

        # 按场景过滤
        if scenario:
            indicator_sqls = [r for r in indicator_sqls if r.get("scenario_id") == scenario]

        # 检查代理在线（优先用 graphdb_org_id 匹配，其次全局 datasource 匹配）
        conn = self._router.get_connection(graphdb_org_id, datasource)
        if conn is None or conn.status != AgentStatus.ONLINE:
            # 尝试通过 datasource 查找任意在线连接
            all_conns = self._router.get_all_for_org("*")
            for c in all_conns:
                if c.datasource == datasource and c.status == AgentStatus.ONLINE:
                    conn = c
                    break

        if conn is None or conn.status != AgentStatus.ONLINE:
            return {
                "status": TaskStatus.DATASOURCE_OFFLINE.value,
                "detail": f"ERP代理 {datasource} 离线",
            }

        org_key_field = indicator_sqls[0].get("org_key_field", "PK_ORG")
        today = str(date.today())
        dispatched = 0
        errors = []

        for rule_info in indicator_sqls:
            sql_template = rule_info.get("sql", "")
            if not sql_template:
                continue

            try:
                rendered_sql = self._render_sql(
                    sql_template,
                    org_key_field=org_key_field,
                    org_id=graphdb_org_id,  # 使用 GraphDB unified_code 替换 :org_id 占位符
                    start_date=f"{today[:4]}-01-01",
                    asof_date=today,
                )

                result = await self._task_queue.submit(
                    org_id=conn.org_id,
                    datasource=conn.datasource,
                    action="query_indicator",
                    payload={"sql": rendered_sql},
                    timeout_ms=60000,
                )

                status = result.get("status")
                if status == TaskStatus.DISPATCHED.value:
                    dispatched += 1
                    logger.info(
                        f"指标采集: org={org_id}(graphdb={graphdb_org_id}) "
                        f"indicator={rule_info.get('indicator_label', '')} "
                        f"msg_id={result.get('msg_id')}"
                    )
                else:
                    errors.append({
                        "rule": rule_info.get("rule_label", ""),
                        "status": status,
                        "detail": result.get("detail", ""),
                    })

            except Exception as e:
                errors.append({
                    "rule": rule_info.get("rule_label", ""),
                    "error": str(e),
                })

        return {
            "status": "OK",
            "dispatched": dispatched,
            "total_indicators": len(indicator_sqls),
            "errors": errors,
        }


def start_collection_scheduler():
    """启动指标采集定时调度（APScheduler）。"""
    global _collection_scheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        logger.warning("APScheduler not installed, indicator collection scheduler disabled")
        return

    if _collection_scheduler is not None:
        return

    pipeline = IndicatorCollectionPipeline()

    async def _collect_job():
        """定时采集任务。"""
        try:
            result = await pipeline.collect_all()
            logger.info(f"定时指标采集: {result}")
        except Exception as e:
            logger.error(f"定时指标采集异常: {e}")

    _collection_scheduler = AsyncIOScheduler()
    # 每 20 分钟采集一次
    _collection_scheduler.add_job(
        _collect_job,
        IntervalTrigger(minutes=20),
        id="indicator_collection",
        replace_existing=True,
    )
    _collection_scheduler.start()
    logger.info("Indicator collection scheduler started: every 20 minutes")


def stop_collection_scheduler():
    """停止指标采集定时调度。"""
    global _collection_scheduler
    if _collection_scheduler is not None:
        _collection_scheduler.shutdown(wait=False)
        _collection_scheduler = None
        logger.info("Indicator collection scheduler stopped")
