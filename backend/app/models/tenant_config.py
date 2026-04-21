"""Tenant configuration model for rules engine."""

from sqlalchemy import String, Integer, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class TenantConfig(Base):
    """租户配置表，存储每个租户的编译参数和自定义设置。"""

    __tablename__ = "tenant_configs"

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    db_schema: Mapped[str] = mapped_column(String(64), nullable=False)
    compile_priority: Mapped[int] = mapped_column(Integer, default=5)
    max_rules: Mapped[int] = mapped_column(Integer, default=100)
    nlq_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    custom_settings: Mapped[str] = mapped_column(Text, nullable=True)
