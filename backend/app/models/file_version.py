"""File Version Models for DDL and TTL file management."""

from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text, Index
from sqlalchemy.sql import func
from backend.app.database import Base


class DDLFileVersion(Base):
    """DDL file versions uploaded by users."""
    
    __tablename__ = "ddl_file_version"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    file_name = Column(String(256), nullable=False)
    source_tag = Column(String(128), nullable=False, comment="e.g., BIPV5-财务域-v1.2")
    erp_source = Column(String(64), nullable=False, comment="e.g., BIPV5, SAP")
    version = Column(String(32), nullable=False, comment="e.g., v1.2")
    file_size = Column(BigInteger, nullable=False, default=0)
    file_path = Column(String(512), nullable=False)
    parse_status = Column(String(32), nullable=False, default="pending")
    table_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by = Column(String(128), nullable=True)
    
    __table_args__ = (
        Index('idx_ddl_source_tag', 'source_tag'),
        Index('idx_ddl_erp_source', 'erp_source'),
        Index('idx_ddl_parse_status', 'parse_status'),
    )


class TTLFileVersion(Base):
    """TTL file versions uploaded by users."""
    
    __tablename__ = "ttl_file_version"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    file_name = Column(String(256), nullable=False)
    ontology_tag = Column(String(128), nullable=False, comment="e.g., FIBO-v4.4")
    ontology_type = Column(String(64), nullable=False, comment="e.g., FIBO, SASAC")
    version = Column(String(32), nullable=False, comment="e.g., v4.4")
    file_size = Column(BigInteger, nullable=False, default=0)
    file_path = Column(String(512), nullable=False)
    index_status = Column(String(32), nullable=False, default="pending")
    class_count = Column(Integer, nullable=True)
    property_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by = Column(String(128), nullable=True)
    
    __table_args__ = (
        Index('idx_ttl_ontology_tag', 'ontology_tag'),
        Index('idx_ttl_ontology_type', 'ontology_type'),
        Index('idx_ttl_index_status', 'index_status'),
    )
