"""FIBO Indexer - Parse FIBO 2025Q4 RDF files and build structured PostgreSQL index.

Processes all .rdf files under docs/fibo-master_2025Q4 in module order:
  FND → FBC → LOAN → SEC → DER → IND → MD → CAE → BP → ACTUS

Extracts:
  - owl:Class          → ontology_class_index
  - owl:ObjectProperty / owl:DatatypeProperty  → ontology_property_index
  - rdfs:subClassOf / owl:equivalentClass      → ontology_relation_index

Supports incremental indexing (skips already-indexed files by MD5).
"""

import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from loguru import logger
from rdflib import Graph, Namespace, OWL, RDF, RDFS
from rdflib.term import URIRef
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import async_session_factory
from backend.app.models.ontology_index import (
    OntologyClassIndex,
    OntologyIndexMeta,
    OntologyPropertyIndex,
    OntologyRelationIndex,
)
from backend.app.services.pipeline_state import PipelineState

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FIBO_BASE = "https://spec.edmcouncil.org/fibo/"
CMNS_BASE = "https://www.omg.org/spec/Commons/"

# Modules to process in order (relative to fibo-master_2025Q4/)
MODULE_ORDER = ["FND", "FBC", "LOAN", "SEC", "DER", "IND", "MD", "CAE", "BP", "ACTUS"]

# Skip files that contain only individuals or catalog metadata
SKIP_FILENAME_PATTERNS = [
    re.compile(r"Individuals", re.IGNORECASE),
    re.compile(r"Metadata", re.IGNORECASE),
    re.compile(r"^All[A-Z]"),
    re.compile(r"catalog-v001"),
    re.compile(r"ISO4217"),  # 210KB currency codes - skip for speed
]

# ---------------------------------------------------------------------------
# SPARQL queries (executed per-file against local rdflib Graph)
# ---------------------------------------------------------------------------

_SPARQL_CLASSES = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX cmns-av: <https://www.omg.org/spec/Commons/AnnotationVocabulary/>

SELECT DISTINCT ?class ?label_en ?comment_en ?parent
WHERE {
  ?class a owl:Class .
  OPTIONAL { ?class rdfs:label   ?label_en   . FILTER(LANG(?label_en)   = "en") }
  OPTIONAL {
    ?class rdfs:comment ?comment_en . FILTER(LANG(?comment_en) = "en")
  }
  OPTIONAL { ?class rdfs:subClassOf ?parent . }
}
"""

_SPARQL_PROPERTIES = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?prop ?type ?label_en ?comment_en ?domain ?range
WHERE {
  ?prop a ?type .
  FILTER(?type IN (owl:ObjectProperty, owl:DatatypeProperty))
  OPTIONAL { ?prop rdfs:label   ?label_en   . FILTER(LANG(?label_en)   = "en") }
  OPTIONAL { ?prop rdfs:comment ?comment_en . FILTER(LANG(?comment_en) = "en") }
  OPTIONAL { ?prop rdfs:domain ?domain . }
  OPTIONAL { ?prop rdfs:range  ?range  . }
}
"""

