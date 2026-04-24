"""Alert record model - stores threshold breach alerts per indicator."""

import uuid
from sqlalchemy import Column, String, Numeric, Date, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from backend.app.database import Base


class FiAlertRecord(Base):
    """预警记录表，存储企业指标触发阈值预警的历史记录。"""

    __tablename__ = "fi_alert_record"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("fi_applicant_org.id"), nullable=False, comment="企业ID")
    indicator_id = Column(UUID(as_uuid=True), ForeignKey("fi_indicator.id"), nullable=False, comment="指标ID")
    alert_level = Column(String(16), nullable=False, comment="预警级别：warning / alert")
    trigger_value = Column(Numeric(20, 6), nullable=True, comment="触发时的指标值")
    threshold_value = Column(Numeric(20, 6), nullable=True, comment="触发的阈值")
    trigger_date = Column(Date, nullable=False, comment="触发日期")
    action_suggestion = Column(String(512), nullable=True, comment="行动建议")
    status = Column(String(16), nullable=False, default="open", comment="处置状态：open / resolved")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_fi_alert_company_date", "company_id", "trigger_date"),
        Index("idx_fi_alert_level", "alert_level"),
        Index("idx_fi_alert_status", "status"),
    )
