"""发布版本模型 - 映射数据版本快照管理"""

from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import String, DateTime, Text, JSON, Integer, Boolean
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
    ttl_file_path: Mapped[str] = mapped_column(String(512), nullable=True, comment="TTL文件存储路径")
    ttl_file_name: Mapped[str] = mapped_column(String(256), nullable=True, comment="原始文件名")
    ttl_file_size: Mapped[int] = mapped_column(Integer, nullable=True, comment="文件大小字节")
    ttl_valid: Mapped[bool] = mapped_column(Boolean, nullable=True, comment="TTL语法是否通过")
    ttl_validation_msg: Mapped[str] = mapped_column(Text, nullable=True, comment="检核错误信息")
    class_count: Mapped[int] = mapped_column(Integer, nullable=True, comment="类数量")
    property_count: Mapped[int] = mapped_column(Integer, nullable=True, comment="属性数量")
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
