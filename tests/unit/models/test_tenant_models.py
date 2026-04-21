"""Unit tests for tenant-related models (GraphDB Rules Engine v2)."""
import sys
import types
import pytest
from datetime import datetime
from unittest.mock import MagicMock

# Pop conftest mocks to allow real SQLAlchemy imports
_sqla_keys = [k for k in list(sys.modules.keys()) if k.startswith("sqlalchemy")]
for k in _sqla_keys:
    del sys.modules[k]

for mod in [
    "backend.app.database",
    "backend.app.models.tenant",
    "backend.app.models.tenant_config",
    "backend.app.models.compile_status",
    "backend.app.models.rule_version",
    "backend.app.models.l2_rule",
]:
    sys.modules.pop(mod, None)

if "asyncpg" not in sys.modules:
    sys.modules["asyncpg"] = MagicMock()

# Set up lightweight database module with real Base
from sqlalchemy.orm import DeclarativeBase


class _TestBase(DeclarativeBase):
    pass


_db_module = types.ModuleType("backend.app.database")
_db_module.Base = _TestBase
_db_module.async_session_factory = None
_db_module.engine = None
sys.modules["backend.app.database"] = _db_module

from backend.app.models.tenant import Tenant
from backend.app.models.tenant_config import TenantConfig
from backend.app.models.compile_status import CompileStatus
from backend.app.models.rule_version import RuleVersion
from backend.app.models.l2_rule import L2Rule


class TestTenant:
    def test_tablename(self):
        assert Tenant.__tablename__ == "tenants"

    def test_create_with_valid_data(self):
        t = Tenant(id="t1", name="Acme Corp", industry="manufacturing", tier="tier1")
        assert t.id == "t1"
        assert t.name == "Acme Corp"
        assert t.industry == "manufacturing"
        assert t.tier == "tier1"

    def test_default_status(self):
        assert Tenant.__table__.c.status.default.arg == "active"

    def test_created_at_has_default(self):
        assert Tenant.__table__.c.created_at.default is not None


class TestTenantConfig:
    def test_tablename(self):
        assert TenantConfig.__tablename__ == "tenant_configs"

    def test_create_with_valid_data(self):
        tc = TenantConfig(tenant_id="t1", db_schema="public")
        assert tc.tenant_id == "t1"
        assert tc.db_schema == "public"

    def test_default_compile_priority(self):
        assert TenantConfig.__table__.c.compile_priority.default.arg == 5

    def test_default_nlq_enabled(self):
        assert TenantConfig.__table__.c.nlq_enabled.default.arg is True


class TestCompileStatus:
    def test_tablename(self):
        assert CompileStatus.__tablename__ == "compile_status"

    def test_default_status(self):
        assert CompileStatus.__table__.c.status.default.arg == "ready"

    def test_valid_states(self):
        valid_states = ["ready", "compiling", "L0_CRITICAL", "L0_HIGH_COMPILING",
                        "L0_CRITICAL_FAILED", "STALE", "failed"]
        for state in valid_states:
            cs = CompileStatus(tenant_id="t1", status=state)
            assert cs.status == state


class TestRuleVersion:
    def test_tablename(self):
        assert RuleVersion.__tablename__ == "rule_versions"

    def test_create_with_valid_data(self):
        rv = RuleVersion(tenant_id="t1", version="v1.0", rule_count=50, compile_time_ms=1200)
        assert rv.tenant_id == "t1"
        assert rv.version == "v1.0"
        assert rv.rule_count == 50

    def test_tenant_id_indexed(self):
        assert RuleVersion.__table__.c.tenant_id.index is True


class TestL2Rule:
    def test_tablename(self):
        assert L2Rule.__tablename__ == "l2_rules"

    def test_create_with_valid_data(self):
        rule = L2Rule(
            id="r1", tenant_id="t1", name="Revenue Check",
            rule_type="threshold",
            definition={"field": "revenue", "op": "gt", "value": 1000000},
        )
        assert rule.id == "r1"
        assert rule.tenant_id == "t1"
        assert rule.rule_type == "threshold"

    def test_default_enabled(self):
        assert L2Rule.__table__.c.enabled.default.arg is True

    def test_tenant_id_indexed(self):
        assert L2Rule.__table__.c.tenant_id.index is True
