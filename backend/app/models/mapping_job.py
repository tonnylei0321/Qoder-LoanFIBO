from sqlalchemy import Column, BigInteger, String, JSON, Integer, DateTime, Boolean, Index
from sqlalchemy.sql import func
from backend.app.database import Base

class MappingJob(Base):
    """Pipeline task management."""
    
    __tablename__ = "mapping_job"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_name = Column(String(256), nullable=True)
    scope_databases = Column(JSON, nullable=True)
    status = Column(String(32), nullable=False, default="pending")
    phase = Column(String(32), nullable=False, default="parse_ddl")
    total_tables = Column(Integer, nullable=False, default=0)
    processed_tables = Column(Integer, nullable=False, default=0)
    mapped_count = Column(Integer, nullable=False, default=0)
    unmappable_count = Column(Integer, nullable=False, default=0)
    approved_count = Column(Integer, nullable=False, default=0)
    needs_revision_count = Column(Integer, nullable=False, default=0)
    manual_review_count = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    report = Column(JSON, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
