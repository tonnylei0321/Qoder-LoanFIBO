"""同步任务模型"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class SyncTask(Base):
    """同步任务表"""

    __tablename__ = "sync_tasks"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"sync_{uuid.uuid4().hex[:12]}"
    )
    version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    instance_id: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), default="upsert")  # upsert/replace
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/running/completed/failed
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    triples_synced: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
