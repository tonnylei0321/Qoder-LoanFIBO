from sqlalchemy import Column, BigInteger, String, Text, Integer, Boolean, DateTime, Index
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.sql import func
from backend.app.database import Base


class OntologyClassIndex(Base):
    """FIBO ontology class index (supports both SASAC TTL and FIBO RDF)."""

    __tablename__ = "ontology_class_index"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    class_uri = Column(String(512), nullable=False, unique=True)
    label_zh = Column(String(256), nullable=True)
    label_en = Column(String(256), nullable=True)
    comment_zh = Column(Text, nullable=True)
    comment_en = Column(Text, nullable=True)
    parent_uri = Column(String(512), nullable=True)
    namespace = Column(String(256), nullable=True)
    # Module path derived from FIBO URI, e.g. "FBC/ProductsAndServices/ClientsAndAccounts"
    module_path = Column(String(256), nullable=True)
    search_vector = Column(TSVECTOR, nullable=True)  # Full-text search vector
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index('idx_class_namespace', 'namespace'),
        Index('idx_class_module_path', 'module_path'),
    )


class OntologyPropertyIndex(Base):
    """FIBO ontology property index."""

    __tablename__ = "ontology_property_index"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    property_uri = Column(String(512), nullable=False, unique=True)
    property_type = Column(String(32), nullable=False)  # ObjectProperty / DatatypeProperty
    label_zh = Column(String(256), nullable=True)
    label_en = Column(String(256), nullable=True)
    comment_en = Column(Text, nullable=True)
    domain_uri = Column(String(512), nullable=True)
    range_uri = Column(String(512), nullable=True)
    namespace = Column(String(256), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index('idx_property_domain', 'domain_uri'),
        Index('idx_property_namespace', 'namespace'),
    )


class OntologyRelationIndex(Base):
    """FIBO class hierarchy and equivalence relations."""

    __tablename__ = "ontology_relation_index"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_uri = Column(String(512), nullable=False)   # child / subclass
    target_uri = Column(String(512), nullable=False)   # parent / superclass
    relation_type = Column(String(64), nullable=False)  # subClassOf / equivalentClass
    namespace = Column(String(256), nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index('idx_relation_source', 'source_uri'),
        Index('idx_relation_target', 'target_uri'),
    )


class OntologyIndexMeta(Base):
    """Ontology file index version management (supports incremental/resume)."""

    __tablename__ = "ontology_index_meta"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    file_name = Column(String(256), nullable=False)
    file_md5 = Column(String(64), nullable=False)
    ontology_source = Column(String(64), nullable=False, default='sasac')  # 'sasac' or 'fibo'
    class_count = Column(Integer, nullable=False, default=0)
    property_count = Column(Integer, nullable=False, default=0)
    relation_count = Column(Integer, nullable=False, default=0)
    built_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_active = Column(Boolean, nullable=False, default=True)
