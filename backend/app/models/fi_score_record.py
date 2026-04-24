"""Score record model - stores comprehensive scoring results per company."""

import uuid
from sqlalchemy import Column, String, Numeric, Date, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from backend.app.database import Base


class FiScoreRecord(Base):
    """综合评分记录表，存储企业按场景的多维度加权评分结果。"""

    __tablename__ = "fi_score_record"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("fi_applicant_org.id"), nullable=False, comment="企业ID")
    scenario = Column(String(16), nullable=False, comment="场景：pre_loan / post_loan / scf")
    total_score = Column(Numeric(5, 2), nullable=True, comment="综合评分（0-100）")
    risk_level = Column(String(16), nullable=True,
                         comment="风险等级：AAA / AA / A / BBB / BB / B / CCC")
    dimension_scores = Column(JSONB, nullable=False, server_default="{}",
                               comment="各维度得分，如 {liquidity: {score: 68.0, weight: 0.25}}")
    suggestion = Column(Text, nullable=True, comment="授信建议/行动建议文本")
    calc_date = Column(Date, nullable=False, comment="评分计算日期")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_fi_score_record_company_scenario", "company_id", "scenario"),
        Index("idx_fi_score_record_date", "calc_date"),
        Index("idx_fi_score_record_risk_level", "risk_level"),
    )
