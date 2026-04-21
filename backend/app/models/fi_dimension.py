"""Dimension model for loan analysis scoring."""

import uuid
from sqlalchemy import Column, String, Numeric, Integer, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from backend.app.database import Base


class FiDimension(Base):
    """指标维度表，定义贷前/贷后/供应链金融各维度及其权重。"""

    __tablename__ = "fi_dimension"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(64), unique=True, nullable=False, comment="维度编码，如 liquidity / profitability")
    name = Column(String(128), nullable=False, comment="维度名称（中文）")
    weight = Column(Numeric(5, 4), nullable=False, comment="维度权重，如 0.2500 表示 25%")
    scenario = Column(String(16), nullable=False, comment="适用场景：pre_loan / post_loan / scf")
    sort_order = Column(Integer, nullable=False, default=0, comment="排序序号")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_fi_dimension_scenario", "scenario"),
        Index("idx_fi_dimension_code", "code"),
    )
