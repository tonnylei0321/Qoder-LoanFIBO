"""GraphDB 实例模型 - 多 GraphDB 实例注册管理"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class GraphDBInstance(Base):
    """GraphDB 实例表，存储已注册的 GraphDB 实例信息。"""

    __tablename__ = "graphdb_instances"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"inst_{uuid.uuid4().hex[:12]}"
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    server_url: Mapped[str] = mapped_column(String(512), nullable=False)
    repo_id: Mapped[str] = mapped_column(String(128), nullable=False)
    domain: Mapped[str] = mapped_column(String(128), nullable=True)
    namespace_prefix: Mapped[str] = mapped_column(String(64), default="loanfibo")
    version_id: Mapped[str] = mapped_column(String(64), nullable=True, comment="绑定的版本ID")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
