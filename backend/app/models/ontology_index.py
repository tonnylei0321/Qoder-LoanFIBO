from sqlalchemy import Column, BigInteger, String, Text, Integer, Boolean, DateTime, Index
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.sql import func
from backend.app.database import Base

class OntologyClassIndex(Base):
    """TTL ontology class index."""
    
    __tablename__ = "ontology_class_index"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    class_uri = Column(String(512), nullable=False, unique=True)
    label_zh = Column(String(256), nullable=True)
    label_en = Column(String(256), nullable=True)
    comment_zh = Column(Text, nullable=True)
    comment_en = Column(Text, nullable=True)
    parent_uri = Column(String(512), nullable=True)
    namespace = Column(String(256), nullable=True)
    search_vector = Column(TSVECTOR, nullable=True)  # Full-text search vector
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
    
    __table_args__ = (
        Index('idx_class_namespace', 'namespace'),
    )

class OntologyPropertyIndex(Base):
    """TTL ontology property index."""
    
    __tablename__ = "ontology_property_index"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    property_uri = Column(String(512), nullable=False, unique=True)
    property_type = Column(String(32), nullable=False)
    label_zh = Column(String(256), nullable=True)
    label_en = Column(String(256), nullable=True)
    domain_uri = Column(String(512), nullable=True)
    range_uri = Column(String(512), nullable=True)
    namespace = Column(String(256), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
    
    __table_args__ = (
        Index('idx_property_domain', 'domain_uri'),
    )

class OntologyIndexMeta(Base):
    """TTL index version management."""
    
    __tablename__ = "ontology_index_meta"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    file_name = Column(String(256), nullable=False)
    file_md5 = Column(String(64), nullable=False)
    class_count = Column(Integer, nullable=False, default=0)
    property_count = Column(Integer, nullable=False, default=0)
    built_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_active = Column(Boolean, nullable=False, default=True)
