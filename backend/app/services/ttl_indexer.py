"""TTL Indexer - Parse TTL ontology files and build structured index."""

import os
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from rdflib import Graph, Namespace, RDF, RDFS, OWL
from rdflib.namespace import XSD
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, text, func

from backend.app.services.pipeline_state import PipelineState
from backend.app.models.ontology_index import OntologyClassIndex, OntologyPropertyIndex, OntologyIndexMeta
from backend.app.database import async_session_factory


# SPARQL queries
QUERY_CLASSES = """
SELECT ?class ?label_zh ?label_en ?comment_zh ?comment_en ?parent
WHERE {
    ?class a owl:Class .
    OPTIONAL { ?class rdfs:label ?label_zh . FILTER(LANG(?label_zh) = "zh") }
    OPTIONAL { ?class rdfs:label ?label_en . FILTER(LANG(?label_en) = "en") }
    OPTIONAL { ?class rdfs:comment ?comment_zh . FILTER(LANG(?comment_zh) = "zh") }
    OPTIONAL { ?class rdfs:comment ?comment_en . FILTER(LANG(?comment_en) = "en") }
    OPTIONAL { ?class rdfs:subClassOf ?parent . }
}
"""

QUERY_PROPERTIES = """
SELECT ?prop ?type ?label_zh ?label_en ?domain ?range
WHERE {
    ?prop a ?type .
    FILTER (?type IN (owl:ObjectProperty, owl:DatatypeProperty))
    OPTIONAL { ?prop rdfs:label ?label_zh . FILTER(LANG(?label_zh) = "zh") }
    OPTIONAL { ?prop rdfs:label ?label_en . FILTER(LANG(?label_en) = "en") }
    OPTIONAL { ?prop rdfs:domain ?domain . }
    OPTIONAL { ?prop rdfs:range ?range . }
}
"""


async def index_ttl_node(state: PipelineState) -> PipelineState:
    """Parse TTL file and build ontology index.
    
    This node:
    1. Reads TTL file
    2. Parses with rdflib
    3. Extracts owl:Class and owl:Property definitions
    4. Inserts into ontology_class_index and ontology_property_index
    5. Updates search_vector for full-text search
    """
    job_id = state['job_id']
    logger.info(f"[index_ttl_node] Starting TTL indexing for job_id={job_id}")
    
    ttl_dir = Path(os.getenv("TTL_DIR", "./data/ttl"))
    
    if not ttl_dir.exists():
        logger.error(f"TTL directory not found: {ttl_dir}")
        state['error'] = f"TTL directory not found: {ttl_dir}"
        return state
    
    async with async_session_factory() as db:
        for ttl_file in ttl_dir.glob("*.ttl"):
            logger.info(f"Processing TTL file: {ttl_file.name}")
            
            try:
                # Calculate file MD5
                file_md5 = calculate_file_md5(ttl_file)
                
                # Check if already indexed
                existing = await db.execute(
                    select(OntologyIndexMeta).where(
                        OntologyIndexMeta.file_name == ttl_file.name,
                        OntologyIndexMeta.file_md5 == file_md5
                    )
                )
                if existing.scalar_one_or_none():
                    logger.info(f"TTL file already indexed: {ttl_file.name}")
                    continue
                
                # Parse TTL file
                classes, properties = parse_ttl_file(str(ttl_file))
                
                logger.info(f"Extracted {len(classes)} classes and {len(properties)} properties")
                
                # Deduplicate by URI (SPARQL may return multiple rows per class due to optional fields)
                seen_uris = set()
                unique_classes = []
                for c in classes:
                    uri = c['class_uri']
                    if uri not in seen_uris:
                        seen_uris.add(uri)
                        unique_classes.append(c)
                    else:
                        # Merge: prefer non-None values
                        existing_c = next(x for x in unique_classes if x['class_uri'] == uri)
                        for k in ('label_zh', 'label_en', 'comment_zh', 'comment_en', 'parent_uri'):
                            if not existing_c.get(k) and c.get(k):
                                existing_c[k] = c[k]
                
                seen_prop_uris = set()
                unique_props = []
                for p in properties:
                    uri = p['property_uri']
                    if uri not in seen_prop_uris:
                        seen_prop_uris.add(uri)
                        unique_props.append(p)
                
                logger.info(f"After dedup: {len(unique_classes)} classes, {len(unique_props)} properties")
                
                # Insert classes
                for class_info in unique_classes:
                    await insert_class(db, class_info)
                
                # Insert properties
                for prop_info in unique_props:
                    await insert_property(db, prop_info)
                
                # Update index meta
                meta = OntologyIndexMeta(
                    file_name=ttl_file.name,
                    file_md5=file_md5,
                    class_count=len(unique_classes),
                    property_count=len(unique_props),
                    is_active=True
                )
                db.add(meta)
                await db.commit()
                
                logger.info(f"TTL indexing completed for: {ttl_file.name}")
                
            except Exception as e:
                logger.error(f"Failed to index TTL file {ttl_file.name}: {str(e)}")
                await db.rollback()
                state['error'] = f"TTL indexing failed: {str(e)}"
    
    logger.info("[index_ttl_node] TTL indexing completed")
    return state


