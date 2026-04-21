"""Candidate Retriever - Retrieve FIBO candidate classes for mapping.

Three-stage search strategy optimised for FIBO 2025Q4 (all-English labels):

Stage 1: pg_trgm similarity search on label_en + comment_en
  Best for: "deposit account" → DepositAccount, "payable" → REAClaim

Stage 2: Inheritance-chain expansion
  Best for: found DepositAccount → also return parent Account, FinancialProduct

Stage 3: Property-domain reverse lookup
  Best for: field "amount" → hasAmount.domain → MonetaryAmount
"""

import re
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import func, or_, select, text

from backend.app.database import async_session_factory
from backend.app.models.ontology_index import (
    OntologyClassIndex,
    OntologyPropertyIndex,
    OntologyRelationIndex,
)
from backend.app.services.pipeline_state import PipelineState


# ---------------------------------------------------------------------------
# Pipeline node
# ---------------------------------------------------------------------------


async def retrieve_candidates_node(state: PipelineState) -> PipelineState:
    """Validate ontology index is populated and log readiness."""
    current_batch = state.get("current_batch", [])
    if not current_batch:
        logger.info("[retrieve_candidates_node] Empty batch, skipping")
        return state

    async with async_session_factory() as db:
        result = await db.execute(
            select(func.count())
            .select_from(OntologyClassIndex)
            .where(OntologyClassIndex.is_deleted == False)
        )
        class_count = result.scalar()

    if class_count == 0:
        logger.warning(
            "[retrieve_candidates_node] ontology_class_index is empty — "
            "run fibo_indexer first"
        )
    else:
        logger.info(
            f"[retrieve_candidates_node] ontology index has {class_count} classes; "
            f"batch of {len(current_batch)} tables ready for FIBO mapping"
        )
    return state


# ---------------------------------------------------------------------------
# Main search API
# ---------------------------------------------------------------------------


