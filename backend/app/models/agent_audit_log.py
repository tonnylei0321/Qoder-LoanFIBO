"""审计日志表 — 记录管理操作。"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class AgentAuditLog(Base):
    """代理审计日志表，记录Agent服务的关键操作（凭证创建/吊销、版本变更等）。"""

    __tablename__ = "agent_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fi_applicant_org.id"), nullable=False, comment="关联企业"
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False, comment="操作类型")
    operator: Mapped[str] = mapped_column(String(128), nullable=False, comment="操作人（从JWT提取）")
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="操作IP")
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="操作详情")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_audit_org_created", "org_id", "created_at"),
        {"comment": "代理管理审计日志表"},
    )
