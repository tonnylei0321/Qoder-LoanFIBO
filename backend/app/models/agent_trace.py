"""全链追踪表 — PG 持久化 Trace 数据。"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class AgentTrace(Base):
    """全链追踪表，存储Agent请求的trace_id、span信息及执行耗时。"""

    __tablename__ = "agent_trace"

    trace_id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="追踪ID")
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fi_applicant_org.id"), nullable=False, comment="关联企业"
    )
    datasource: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="数据源标识")
    action: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="操作类型")
    status: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="执行状态")
    spans: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="Span列表(JSON+GIN索引)")
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="执行耗时(毫秒)")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_trace_org_created", "org_id", "created_at"),
        Index("idx_trace_spans", "spans", postgresql_using="gin"),
        {"comment": "全链追踪持久化表"},
    )