def calculate_file_md5(file_path: Path) -> str:
    """Calculate MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def parse_ttl_file(ttl_path: str) -> Tuple[List[Dict], List[Dict]]:
    """Parse a TTL file and extract ontology information.
    
    Returns:
        Tuple of (classes, properties) lists
    """
    try:
        g = Graph()
        g.parse(ttl_path, format="turtle")
        
        # Bind namespaces
        g.bind("owl", OWL)
        g.bind("rdfs", RDFS)
        g.bind("rdf", RDF)
        
        # Extract classes
        classes = []
        class_results = g.query(QUERY_CLASSES)
        
        for row in class_results:
            class_uri = str(row['class'])
            namespace = extract_namespace(class_uri)
            
            classes.append({
                'class_uri': class_uri,
                'label_zh': str(row.label_zh) if row.label_zh else None,
                'label_en': str(row.label_en) if row.label_en else None,
                'comment_zh': str(row.comment_zh) if row.comment_zh else None,
                'comment_en': str(row.comment_en) if row.comment_en else None,
                'parent_uri': str(row.parent) if row.parent else None,
                'namespace': namespace,
            })
        
        # Extract properties
        properties = []
        prop_results = g.query(QUERY_PROPERTIES)
        
        for row in prop_results:
            prop_uri = str(row.prop)
            namespace = extract_namespace(prop_uri)
            
            properties.append({
                'property_uri': prop_uri,
                'property_type': str(row.type).split('#')[-1] if row.type else 'Property',
                'label_zh': str(row.label_zh) if row.label_zh else None,
                'label_en': str(row.label_en) if row.label_en else None,
                'domain_uri': str(row.domain) if row.domain else None,
                'range_uri': str(row.range) if row.range else None,
                'namespace': namespace,
            })
        
        return classes, properties
        
    except Exception as e:
        logger.error(f"Failed to parse TTL file: {str(e)}")
        raise


def extract_namespace(uri: str) -> str:
    """Extract namespace from URI."""
    if '#' in uri:
        return uri.rsplit('#', 1)[0] + '#'
    elif '/' in uri:
        return uri.rsplit('/', 1)[0] + '/'
    return uri


async def insert_class(db: AsyncSession, class_info: Dict[str, Any]):
    """Insert or update an ontology class."""
    # Check if exists
    existing = await db.execute(
        select(OntologyClassIndex).where(
            OntologyClassIndex.class_uri == class_info['class_uri']
        )
    )
    
    if existing.scalar_one_or_none():
        logger.debug(f"Class already exists: {class_info['class_uri']}")
        return
    
    # Build search vector using PostgreSQL to_tsvector cast
    search_text = ' '.join(filter(None, [
        class_info.get('label_zh'),
        class_info.get('label_en'),
        class_info.get('comment_zh'),
        class_info.get('comment_en'),
    ]))
    
    # Insert class
    class_index = OntologyClassIndex(
        class_uri=class_info['class_uri'],
        label_zh=class_info.get('label_zh'),
        label_en=class_info.get('label_en'),
        comment_zh=class_info.get('comment_zh'),
        comment_en=class_info.get('comment_en'),
        parent_uri=class_info.get('parent_uri'),
        namespace=class_info.get('namespace'),
        search_vector=func.to_tsvector('simple', search_text),
    )
    db.add(class_index)


async def insert_property(db: AsyncSession, prop_info: Dict[str, Any]):
    """Insert or update an ontology property."""
    # Check if exists
    existing = await db.execute(
        select(OntologyPropertyIndex).where(
            OntologyPropertyIndex.property_uri == prop_info['property_uri']
        )
    )
    
    if existing.scalar_one_or_none():
        logger.debug(f"Property already exists: {prop_info['property_uri']}")
        return
    
    # Insert property
    prop_index = OntologyPropertyIndex(
        property_uri=prop_info['property_uri'],
        property_type=prop_info.get('property_type', 'Property'),
        label_zh=prop_info.get('label_zh'),
        label_en=prop_info.get('label_en'),
        domain_uri=prop_info.get('domain_uri'),
        range_uri=prop_info.get('range_uri'),
        namespace=prop_info.get('namespace'),
    )
    db.add(prop_index)


async def search_candidates(keywords: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Search for candidate FIBO classes by keywords.
    
    Uses PostgreSQL full-text search.
    """
    async with async_session_factory() as db:
        # Use simple text search for now
        # In production, use to_tsvector with proper configuration
        query = text("""
            SELECT class_uri, label_zh, label_en, comment_zh,
                   similarity(search_vector, :keywords) as rank
            FROM ontology_class_index
            WHERE search_vector % :keywords
               OR label_zh ILIKE :pattern
               OR label_en ILIKE :pattern
            ORDER BY rank DESC
            LIMIT :limit
        """)
        
        result = await db.execute(
            query,
            {
                'keywords': keywords,
                'pattern': f'%{keywords}%',
                'limit': limit
            }
        )
        
        candidates = []
        for row in result:
            candidates.append({
                'class_uri': row.class_uri,
                'label_zh': row.label_zh,
                'label_en': row.label_en,
                'comment_zh': row.comment_zh,
                'rank': row.rank,
            })
        
        return candidates


async def get_properties_for_class(class_uri: str) -> List[Dict[str, Any]]:
    """Get all properties applicable to a class (by domain)."""
    async with async_session_factory() as db:
        result = await db.execute(
            select(OntologyPropertyIndex).where(
                OntologyPropertyIndex.domain_uri == class_uri
            )
        )
        
        properties = []
        for prop in result.scalars():
            properties.append({
                'property_uri': prop.property_uri,
                'property_type': prop.property_type,
                'label_zh': prop.label_zh,
                'label_en': prop.label_en,
                'domain_uri': prop.domain_uri,
                'range_uri': prop.range_uri,
            })
        
        return properties
