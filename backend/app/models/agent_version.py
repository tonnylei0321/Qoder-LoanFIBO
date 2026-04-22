"""代理版本表 — 管理代理安装包版本。"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class AgentVersion(Base):
    """代理版本表，存储SaaS Agent客户端的版本发布与下载信息。"""

    __tablename__ = "agent_version"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version: Mapped[str] = mapped_column(String(32), nullable=False, comment="版本号")
    platform: Mapped[str] = mapped_column(String(16), nullable=False, comment="平台：win/linux")
    download_url: Mapped[str] = mapped_column(String(512), nullable=False, comment="下载链接")
    min_version: Mapped[str] = mapped_column(String(32), default="1.0.0", comment="最低兼容版本")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = ({"comment": "ERP代理版本表"},)
