"""Permission model for RBAC."""

from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class Permission(Base):
    """权限表"""

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. 用户管理, 角色管理
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # relationships
    roles: Mapped[list["Role"]] = relationship(  # noqa: F821
        "Role",
        secondary="role_permissions",
        back_populates="permissions",
        lazy="selectin",
    )
