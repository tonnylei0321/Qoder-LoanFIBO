"""单元测试 — 指标采集管道 IndicatorCollectionPipeline（GraphDB 驱动链路）。

链路: ApplicantOrg → linkedToInstance → ERPInstance → CalculationRule → hasSQL → ERP代理
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.services.indicator_collection import IndicatorCollectionPipeline
from backend.app.services.agent.router import AgentRouter, AgentConn, AgentStatus
from backend.app.services.agent.task_queue import TaskQueue, TaskStatus
from backend.app.services.graphdb_client import GraphDBClient


# --- 测试用 mock 数据 ---

MOCK_ORG_URI = "http://yql.example.com/ontology/applicant-org/Org_test001"
MOCK_INSTANCE_URI = "http://yql.example.com/ontology/erp-instance/NCC_Instance"

MOCK_ORG_LIST = [
    {"uri": MOCK_ORG_URI, "name": "测试企业", "org_id": "test001"},
]

MOCK_INSTANCE_INFO = {
    "instance_uri": MOCK_INSTANCE_URI,
    "instance_code": "NCC",
    "instance_name": "用友NCC",
    "erp_agent_datasource": "ncc_erp",
    "org_key_field": "PK_ORG",
}

MOCK_INDICATOR_SQLS = [
    {
        "rule_uri": "http://yql.example.com/ontology/calculation-rule/Rule_TEST_01",
        "rule_label": "【测试】坏账发生额(计算规则)",
        "indicator_uri": "http://yql.example.com/ontology/credit-risk/BadDebtLossAmount",
        "indicator_label": "【测试】坏账发生额",
        "sql": "SELECT NVL(SUM(LOSSLOCALMONEY), 0) AS bad_debt_loss_amount\nFROM ARAP_BDLOSS\nWHERE PK_ORG = :org_id",
        "scenario_uri": "http://yql.example.com/ontology/scenario/PostLoanMonitoring",
        "scenario_id": "PostLoanMonitoring",
        "formula": "SUM(坏账损失金额)",
        "notation": "POST-AR-03",
        "erp_agent_datasource": "ncc_erp",
        "org_key_field": "PK_ORG",
        "instance_code": "NCC",
        "instance_uri": MOCK_INSTANCE_URI,
    },
]


@pytest.fixture
def router():
    return AgentRouter(redis_client=None)


@pytest.fixture
def mock_task_queue():
    tq = MagicMock(spec=TaskQueue)
    tq.submit = AsyncMock()
    return tq


@pytest.fixture
def mock_graphdb():
    gdb = MagicMock(spec=GraphDBClient)
    gdb.query_applicant_orgs = AsyncMock(return_value=MOCK_ORG_LIST)
    gdb.query_org_linked_instance = AsyncMock(return_value=MOCK_INSTANCE_INFO)
    gdb.query_instance_indicator_sqls = AsyncMock(return_value=MOCK_INDICATOR_SQLS)
    gdb.query_org_indicator_sqls = AsyncMock(return_value=MOCK_INDICATOR_SQLS)
    return gdb


@pytest.fixture
def pipeline(router, mock_task_queue, mock_graphdb):
    return IndicatorCollectionPipeline(
        router=router, task_queue=mock_task_queue, graphdb_client=mock_graphdb
    )


def _make_conn(org_id="test001", datasource="ncc_erp", status=AgentStatus.ONLINE):
    ws = AsyncMock()
    return AgentConn(
        ws=ws, org_id=org_id, datasource=datasource,
        version="1.0.0", ip="127.0.0.1", status=status,
    )


class TestCollectAll:
    """collect_all 测试（GraphDB 驱动链路）。"""

    @pytest.mark.asyncio
    async def test_no_orgs_returns_zeros(self, pipeline, mock_graphdb):
        """GraphDB 无企业记录时应返回全零。"""
        mock_graphdb.query_applicant_orgs = AsyncMock(return_value=[])
        result = await pipeline.collect_all()
        assert result["dispatched"] == 0
        assert result["offline"] == 0
        assert result["skipped"] == 0
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_org_no_instance_skipped(self, pipeline, mock_graphdb):
        """企业未关联 ERPInstance 时应计为 skipped。"""
        mock_graphdb.query_org_indicator_sqls = AsyncMock(return_value=[])
        result = await pipeline.collect_all()
        assert result["dispatched"] == 0
        assert result["skipped"] == 1

    @pytest.mark.asyncio
    async def test_online_connection_dispatched(self, pipeline, router, mock_task_queue):
        """在线连接应派发采集任务。"""
        conn = _make_conn()
        router.add_connection(conn)

        mock_task_queue.submit.return_value = {
            "status": TaskStatus.DISPATCHED.value,
            "msg_id": "msg_test",
        }

        result = await pipeline.collect_all()
        assert result["dispatched"] == 1
        assert result["offline"] == 0
        mock_task_queue.submit.assert_called_once()

    @pytest.mark.asyncio
    async def test_offline_connection_counted_as_offline(self, pipeline, router, mock_graphdb):
        """OFFLINE 状态的连接应计为 offline。"""
        conn = _make_conn(status=AgentStatus.OFFLINE)
        router.add_connection(conn)

        result = await pipeline.collect_all()
        assert result["dispatched"] == 0
        assert result["offline"] == 1


class TestCollectForOrg:
    """collect_for_org 测试（GraphDB 驱动链路）。"""

    @pytest.mark.asyncio
    async def test_org_not_found_in_graphdb(self, pipeline, mock_graphdb):
        """企业在 GraphDB 中未找到应返回 ERROR。"""
        mock_graphdb.query_applicant_orgs = AsyncMock(return_value=[])
        result = await pipeline.collect_for_org("unknown", "ncc_erp")
        assert result["status"] == "ERROR"

    @pytest.mark.asyncio
    async def test_org_no_instance_returns_error(self, pipeline, mock_graphdb):
        """企业未关联 ERPInstance 应返回 ERROR。"""
        mock_graphdb.query_org_indicator_sqls = AsyncMock(return_value=[])
        result = await pipeline.collect_for_org("test001", "ncc_erp")
        assert result["status"] == "ERROR"
        assert result["total_indicators"] == 0

    @pytest.mark.asyncio
    async def test_offline_agent_returns_offline_status(self, pipeline, mock_graphdb):
        """ERP代理离线应返回 DATASOURCE_OFFLINE。"""
        result = await pipeline.collect_for_org("test001", "ncc_erp")
        assert result["status"] == TaskStatus.DATASOURCE_OFFLINE.value

    @pytest.mark.asyncio
    async def test_online_agent_dispatches_task(self, pipeline, router, mock_task_queue, mock_graphdb):
        """在线 ERP 代理应派发采集任务。"""
        conn = _make_conn()
        router.add_connection(conn)

        mock_task_queue.submit.return_value = {
            "status": TaskStatus.DISPATCHED.value,
            "msg_id": "msg_test",
        }

        result = await pipeline.collect_for_org("test001", "ncc_erp")
        assert result["status"] == "OK"
        assert result["dispatched"] == 1
        mock_task_queue.submit.assert_called_once()

    @pytest.mark.asyncio
    async def test_sql_rendered_with_graphdb_org_id(self, pipeline, router, mock_task_queue, mock_graphdb):
        """传入 PG UUID 时，SQL 中应使用 GraphDB unified_code 而非 PG UUID。

        局景：传入的 org_id='test001'，GraphDB 匹配后 unified_code 也是 'test001'。
        验证 SQL payload 包含 'test001'，而不是占位符 :org_id。
        """
        conn = _make_conn()
        router.add_connection(conn)

        mock_task_queue.submit.return_value = {
            "status": TaskStatus.DISPATCHED.value,
            "msg_id": "msg_test2",
        }

        result = await pipeline.collect_for_org("test001", "ncc_erp")
        assert result["status"] == "OK"
        assert result["dispatched"] == 1

        # 验证 SQL 中的 :org_id 占位符已被替换为 unified_code
        call_args = mock_task_queue.submit.call_args
        rendered_sql = call_args.kwargs["payload"]["sql"]
        assert ":org_id" not in rendered_sql, "SQL 占位符应已替换"
        assert "'test001'" in rendered_sql, "应包含 graphdb unified_code"

    @pytest.mark.asyncio
    async def test_graphdb_uri_as_org_id(self, pipeline, router, mock_task_queue, mock_graphdb):
        """直接传入 GraphDB URI 应能正常欧采集。"""
        conn = _make_conn()
        router.add_connection(conn)

        mock_task_queue.submit.return_value = {
            "status": TaskStatus.DISPATCHED.value,
            "msg_id": "msg_uri_test",
        }

        # 传入完整 GraphDB URI
        result = await pipeline.collect_for_org(MOCK_ORG_URI, "ncc_erp")
        assert result["status"] == "OK"
        assert result["dispatched"] == 1

        # SQL 中应包含从 URI 提取的 org_id
        call_args = mock_task_queue.submit.call_args
        rendered_sql = call_args.kwargs["payload"]["sql"]
        assert ":org_id" not in rendered_sql, "SQL 占位符应已替换"
        assert "'test001'" in rendered_sql, "应包含从 URI 提取的 unified_code"


class TestRenderSQL:
    """_render_sql 渲染测试。"""

    def test_replace_org_id(self):
        """替换 :org_id 占位符。"""
        sql = "SELECT * FROM T WHERE PK_ORG = :org_id"
        result = IndicatorCollectionPipeline._render_sql(sql, "PK_ORG", "TEST001")
        assert "'TEST001'" in result
        assert ":org_id" not in result

    def test_replace_dates(self):
        """替换 :start_date 和 :asof_date 占位符。"""
        sql = "WHERE DATE BETWEEN :start_date AND :asof_date"
        result = IndicatorCollectionPipeline._render_sql(
            sql, "PK_ORG", "ORG1",
            start_date="2026-01-01", asof_date="2026-04-20",
        )
        assert "'2026-01-01'" in result
        assert "'2026-04-20'" in result

    def test_remove_comments(self):
        """移除 SQL 注释。"""
        sql = "-- This is a comment\nSELECT * FROM T\n-- Another comment"
        result = IndicatorCollectionPipeline._render_sql(sql, "PK_ORG", "ORG1")
        assert "--" not in result
        assert result.startswith("SELECT")

    def test_remove_trailing_semicolon(self):
        """移除末尾分号。"""
        sql = "SELECT * FROM T WHERE PK_ORG = :org_id;"
        result = IndicatorCollectionPipeline._render_sql(sql, "PK_ORG", "ORG1")
        assert not result.endswith(";")
