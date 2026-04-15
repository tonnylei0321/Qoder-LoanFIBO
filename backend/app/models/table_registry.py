from sqlalchemy import Column, BigInteger, String, Text, JSON, Boolean, DateTime, Index
from sqlalchemy.sql import func
from backend.app.database import Base

class TableRegistry(Base):
    """DDL parsing results - one record per source table."""
    
    __tablename__ = "table_registry"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    database_name = Column(String(128), nullable=False)
    table_name = Column(String(256), nullable=False)
    raw_ddl = Column(Text, nullable=False)
    parsed_fields = Column(JSON, nullable=False, default=list)
    mapping_status = Column(String(32), nullable=False, default="pending")
    parse_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
    
    __table_args__ = (
        Index('idx_table_registry_status', 'mapping_status'),
        Index('idx_table_registry_db', 'database_name'),
    )
