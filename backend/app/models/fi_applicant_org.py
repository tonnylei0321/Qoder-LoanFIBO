"""融资企业(ApplicantOrg)模型 — PG 主表，同步到 GraphDB。"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class FiApplicantOrg(Base):
    """融资企业信息表，存储申请贷款的融资企业基本信息。"""

    __tablename__ = "fi_applicant_org"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), nullable=False, comment="企业名称")
    unified_code: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, comment="统一社会信用代码")
    short_name: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="企业简称")
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="行业分类")
    region: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="注册地区")
    legal_person: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="法定代表人")
    registered_capital: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="注册资本")
    contact_info: Mapped[str | None] = mapped_column(Text, nullable=True, comment="联系方式(JSON)")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否有效")
    security_id: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True, index=True, comment="安全ID，线下给企业配置ERP代理")
    graph_uri: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="GraphDB 中的 URI")
    extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="扩展字段")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