async def search_candidates(
    keywords: str,
    limit: int = 20,
    field_names: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Search FIBO candidate classes using three-stage strategy.

    Args:
        keywords: Space-separated keywords from table name, comments, and field names.
        limit:    Maximum candidates to return.
        field_names: Optional list of field names for property-domain reverse lookup.

    Returns:
        List of candidate dicts with keys:
          class_uri, label_en, comment_en, module_path, namespace, parent_chain, properties
    """
    async with async_session_factory() as db:
        seen_uris: set = set()
        candidates: List[Dict] = []

        # -------- Stage 1: pg_trgm similarity search --------
        english_terms = _extract_english_terms(keywords)
        trgm_results = await _trgm_search(db, english_terms, limit)
        for row in trgm_results:
            if row["class_uri"] not in seen_uris:
                seen_uris.add(row["class_uri"])
                candidates.append(row)

        # -------- Stage 1b: Full-text tsvector search --------
        if len(candidates) < limit:
            fts_results = await _fts_search(db, english_terms, limit - len(candidates))
            for row in fts_results:
                if row["class_uri"] not in seen_uris:
                    seen_uris.add(row["class_uri"])
                    candidates.append(row)

        # -------- Stage 2: Inheritance-chain expansion --------
        if candidates:
            parent_uris = set()
            for c in list(candidates):
                parents = await _get_parents(db, c["class_uri"], depth=2)
                parent_uris.update(p for p in parents if p not in seen_uris)

            if parent_uris:
                parent_results = await _fetch_classes_by_uris(db, list(parent_uris))
                for row in parent_results:
                    if row["class_uri"] not in seen_uris and len(candidates) < limit:
                        seen_uris.add(row["class_uri"])
                        candidates.append(row)

        # -------- Stage 3: Property-domain reverse lookup --------
        if field_names and len(candidates) < limit:
            field_terms = _extract_english_terms(" ".join(field_names))
            domain_uris = await _property_domain_lookup(
                db, field_terms, limit - len(candidates)
            )
            for uri in domain_uris:
                if uri not in seen_uris:
                    rows = await _fetch_classes_by_uris(db, [uri])
                    if rows:
                        seen_uris.add(uri)
                        candidates.append(rows[0])

        # -------- Enrich with properties (for Prompt) --------
        for c in candidates:
            c["properties"] = await _get_class_properties(db, c["class_uri"])
            c["parent_chain"] = await _get_parent_labels(db, c["class_uri"])

    logger.debug(f"search_candidates('{keywords[:60]}') → {len(candidates)} results")
    return candidates[:limit]


# ---------------------------------------------------------------------------
# Stage 1: pg_trgm similarity
# ---------------------------------------------------------------------------


async def _trgm_search(
    db, terms: List[str], limit: int
) -> List[Dict[str, Any]]:
    if not terms:
        return []

    # Build OR conditions: similarity on label_en and comment_en
    query_str = " | ".join(terms)  # Use the most distinctive terms

    rows = await db.execute(
        text("""
            SELECT DISTINCT class_uri, label_en, comment_en, module_path, namespace,
                   GREATEST(
                     similarity(LOWER(label_en), LOWER(:q)),
                     similarity(LOWER(COALESCE(comment_en, '')), LOWER(:q))
                   ) AS sim
            FROM ontology_class_index
            WHERE is_deleted = false
              AND (
                label_en ILIKE ANY(:patterns)
                OR comment_en ILIKE ANY(:patterns)
              )
            ORDER BY sim DESC
            LIMIT :limit
        """),
        {
            "q": query_str,
            "patterns": [f"%{t}%" for t in terms],
            "limit": limit,
        },
    )
    return [_row_to_dict(r) for r in rows.fetchall()]


# ---------------------------------------------------------------------------
# Stage 1b: Full-text vector search
# ---------------------------------------------------------------------------


async def _fts_search(db, terms: List[str], limit: int) -> List[Dict[str, Any]]:
    if not terms:
        return []
    query_words = " | ".join(terms)
    try:
        tsquery = func.to_tsquery("english", query_words)
        result = await db.execute(
            select(
                OntologyClassIndex.class_uri,
                OntologyClassIndex.label_en,
                OntologyClassIndex.comment_en,
                OntologyClassIndex.module_path,
                OntologyClassIndex.namespace,
            )
            .where(
                OntologyClassIndex.search_vector.op("@@")(tsquery),
                OntologyClassIndex.is_deleted == False,
            )
            .order_by(
                func.ts_rank(OntologyClassIndex.search_vector, tsquery).desc()
            )
            .limit(limit)
        )
        return [_row_to_dict(r) for r in result.fetchall()]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Stage 2: Inheritance chain
# ---------------------------------------------------------------------------


async def _get_parents(db, class_uri: str, depth: int = 2) -> List[str]:
    parents = []
    current = class_uri
    for _ in range(depth):
        result = await db.execute(
            select(OntologyRelationIndex.target_uri).where(
                OntologyRelationIndex.source_uri == current,
                OntologyRelationIndex.relation_type == "subClassOf",
                OntologyRelationIndex.is_deleted == False,
            )
        )
        # FIBO supports multiple inheritance; take the first parent only
        row = result.scalars().first()
        if not row:
            break
        parents.append(row)
        current = row
    return parents


async def _get_parent_labels(db, class_uri: str, depth: int = 3) -> List[str]:
    labels = []
    current = class_uri
    for _ in range(depth):
        result = await db.execute(
            select(OntologyRelationIndex.target_uri).where(
                OntologyRelationIndex.source_uri == current,
                OntologyRelationIndex.relation_type == "subClassOf",
                OntologyRelationIndex.is_deleted == False,
            )
        )
        # FIBO supports multiple inheritance; take the first parent only
        parent_uri = result.scalars().first()
        if not parent_uri:
            break
        cls_result = await db.execute(
            select(OntologyClassIndex.label_en).where(
                OntologyClassIndex.class_uri == parent_uri,
                OntologyClassIndex.is_deleted == False,
            )
        )
        label = cls_result.scalar_one_or_none()
        labels.append(label or parent_uri.rsplit("/", 1)[-1])
        current = parent_uri
    return labels


# ---------------------------------------------------------------------------
# Stage 3: Property-domain reverse lookup
# ---------------------------------------------------------------------------


async def _property_domain_lookup(
    db, terms: List[str], limit: int
) -> List[str]:
    """Find FIBO classes by looking up which class has properties matching field terms."""
    if not terms:
        return []

    result = await db.execute(
        select(OntologyPropertyIndex.domain_uri).where(
            OntologyPropertyIndex.is_deleted == False,
            OntologyPropertyIndex.domain_uri.isnot(None),
            or_(*[OntologyPropertyIndex.label_en.ilike(f"%{t}%") for t in terms]),
        ).distinct().limit(limit)
    )
    return [row[0] for row in result.fetchall() if row[0]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _fetch_classes_by_uris(
    db, uris: List[str]
) -> List[Dict[str, Any]]:
    if not uris:
        return []
    result = await db.execute(
        select(
            OntologyClassIndex.class_uri,
            OntologyClassIndex.label_en,
            OntologyClassIndex.comment_en,
            OntologyClassIndex.module_path,
            OntologyClassIndex.namespace,
        ).where(
            OntologyClassIndex.class_uri.in_(uris),
            OntologyClassIndex.is_deleted == False,
        )
    )
    return [_row_to_dict(r) for r in result.fetchall()]


async def _get_class_properties(
    db, class_uri: str, limit: int = 15
) -> List[Dict[str, Any]]:
    """Return properties whose domain is the given class URI."""
    result = await db.execute(
        select(OntologyPropertyIndex).where(
            OntologyPropertyIndex.domain_uri == class_uri,
            OntologyPropertyIndex.is_deleted == False,
        ).limit(limit)
    )
    return [
        {
            "uri": p.property_uri,
            "label_en": p.label_en or p.property_uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1],
            "type": p.property_type,
            "range": p.range_uri,
        }
        for p in result.scalars().all()
    ]


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "class_uri": row.class_uri,
        "label_en": row.label_en,
        "comment_en": row.comment_en,
        "module_path": getattr(row, "module_path", None),
        "namespace": row.namespace,
        "properties": [],    # populated later
        "parent_chain": [],  # populated later
    }


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------

# Business term mapping: Chinese/domain keywords → FIBO English search terms
_KEYWORD_MAP = {
    # Accounting / AP / AR
    "应付": ["payable", "liability", "obligation"],
    "应收": ["receivable", "asset", "claim"],
    "账款": ["account", "receivable", "payable"],
    "付款": ["payment", "disbursement"],
    "收款": ["collection", "receipt", "settlement"],
    "结算": ["settlement", "clearing"],
    # Banking
    "银行账": ["bank account", "deposit account"],
    "存款": ["deposit", "savings"],
    "贷款": ["loan", "credit"],
    "融资": ["financing", "loan", "debt"],
    "债务": ["debt", "obligation", "liability"],
    "债券": ["bond", "security", "debt instrument"],
    # Credit
    "授信": ["credit facility", "credit limit", "credit agreement"],
    "信用": ["credit", "creditworthiness"],
    # Guarantee
    "担保": ["guaranty", "collateral", "security"],
    "抵押": ["mortgage", "collateral", "pledge"],
    "质押": ["pledge", "collateral"],
    # Contract
    "合同": ["contract", "agreement"],
    "利率": ["interest rate", "rate"],
    "利息": ["interest", "accrued interest"],
    "还款": ["repayment", "principal payment"],
    "费用": ["fee", "charge"],
}


def _extract_english_terms(text: str) -> List[str]:
    """Extract English search terms from mixed Chinese/English input."""
    terms = []

    # 1. Map known Chinese phrases to English
    for zh, en_list in _KEYWORD_MAP.items():
        if zh in text:
            terms.extend(en_list)

    # 2. Extract raw English words (split camelCase)
    english_words = re.findall(r"[A-Za-z][a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)", text)
    terms.extend([w.lower() for w in english_words if len(w) > 2])

    # 3. Extract plain English tokens
    plain_tokens = re.split(r"[\s_\-,，。、：:]+", text)
    for t in plain_tokens:
        if t.isascii() and len(t) > 2:
            terms.append(t.lower())

    # De-duplicate, keep order, max 15 terms
    seen: set = set()
    result = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result[:15]
