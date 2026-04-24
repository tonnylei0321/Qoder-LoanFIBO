"""外键推断模型 - LLM 辅助外键关系发现"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Float, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class TableForeignKey(Base):
    """外键推断结果表"""

    __tablename__ = "table_foreign_keys"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"fk_{uuid.uuid4().hex[:12]}"
    )
    source_table: Mapped[str] = mapped_column(String(256), nullable=False)
    source_column: Mapped[str] = mapped_column(String(256), nullable=False)
    target_table: Mapped[str] = mapped_column(String(256), nullable=False)
    target_column: Mapped[str] = mapped_column(String(256), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/approved/rejected
    inferred_by: Mapped[str] = mapped_column(String(16), default="llm")  # llm/manual
    inference_reason: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