_SPARQL_RELATIONS = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?child ?parent ?rel
WHERE {
  {
    ?child rdfs:subClassOf ?parent .
    BIND(rdfs:subClassOf AS ?rel)
  } UNION {
    ?child owl:equivalentClass ?parent .
    BIND(owl:equivalentClass AS ?rel)
  }
  FILTER(isIRI(?child) && isIRI(?parent))
}
"""

# ---------------------------------------------------------------------------
# Pipeline node entry point
# ---------------------------------------------------------------------------


async def index_fibo_node(state: PipelineState) -> PipelineState:
    """LangGraph node: index FIBO RDF files into PostgreSQL.

    Replaces the old index_ttl_node when using FIBO 2025Q4.
    Supports incremental indexing — already-indexed files (same MD5) are skipped.
    If all FIBO data is already indexed, this node returns immediately.
    """
    job_id = state["job_id"]
    logger.info(f"[index_fibo_node] Starting FIBO indexing for job_id={job_id}")

    # Fast-path: if FIBO is already fully indexed, skip all file scanning
    async with async_session_factory() as db:
        existing_count = (
            await db.execute(
                select(func.count())
                .select_from(OntologyClassIndex)
                .where(OntologyClassIndex.is_deleted == False)
            )
        ).scalar()

    if existing_count and existing_count > 100:
        logger.info(
            f"[index_fibo_node] FIBO already indexed ({existing_count} classes). "
            "Skipping file scan."
        )
        return state

    fibo_root = Path(
        os.getenv(
            "FIBO_DIR",
            str(Path(__file__).parents[4] / "docs" / "fibo-master_2025Q4"),
        )
    )

    if not fibo_root.exists():
        msg = f"FIBO directory not found: {fibo_root}"
        logger.error(msg)
        state["error"] = msg
        return state

    total_classes = 0
    total_props = 0
    total_rels = 0

    # Run CPU-bound RDF parsing in a thread pool to avoid blocking event loop
    import asyncio
    loop = asyncio.get_event_loop()

    async with async_session_factory() as db:
        for module in MODULE_ORDER:
            module_dir = fibo_root / module
            if not module_dir.exists():
                continue

            for rdf_file in sorted(module_dir.rglob("*.rdf")):
                if _should_skip(rdf_file.name):
                    logger.debug(f"  skip: {rdf_file.name}")
                    continue

                file_md5 = await loop.run_in_executor(None, _md5, rdf_file)
                if await _already_indexed(db, rdf_file.name, file_md5):
                    logger.info(f"  cached: {rdf_file.name}")
                    continue

                logger.info(f"  indexing: {rdf_file.relative_to(fibo_root)}")
                try:
                    g = await loop.run_in_executor(None, _parse_rdf, rdf_file)
                    classes, props, rels = _extract_all(g, rdf_file, fibo_root)

                    nc = await _upsert_classes(db, classes)
                    np = await _upsert_properties(db, props)
                    nr = await _upsert_relations(db, rels)

                    meta = OntologyIndexMeta(
                        file_name=rdf_file.name,
                        file_md5=file_md5,
                        ontology_source="fibo",
                        class_count=nc,
                        property_count=np,
                        relation_count=nr,
                        is_active=True,
                    )
                    db.add(meta)
                    await db.commit()

                    total_classes += nc
                    total_props += np
                    total_rels += nr
                    logger.info(
                        f"    → classes={nc}, props={np}, rels={nr}"
                    )
                except Exception as exc:
                    logger.error(f"  FAILED {rdf_file.name}: {exc}")
                    await db.rollback()

    logger.info(
        f"[index_fibo_node] Done. "
        f"total classes={total_classes}, props={total_props}, rels={total_rels}"
    )
    return state


# ---------------------------------------------------------------------------
# Standalone runner (for direct execution / scripts)
# ---------------------------------------------------------------------------


async def run_fibo_indexer(fibo_root: Optional[Path] = None, clear_existing: bool = False):
    """Run the FIBO indexer standalone (outside of Pipeline).

    Args:
        fibo_root: Path to fibo-master_2025Q4 directory.
        clear_existing: If True, clear all existing FIBO index data first.
    """
    if fibo_root is None:
        fibo_root = Path(__file__).parents[4] / "docs" / "fibo-master_2025Q4"

    logger.info(f"FIBO Indexer starting. Root: {fibo_root}")

    if clear_existing:
        async with async_session_factory() as db:
            await db.execute(
                text("DELETE FROM ontology_relation_index WHERE is_deleted = false")
            )
            await db.execute(
                text(
                    "UPDATE ontology_property_index SET is_deleted = true "
                    "WHERE namespace LIKE 'https://spec.edmcouncil.org/fibo/%'"
                )
            )
            await db.execute(
                text(
                    "UPDATE ontology_class_index SET is_deleted = true "
                    "WHERE namespace LIKE 'https://spec.edmcouncil.org/fibo/%'"
                )
            )
            await db.execute(
                text("DELETE FROM ontology_index_meta WHERE ontology_source = 'fibo'")
            )
            await db.commit()
        logger.info("Cleared existing FIBO index data.")

    # Reuse the node logic
    dummy_state: PipelineState = {"job_id": 0}  # type: ignore[typeddict-item]
    env_backup = os.environ.get("FIBO_DIR")
    os.environ["FIBO_DIR"] = str(fibo_root)
    try:
        await index_fibo_node(dummy_state)
    finally:
        if env_backup is None:
            os.environ.pop("FIBO_DIR", None)
        else:
            os.environ["FIBO_DIR"] = env_backup


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _should_skip(filename: str) -> bool:
    return any(p.search(filename) for p in SKIP_FILENAME_PATTERNS)


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_rdf(path: Path) -> Graph:
    g = Graph()
    g.parse(str(path), format="xml")
    return g


def _extract_namespace(uri: str) -> str:
    if "#" in uri:
        return uri.rsplit("#", 1)[0] + "#"
    if "/" in uri:
        return uri.rsplit("/", 1)[0] + "/"
    return uri


def _extract_module_path(uri: str, fibo_root: Path) -> Optional[str]:
    """Extract module path from FIBO URI.

    e.g. https://spec.edmcouncil.org/fibo/ontology/FBC/ProductsAndServices/ClientsAndAccounts/DepositAccount
         → FBC/ProductsAndServices/ClientsAndAccounts
    """
    prefix = "https://spec.edmcouncil.org/fibo/ontology/"
    if not uri.startswith(prefix):
        return None
    rest = uri[len(prefix):]
    parts = rest.rstrip("/").split("/")
    # Remove the last part (class/property name)
    if len(parts) >= 2:
        return "/".join(parts[:-1])
    return parts[0] if parts else None


def _extract_all(
    g: Graph, rdf_file: Path, fibo_root: Path
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Extract classes, properties, and relations from a parsed Graph."""
    classes: Dict[str, Dict] = {}
    props: Dict[str, Dict] = {}
    relations: List[Dict] = []

    # ---- Classes ----
    for row in g.query(_SPARQL_CLASSES):
        uri = str(row["class"])
        if not uri.startswith("http"):
            continue
        if uri in classes:
            existing = classes[uri]
            for k in ("label_en", "comment_en", "parent_uri"):
                if not existing.get(k) and row.get(k.replace("_uri", "").replace("_en", "").replace("label", "label").replace("comment", "comment")):
                    pass  # handled below
            if not existing.get("label_en") and row["label_en"]:
                existing["label_en"] = str(row["label_en"])
            if not existing.get("comment_en") and row["comment_en"]:
                existing["comment_en"] = str(row["comment_en"])
        else:
            classes[uri] = {
                "class_uri": uri,
                "label_en": str(row["label_en"]) if row["label_en"] else _uri_to_label(uri),
                "comment_en": str(row["comment_en"]) if row["comment_en"] else None,
                "parent_uri": str(row["parent"]) if row["parent"] else None,
                "namespace": _extract_namespace(uri),
                "module_path": _extract_module_path(uri, fibo_root),
            }
        # Collect relation
        if row["parent"]:
            relations.append({
                "source_uri": uri,
                "target_uri": str(row["parent"]),
                "relation_type": "subClassOf",
                "namespace": _extract_namespace(uri),
            })

    # ---- Properties ----
    for row in g.query(_SPARQL_PROPERTIES):
        uri = str(row["prop"])
        if not uri.startswith("http"):
            continue
        ptype = str(row["type"]).split("#")[-1] if row["type"] else "ObjectProperty"
        if uri not in props:
            props[uri] = {
                "property_uri": uri,
                "property_type": ptype,
                "label_en": str(row["label_en"]) if row["label_en"] else _uri_to_label(uri),
                "comment_en": str(row["comment_en"]) if row["comment_en"] else None,
                "domain_uri": str(row["domain"]) if row["domain"] else None,
                "range_uri": str(row["range"]) if row["range"] else None,
                "namespace": _extract_namespace(uri),
            }

    return list(classes.values()), list(props.values()), relations


