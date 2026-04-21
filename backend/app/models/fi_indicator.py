"""Indicator definition model for loan analysis."""

import uuid
from sqlalchemy import Column, String, Numeric, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from backend.app.database import Base


class FiIndicator(Base):
    """指标定义表，存储各场景的金融指标元数据，与FIBO Pipeline解耦。"""

    __tablename__ = "fi_indicator"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(64), unique=True, nullable=False, comment="指标编码（唯一）")
    name = Column(String(128), nullable=False, comment="指标名称（中文）")
    fibo_path = Column(String(512), nullable=True, comment="FIBO本体路径（展示用）")
    formula = Column(Text, nullable=True, comment="计算公式描述")
    data_source = Column(Text, nullable=True, comment="数据来源说明")
    unit = Column(String(32), nullable=True, comment="单位，如 %、倍、万元")
    dimension_id = Column(UUID(as_uuid=True), ForeignKey("fi_dimension.id"), nullable=True, comment="所属维度")
    scenario = Column(String(16), nullable=False, comment="适用场景：pre_loan / post_loan / scf")
    weight = Column(Numeric(5, 4), nullable=True, comment="维度内权重")
    threshold_warning = Column(Numeric(20, 6), nullable=True, comment="关注阈值")
    threshold_alert = Column(Numeric(20, 6), nullable=True, comment="预警阈值")
    threshold_direction = Column(String(8), nullable=False, default="above",
                                  comment="阈值方向：above=高于阈值为好，below=低于阈值为好")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_fi_indicator_scenario", "scenario"),
        Index("idx_fi_indicator_dimension", "dimension_id"),
        Index("idx_fi_indicator_code", "code"),
    )
