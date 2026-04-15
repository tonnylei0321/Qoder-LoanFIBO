"""Candidate Retriever - Retrieve FIBO candidate classes for mapping."""

from typing import List, Dict, Any
from loguru import logger
from sqlalchemy import select, func, text

from backend.app.services.pipeline_state import PipelineState
from backend.app.database import async_session_factory
from backend.app.models.ontology_index import OntologyClassIndex


async def retrieve_candidates_node(state: PipelineState) -> PipelineState:
    """Validate that the ontology index is populated and pass-through state.

    mapping_llm_node calls search_candidates internally for each table, so
    this node only needs to confirm the index is non-empty and log progress.
    """
    current_batch = state.get('current_batch', [])
    if not current_batch:
        logger.info("[retrieve_candidates_node] Empty batch, skipping")
        return state

    async with async_session_factory() as db:
        result = await db.execute(
            select(func.count()).select_from(OntologyClassIndex)
            .where(OntologyClassIndex.is_deleted == False)
        )
        class_count = result.scalar()

    if class_count == 0:
        logger.warning(
            "[retrieve_candidates_node] ontology_class_index is empty — "
            "run index_ttl_node first"
        )
    else:
        logger.info(
            f"[retrieve_candidates_node] ontology index has {class_count} classes; "
            f"batch of {len(current_batch)} tables ready for mapping"
        )
    return state


async def search_candidates(keywords: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Search for candidate FIBO classes by keywords.

    Uses PostgreSQL tsvector full-text search with ts_rank scoring.
    Falls back to an ILIKE label search when the tsvector query matches nothing.

    Args:
        keywords: Space-separated keywords derived from table/field names and comments.
        limit:    Maximum number of candidates to return.

    Returns:
        List of dicts with keys: class_uri, label_zh, label_en, comment_zh, namespace.
    """
    async with async_session_factory() as db:
        # Primary: tsvector full-text search with rank scoring
        tsquery = func.plainto_tsquery('simple', keywords)
        query = (
            select(
                OntologyClassIndex.class_uri,
                OntologyClassIndex.label_zh,
                OntologyClassIndex.label_en,
                OntologyClassIndex.comment_zh,
                OntologyClassIndex.namespace,
                func.ts_rank(OntologyClassIndex.search_vector, tsquery).label('rank'),
            )
            .where(
                OntologyClassIndex.search_vector.op('@@')(tsquery),
                OntologyClassIndex.is_deleted == False,
            )
            .order_by(text('rank DESC'))
            .limit(limit)
        )
        result = await db.execute(query)
        rows = result.fetchall()

        # Fallback: ILIKE on Chinese/English labels when tsvector returns nothing
        if not rows:
            pattern = f"%{keywords[:30]}%"   # use first 30 chars to keep pattern sane
            fallback_query = (
                select(
                    OntologyClassIndex.class_uri,
                    OntologyClassIndex.label_zh,
                    OntologyClassIndex.label_en,
                    OntologyClassIndex.comment_zh,
                    OntologyClassIndex.namespace,
                )
                .where(
                    (
                        OntologyClassIndex.label_zh.ilike(pattern)
                        | OntologyClassIndex.label_en.ilike(pattern)
                        | OntologyClassIndex.comment_zh.ilike(pattern)
                    ),
                    OntologyClassIndex.is_deleted == False,
                )
                .limit(limit)
            )
            result = await db.execute(fallback_query)
            rows = result.fetchall()

    return [
        {
            'class_uri': r.class_uri,
            'label_zh': r.label_zh,
            'label_en': r.label_en,
            'comment_zh': r.comment_zh,
            'namespace': r.namespace,
        }
        for r in rows
    ]