def _uri_to_label(uri: str) -> str:
    """Derive a human-readable label from URI (camelCase split)."""
    local = uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    # Split camelCase: 'DepositAccount' → 'Deposit Account'
    return re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", local)


# ---------------------------------------------------------------------------
# Database upsert helpers
# ---------------------------------------------------------------------------


async def _already_indexed(db: AsyncSession, filename: str, md5: str) -> bool:
    result = await db.execute(
        select(OntologyIndexMeta).where(
            OntologyIndexMeta.file_name == filename,
            OntologyIndexMeta.file_md5 == md5,
            OntologyIndexMeta.ontology_source == "fibo",
        )
    )
    return result.scalar_one_or_none() is not None


async def _upsert_classes(db: AsyncSession, classes: List[Dict]) -> int:
    count = 0
    for c in classes:
        existing = await db.execute(
            select(OntologyClassIndex).where(
                OntologyClassIndex.class_uri == c["class_uri"]
            )
        )
        obj = existing.scalar_one_or_none()
        if obj:
            # Update enrichment fields if missing
            if not obj.label_en and c.get("label_en"):
                obj.label_en = c["label_en"]
            if not obj.comment_en and c.get("comment_en"):
                obj.comment_en = c["comment_en"]
            if not obj.module_path and c.get("module_path"):
                obj.module_path = c["module_path"]
        else:
            search_text = " ".join(
                filter(None, [c.get("label_en"), c.get("comment_en")])
            )
            obj = OntologyClassIndex(
                class_uri=c["class_uri"],
                label_en=c.get("label_en"),
                comment_en=c.get("comment_en"),
                parent_uri=c.get("parent_uri"),
                namespace=c.get("namespace"),
                module_path=c.get("module_path"),
                search_vector=func.to_tsvector("english", search_text) if search_text else None,
                is_deleted=False,
            )
            db.add(obj)
            count += 1
    return count


