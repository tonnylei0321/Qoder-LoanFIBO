"""User model with RBAC support."""

from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base
from backend.app.models.role import user_roles


class User(Base):
    """用户表"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active / disabled
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # relationships
    roles: Mapped[list["Role"]] = relationship(  # noqa: F821
        "Role",
        secondary=user_roles,
        back_populates="users",
        lazy="selectin",
    )

    @property
    def permissions(self) -> set[str]:
        """Return all permission codes from all assigned roles."""
        codes: set[str] = set()
        for role in self.roles:
            for perm in role.permissions:
                codes.add(perm.code)
        return codes

    def has_permission(self, code: str) -> bool:
        """Check if user has a specific permission through any role."""
        return code in self.permissions

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return any(r.code == "admin" for r in self.roles)
