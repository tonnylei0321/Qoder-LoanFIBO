"""Role model for RBAC."""

from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Integer, Table, Column, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base

# M:N association table: role <-> permission
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

# M:N association table: user <-> role (defined here to avoid circular import)
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Role(Base):
    """角色表"""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active / disabled
    menu_codes: Mapped[list | None] = mapped_column(JSON, nullable=True, default=None)  # list of route names
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # relationships
    users: Mapped[list["User"]] = relationship(  # noqa: F821
        "User",
        secondary="user_roles",
        back_populates="roles",
        lazy="selectin",
    )
    permissions: Mapped[list["Permission"]] = relationship(  # noqa: F821
        "Permission",
        secondary=role_permissions,
        back_populates="roles",
        lazy="selectin",
    )
