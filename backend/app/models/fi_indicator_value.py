"""Indicator value model - stores calculated indicator results per company."""

import uuid
from sqlalchemy import Column, String, Numeric, Date, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from backend.app.database import Base


class FiIndicatorValue(Base):
    """指标值表，存储企业在某一日期的各指标计算结果。"""

    __tablename__ = "fi_indicator_value"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("fi_company.id"), nullable=False, comment="企业ID")
    indicator_id = Column(UUID(as_uuid=True), ForeignKey("fi_indicator.id"), nullable=False, comment="指标ID")
    value = Column(Numeric(20, 6), nullable=True, comment="当前值")
    value_prev = Column(Numeric(20, 6), nullable=True, comment="上期值（用于环比计算）")
    change_pct = Column(Numeric(10, 4), nullable=True, comment="环比变化率（%）")
    alert_level = Column(String(16), nullable=False, default="normal",
                          comment="预警级别：normal / warning / alert")
    data_quality = Column(String(4), nullable=True, comment="数据质量等级：P0/P1/P2")
    calc_date = Column(Date, nullable=False, comment="计算日期")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("company_id", "indicator_id", "calc_date", name="uq_fi_indicator_value"),
        Index("idx_fi_indicator_value_company_date", "company_id", "calc_date"),
        Index("idx_fi_indicator_value_alert", "alert_level"),
    )
