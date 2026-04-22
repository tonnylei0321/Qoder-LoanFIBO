"""代理凭证表 — 存储 ERP Agent 的 client_id/client_secret。"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class AgentCredential(Base):
    """代理凭证表，存储SaaS Agent的client_id/secret认证信息。"""

    __tablename__ = "agent_credential"

    client_id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="客户端ID")
    client_secret_hash: Mapped[str] = mapped_column(String(128), nullable=False, comment="bcrypt哈希")
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fi_applicant_org.id"), nullable=False, comment="关联企业"
    )
    datasource: Mapped[str] = mapped_column(String(64), nullable=False, comment="数据源标识(如NCC)")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="吊销时间，NULL=有效"
    )

    __table_args__ = (
        Index("idx_credential_org_datasource", "org_id", "datasource"),
        {"comment": "ERP代理凭证表"},
    )
