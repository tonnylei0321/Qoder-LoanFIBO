"""Rule version model for rules engine."""

from datetime import datetime

from sqlalchemy import String, Integer, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class RuleVersion(Base):
    """规则版本表，记录每次编译生成的版本快照。"""

    __tablename__ = "rule_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_count: Mapped[int] = mapped_column(Integer, default=0)
    compile_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    config_snapshot: Mapped[str] = mapped_column(Text, nullable=True)
