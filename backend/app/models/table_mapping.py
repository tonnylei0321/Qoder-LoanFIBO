from sqlalchemy import Column, BigInteger, String, Text, Integer, DateTime, Index, ForeignKey
from sqlalchemy.sql import func
from backend.app.database import Base

class TableMapping(Base):
    """Table-level mapping results (table → FIBO class)."""
    
    __tablename__ = "table_mapping"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(BigInteger, ForeignKey("mapping_job.id"), nullable=False)
    database_name = Column(String(128), nullable=False)
    table_name = Column(String(256), nullable=False)
    fibo_class_uri = Column(String(512), nullable=True)
    confidence_level = Column(String(16), nullable=True)
    mapping_reason = Column(Text, nullable=True)
    mapping_status = Column(String(32), nullable=False, default="pending")
    review_status = Column(String(32), nullable=False, default="pending")
    revision_count = Column(Integer, nullable=False, default=0)
    model_used = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    updated_by = Column(String(128), nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    
    __table_args__ = (
        Index('idx_table_mapping_review', 'review_status'),
        Index('idx_table_mapping_confidence', 'confidence_level'),
    )

class FieldMapping(Base):
    """Field-level mapping results (field → FIBO property)."""
    
    __tablename__ = "field_mapping"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    table_mapping_id = Column(BigInteger, ForeignKey("table_mapping.id"), nullable=False)
    field_name = Column(String(256), nullable=False)
    field_type = Column(String(128), nullable=True)
    fibo_property_uri = Column(String(512), nullable=True)
    confidence_level = Column(String(16), nullable=True)
    mapping_reason = Column(Text, nullable=True)
    proj_ext_uri = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    updated_by = Column(String(128), nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
