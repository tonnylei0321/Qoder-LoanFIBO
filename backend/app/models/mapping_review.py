from sqlalchemy import Column, BigInteger, String, Text, Integer, Boolean, DateTime, JSON, Index, ForeignKey
from sqlalchemy.sql import func
from backend.app.database import Base

class MappingReview(Base):
    """Review comments for mapping records."""
    
    __tablename__ = "mapping_review"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    table_mapping_id = Column(BigInteger, ForeignKey("table_mapping.id"), nullable=False)
    field_mapping_id = Column(BigInteger, ForeignKey("field_mapping.id"), nullable=True)
    review_round = Column(Integer, nullable=False, default=0)
    issue_type = Column(String(32), nullable=False)
    severity = Column(String(4), nullable=False)
    is_must_fix = Column(Boolean, nullable=False, default=False)
    issue_description = Column(Text, nullable=False)
    suggested_fix = Column(Text, nullable=True)
    is_resolved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
    
    __table_args__ = (
        Index('idx_review_table_mapping', 'table_mapping_id'),
        Index('idx_review_severity', 'severity'),
    )

class MappingRevisionLog(Base):
    """Revision history for mapping changes."""
    
    __tablename__ = "mapping_revision_log"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    table_mapping_id = Column(BigInteger, ForeignKey("table_mapping.id"), nullable=False)
    revision_round = Column(Integer, nullable=False)
    model_used = Column(String(64), nullable=True)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    prev_fibo_class_uri = Column(String(512), nullable=True)
    prev_confidence = Column(String(16), nullable=True)
    new_fibo_class_uri = Column(String(512), nullable=True)
    new_confidence = Column(String(16), nullable=True)
    field_changes = Column(JSON, nullable=True)
    resolved_review_ids = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    __table_args__ = (
        Index('idx_revision_log_table', 'table_mapping_id'),
    )

class LLMCallLog(Base):
    """LLM call logs for cost analysis and monitoring."""
    
    __tablename__ = "llm_call_log"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(BigInteger, ForeignKey("mapping_job.id"), nullable=True)
    table_mapping_id = Column(BigInteger, ForeignKey("table_mapping.id"), nullable=True)
    call_type = Column(String(32), nullable=False)
    model_name = Column(String(64), nullable=False)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Integer, nullable=False, default=0)
    is_fallback = Column(Boolean, nullable=False, default=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