async def _upsert_properties(db: AsyncSession, props: List[Dict]) -> int:
    count = 0
    for p in props:
        existing = await db.execute(
            select(OntologyPropertyIndex).where(
                OntologyPropertyIndex.property_uri == p["property_uri"]
            )
        )
        obj = existing.scalar_one_or_none()
        if obj:
            if not obj.label_en and p.get("label_en"):
                obj.label_en = p["label_en"]
            if not obj.comment_en and p.get("comment_en"):
                obj.comment_en = p["comment_en"]
            if not obj.domain_uri and p.get("domain_uri"):
                obj.domain_uri = p["domain_uri"]
            if not obj.range_uri and p.get("range_uri"):
                obj.range_uri = p["range_uri"]
        else:
            obj = OntologyPropertyIndex(
                property_uri=p["property_uri"],
                property_type=p.get("property_type", "ObjectProperty"),
                label_en=p.get("label_en"),
                comment_en=p.get("comment_en"),
                domain_uri=p.get("domain_uri"),
                range_uri=p.get("range_uri"),
                namespace=p.get("namespace"),
                is_deleted=False,
            )
            db.add(obj)
            count += 1
    return count


async def _upsert_relations(db: AsyncSession, relations: List[Dict]) -> int:
    count = 0
    for r in relations:
        # Avoid duplicate source+target+type
        existing = await db.execute(
            select(OntologyRelationIndex).where(
                OntologyRelationIndex.source_uri == r["source_uri"],
                OntologyRelationIndex.target_uri == r["target_uri"],
                OntologyRelationIndex.relation_type == r["relation_type"],
            )
        )
        if existing.scalar_one_or_none():
            continue
        obj = OntologyRelationIndex(
            source_uri=r["source_uri"],
            target_uri=r["target_uri"],
            relation_type=r["relation_type"],
            namespace=r.get("namespace"),
            is_deleted=False,
        )
        db.add(obj)
        count += 1
    return count


# ---------------------------------------------------------------------------
# SPARQL query helpers for runtime use (by candidate_retriever)
# ---------------------------------------------------------------------------


async def get_class_with_context(class_uri: str) -> Optional[Dict[str, Any]]:
    """Fetch a FIBO class with its properties and parent chain from PostgreSQL."""
    async with async_session_factory() as db:
        # Get class info
        result = await db.execute(
            select(OntologyClassIndex).where(
                OntologyClassIndex.class_uri == class_uri,
                OntologyClassIndex.is_deleted == False,
            )
        )
        cls = result.scalar_one_or_none()
        if not cls:
            return None

        # Get direct properties (by domain)
        props_result = await db.execute(
            select(OntologyPropertyIndex).where(
                OntologyPropertyIndex.domain_uri == class_uri,
                OntologyPropertyIndex.is_deleted == False,
            )
        )
        properties = [
            {
                "uri": p.property_uri,
                "label_en": p.label_en,
                "type": p.property_type,
                "range": p.range_uri,
            }
            for p in props_result.scalars().all()
        ]

        # Get parent chain (up to 3 levels)
        parent_chain = await _get_parent_chain(db, class_uri, depth=3)

        return {
            "class_uri": cls.class_uri,
            "label_en": cls.label_en,
            "comment_en": cls.comment_en,
            "module_path": cls.module_path,
            "parent_classes": parent_chain,
            "properties": properties,
        }


async def _get_parent_chain(
    db: AsyncSession, class_uri: str, depth: int = 3
) -> List[str]:
    """Walk rdfs:subClassOf upward, return list of parent label_en strings."""
    parents = []
    current = class_uri
    for _ in range(depth):
        rel = await db.execute(
            select(OntologyRelationIndex).where(
                OntologyRelationIndex.source_uri == current,
                OntologyRelationIndex.relation_type == "subClassOf",
                OntologyRelationIndex.is_deleted == False,
            )
        )
        row = rel.scalar_one_or_none()
        if not row:
            break
        parent_uri = row.target_uri
        cls_result = await db.execute(
            select(OntologyClassIndex).where(
                OntologyClassIndex.class_uri == parent_uri,
                OntologyClassIndex.is_deleted == False,
            )
        )
        parent_cls = cls_result.scalar_one_or_none()
        if parent_cls:
            parents.append(parent_cls.label_en or parent_uri.rsplit("/", 1)[-1])
        current = parent_uri
    return parents
