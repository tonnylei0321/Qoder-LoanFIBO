"""发布版本模型 - 映射数据版本快照管理"""

from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import String, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class VersionStatus(str, PyEnum):
    """版本状态枚举"""
    DRAFT = "draft"
    PUBLISHED = "published"
    SYNCED = "synced"
    FAILED = "failed"


class PublishVersion(Base):
    """发布版本表，存储映射数据的版本快照。"""

    __tablename__ = "publish_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version_tag: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=VersionStatus.DRAFT.value)
    snapshot_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
