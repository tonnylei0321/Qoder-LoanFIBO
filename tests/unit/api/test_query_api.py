"""NLQ查询API单元测试

测试Schema验证和路由定义，不依赖完整FastAPI app实例化。
"""
import pytest
from pydantic import ValidationError
from backend.app.schemas.query import QueryRequest, QueryResponse
from backend.app.schemas.rules import RuleCreate, RuleResponse, CompileStatusResponse


class TestQuerySchemas:
    def test_query_request_valid(self):
        req = QueryRequest(tenant_id="t1", query="贷款金额")
        assert req.tenant_id == "t1"
        assert req.query == "贷款金额"
        assert req.context == {}

    def test_query_request_missing_tenant(self):
        with pytest.raises(ValidationError):
            QueryRequest(query="贷款金额")

    def test_query_request_missing_query(self):
        with pytest.raises(ValidationError):
            QueryRequest(tenant_id="t1")

    def test_query_response(self):
        resp = QueryResponse(status="success", data={"key": "val"}, sql="SELECT 1")
        assert resp.status == "success"
        assert resp.sql == "SELECT 1"


class TestRuleSchemas:
    def test_rule_create_valid(self):
        rule = RuleCreate(
            tenant_id="t1", name="Revenue Check",
            rule_type="threshold", definition={"field": "revenue", "op": "gt", "value": 1000000}
        )
        assert rule.tenant_id == "t1"
        assert rule.enabled is True
        assert rule.priority == 0

    def test_rule_create_missing_field(self):
        with pytest.raises(ValidationError):
            RuleCreate(tenant_id="t1", name="test")

    def test_compile_status_response(self):
        resp = CompileStatusResponse(tenant_id="t1", status="ready")
        assert resp.status == "ready"
        assert resp.current_version is None
