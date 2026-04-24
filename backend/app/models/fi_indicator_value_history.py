"""指标值历史表 — 时序追加，支持趋势分析。

与 fi_indicator_value（最新快照）互补：
- fi_indicator_value: upsert 语义，只保留最新值，给前端展示用
- fi_indicator_value_history: insert-only，每次采集追加一条，给趋势分析用

采集时双写：先 INSERT history，再 UPSERT value。
"""

import uuid
from sqlalchemy import Column, String, Numeric, Date, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from backend.app.database import Base


class FiIndicatorValueHistory(Base):
    """指标值历史表 — 每次采集追加一条记录，不做 upsert。"""

    __tablename__ = "fi_indicator_value_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("fi_applicant_org.id"), nullable=False, comment="企业ID")
    indicator_id = Column(UUID(as_uuid=True), ForeignKey("fi_indicator.id"), nullable=False, comment="指标ID")
    value = Column(Numeric(20, 6), nullable=True, comment="采集值")
    value_prev = Column(Numeric(20, 6), nullable=True, comment="上期值")
    change_pct = Column(Numeric(10, 4), nullable=True, comment="环比变化率（%）")
    alert_level = Column(String(16), nullable=False, default="normal",
                          comment="预警级别：normal / warning / alert")
    data_quality = Column(String(4), nullable=True, comment="数据质量等级：P0/P1/P2")
    calc_date = Column(Date, nullable=False, comment="计算日期")
    # 采集元数据
    source = Column(String(32), nullable=True, comment="数据来源：agent/manual/import")
    batch_id = Column(UUID(as_uuid=True), nullable=True, comment="采集批次ID（同一次定时任务共享）")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_fi_indicator_value_history_company_date", "company_id", "calc_date"),
        Index("idx_fi_indicator_value_history_indicator_date", "indicator_id", "calc_date"),
        Index("idx_fi_indicator_value_history_batch", "batch_id"),
    )
