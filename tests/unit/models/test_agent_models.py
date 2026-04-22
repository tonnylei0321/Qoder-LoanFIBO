"""Agent models unit tests — 验证4张表的字段定义和索引。"""

import uuid

from backend.app.models.agent_credential import AgentCredential
from backend.app.models.agent_version import AgentVersion
from backend.app.models.agent_audit_log import AgentAuditLog
from backend.app.models.agent_trace import AgentTrace


class TestAgentCredential:
    def test_tablename(self):
        assert AgentCredential.__tablename__ == "agent_credential"

    def test_create_with_valid_data(self):
        cred = AgentCredential(
            client_id="ag_test123",
            client_secret_hash="$2b$12$hashed",
            org_id=uuid.uuid4(),
            datasource="NCC",
        )
        assert cred.client_id == "ag_test123"
        assert cred.revoked_at is None

    def test_client_id_is_primary_key(self):
        assert AgentCredential.__table__.c.client_id.primary_key is True

    def test_org_id_has_foreign_key(self):
        fk = list(AgentCredential.__table__.c.org_id.foreign_keys)[0]
        assert "fi_applicant_org" in str(fk.target_fullname)

    def test_index_credential_org_datasource(self):
        index_names = [idx.name for idx in AgentCredential.__table__.indexes]
        assert "idx_credential_org_datasource" in index_names


class TestAgentVersion:
    def test_tablename(self):
        assert AgentVersion.__tablename__ == "agent_version"

    def test_create_with_valid_data(self):
        ver = AgentVersion(version="1.0.0", platform="linux", download_url="http://example.com/agent")
        assert ver.version == "1.0.0"

    def test_min_version_column_default(self):
        """min_version 列级默认值应为 '1.0.0'（INSERT时生效）。"""
        assert AgentVersion.__table__.c.min_version.default.arg == "1.0.0"

    def test_id_is_uuid_primary_key(self):
        assert AgentVersion.__table__.c.id.primary_key is True


class TestAgentAuditLog:
    def test_tablename(self):
        assert AgentAuditLog.__tablename__ == "agent_audit_log"

    def test_operator_not_nullable(self):
        assert AgentAuditLog.__table__.c.operator.nullable is False

    def test_org_id_has_foreign_key(self):
        fk = list(AgentAuditLog.__table__.c.org_id.foreign_keys)[0]
        assert "fi_applicant_org" in str(fk.target_fullname)

    def test_index_audit_org_created(self):
        index_names = [idx.name for idx in AgentAuditLog.__table__.indexes]
        assert "idx_audit_org_created" in index_names


class TestAgentTrace:
    def test_tablename(self):
        assert AgentTrace.__tablename__ == "agent_trace"

    def test_trace_id_is_primary_key(self):
        assert AgentTrace.__table__.c.trace_id.primary_key is True

    def test_org_id_has_foreign_key(self):
        fk = list(AgentTrace.__table__.c.org_id.foreign_keys)[0]
        assert "fi_applicant_org" in str(fk.target_fullname)

    def test_index_trace_org_created(self):
        index_names = [idx.name for idx in AgentTrace.__table__.indexes]
        assert "idx_trace_org_created" in index_names

    def test_index_trace_spans_gin(self):
        """验证 spans 列有 GIN 索引。"""
        spans_idx = next(idx for idx in AgentTrace.__table__.indexes if idx.name == "idx_trace_spans")
        dialect_kwargs = spans_idx.dialect_options.get("postgresql", {})
        assert dialect_kwargs.get("using", "").lower() == "gin"
