"""授权项(AuthorizationScope)模型 — PG 主表，同步到 GraphDB。"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class FiAuthorizationScope(Base):
    """授权项表，存储数据访问授权的标准化枚举。"""

    __tablename__ = "fi_authorization_scope"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="授权项编码，如 ERP_AR")
    label: Mapped[str] = mapped_column(String(256), nullable=False, comment="授权项名称，如 授权-ERP应收账款数据")
    category: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="分类: ERP/财务/征信/税务/银行")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="详细说明")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否有效")
    graph_uri: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="GraphDB 中的 URI")
    extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="扩展字段")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
