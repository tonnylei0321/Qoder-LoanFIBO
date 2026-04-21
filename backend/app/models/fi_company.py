"""Enterprise (Company) model for loan analysis."""

import uuid
from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from backend.app.database import Base


class FiCompany(Base):
    """企业信息表，存储信贷分析对象的基本信息。"""

    __tablename__ = "fi_company"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(256), nullable=False, comment="企业名称")
    unified_code = Column(String(64), unique=True, nullable=True, comment="统一社会信用代码")
    industry = Column(String(128), nullable=True, comment="行业分类")
    region = Column(String(128), nullable=True, comment="地区")
    reg_tags = Column(JSONB, nullable=False, server_default="{}", comment="监管属性标签（五篇大文章）")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_fi_company_name", "name"),
        Index("idx_fi_company_industry", "industry"),
    )
