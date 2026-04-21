"""Compile status model for rules engine."""

from datetime import datetime

from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class CompileStatus(Base):
    """编译状态表，跟踪每个租户的规则编译状态。"""

    __tablename__ = "compile_status"

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ready")
    current_version: Mapped[str] = mapped_column(String(32), nullable=True)
    last_compiled_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(String(1024), nullable=True)
    staleness_seconds: Mapped[int] = mapped_column(Integer, default=0)
