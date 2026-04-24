"""Pipeline API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from backend.app.database import get_db
from backend.app.schemas import pipeline as schemas

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/jobs", response_model=schemas.JobResponse)
async def create_job(job: schemas.JobCreate, db: AsyncSession = Depends(get_db)):
    """Create a new mapping job."""
    # TODO: Implement job creation
    return {
        "code": 0,
        "data": {
            "job_id": 1,
            "status": "pending",
            "total_tables": 0,
            "created_at": "2026-04-15T00:00:00Z",
        }
    }


@router.get("/jobs/{job_id}", response_model=schemas.JobResponse)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Get job status and progress."""
    # TODO: Implement job status query
    return {
        "code": 0,
        "data": {
            "job_id": job_id,
            "status": "pending",
            "total_tables": 0,
            "created_at": "2026-04-15T00:00:00Z",
        }
    }


@router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Pause a running job."""
    # TODO: Implement job pause
    return {"code": 0, "message": "Job paused"}


@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Resume a paused job."""
    # TODO: Implement job resume
    return {"code": 0, "message": "Job resumed"}


@router.get("/mappings")
async def get_mappings(
    database: Optional[str] = None,
    mapping_status: Optional[str] = None,
    review_status: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Get table mapping results with table/field comments from DB."""
    from sqlalchemy import select, func
    from backend.app.models.table_mapping import TableMapping
    from backend.app.models.table_registry import TableRegistry
    
    # Join TableMapping with TableRegistry to get stored comments
    query = select(TableMapping, TableRegistry).join(
        TableRegistry,
        (TableMapping.database_name == TableRegistry.database_name) &
        (TableMapping.table_name == TableRegistry.table_name)
    ).where(TableMapping.is_deleted == False)
    
    if database:
        query = query.where(TableMapping.database_name == database)
    if mapping_status:
        query = query.where(TableMapping.mapping_status == mapping_status)
    if review_status:
        query = query.where(TableMapping.review_status == review_status)
    
    # Get total count
    count_query = select(func.count()).select_from(TableMapping).where(TableMapping.is_deleted == False)
    if database:
        count_query = count_query.where(TableMapping.database_name == database)
    if mapping_status:
        count_query = count_query.where(TableMapping.mapping_status == mapping_status)
    if review_status:
        count_query = count_query.where(TableMapping.review_status == review_status)
    
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Get paginated results
    query = query.order_by(TableMapping.id.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows = result.all()

    # Batch-fetch field_mapping for all table_mapping ids in this page
    from backend.app.models.table_mapping import FieldMapping
    from backend.app.models.ontology_index import OntologyClassIndex, OntologyPropertyIndex
    table_mapping_ids = [m.id for m, r in rows]
    field_map: dict = {}  # table_mapping_id -> {field_name -> {fibo_property_uri, confidence_level}}
    if table_mapping_ids:
        fm_result = await db.execute(
            select(FieldMapping).where(
                FieldMapping.table_mapping_id.in_(table_mapping_ids),
                FieldMapping.is_deleted == False,
            )
        )
        for fm in fm_result.scalars().all():
            field_map.setdefault(fm.table_mapping_id, {})[fm.field_name] = {
                "fibo_property_uri": fm.fibo_property_uri,
                "confidence_level": fm.confidence_level,
            }

    # Cache for FIBO class/property labels
    class_label_cache: dict = {}  # class_uri -> label_zh
    property_label_cache: dict = {}  # property_uri -> label_zh

    async def get_class_label(class_uri: str) -> str:
        """Get class Chinese label from cache or DB."""
        if not class_uri:
            return ""
        if class_uri in class_label_cache:
            return class_label_cache[class_uri]
        result = await db.execute(
            select(OntologyClassIndex.label_zh, OntologyClassIndex.label_en).where(
                OntologyClassIndex.class_uri == class_uri,
                OntologyClassIndex.is_deleted == False,
            )
        )
        row = result.first()
        label = row.label_zh if row and row.label_zh else (row.label_en if row and row.label_en else "")
        class_label_cache[class_uri] = label
        return label

    async def get_property_label(property_uri: str) -> str:
        """Get property Chinese label from cache or DB."""
        if not property_uri:
            return ""
        if property_uri in property_label_cache:
            return property_label_cache[property_uri]
        result = await db.execute(
            select(OntologyPropertyIndex.label_zh, OntologyPropertyIndex.label_en).where(
                OntologyPropertyIndex.property_uri == property_uri,
                OntologyPropertyIndex.is_deleted == False,
            )
        )
        row = result.first()
        label = row.label_zh if row and row.label_zh else (row.label_en if row and row.label_en else "")
        property_label_cache[property_uri] = label
        return label

    async def build_fields(parsed_fields: list, mapping_status: str, fibo_class_uri: str, tm_id: int) -> list:
        """Build field list merging parsed_fields with field_mapping data."""
        if not parsed_fields:
            return []
        is_mapped = mapping_status == "mapped"
        fm_for_table = field_map.get(tm_id, {})
        result_fields = []
        # Get class label
        class_label = await get_class_label(fibo_class_uri) if is_mapped else ""
        for f in parsed_fields:
            fname = f.get("field_name", "")
            fm_data = fm_for_table.get(fname, {})
            fibo_prop = fm_data.get("fibo_property_uri")
            prop_conf = fm_data.get("confidence_level")
            # Get property label
            prop_label = await get_property_label(fibo_prop) if fibo_prop else ""
            result_fields.append({
                "name": fname,
                "type": f.get("field_type", ""),
                "comment": f.get("comment") or "",
                "is_primary_key": f.get("is_primary_key", False),
                "is_nullable": f.get("is_nullable", True),
                "fibo_entity": fibo_class_uri if is_mapped else None,
                "fibo_entity_label": class_label,
                "fibo_property": fibo_prop,
                "fibo_property_label": prop_label,
                "fibo_property_confidence": prop_conf,
                "is_mapped": is_mapped or (fibo_prop is not None),
            })
        return result_fields

    # Build items with async field processing
    items = []
    for m, r in rows:
        parsed_fields_result = await build_fields(r.parsed_fields, m.mapping_status, m.fibo_class_uri, m.id)
        items.append({
            "id": m.id,
            "job_id": m.job_id,
            "database_name": m.database_name,
            "table_name": m.table_name,
            "table_comment": r.table_comment or "",
            "fibo_class_uri": m.fibo_class_uri,
            "confidence_level": m.confidence_level or ("low" if m.mapping_status == "unmappable" else None),
            "mapping_reason": m.mapping_reason or ("未找到合适的 FIBO 类映射" if m.mapping_status == "unmappable" else ""),
            "mapping_status": m.mapping_status,
            "review_status": m.review_status,
            "revision_count": m.revision_count,
            "model_used": m.model_used,
            "total_fields": len(r.parsed_fields) if r.parsed_fields else 0,
            "mapped_fields": len(r.parsed_fields) if m.mapping_status == "mapped" and r.parsed_fields else 0,
            "unmapped_fields": 0 if m.mapping_status == "mapped" else (len(r.parsed_fields) if r.parsed_fields else 0),
            "parsed_fields": parsed_fields_result,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })

    return {
        "code": 0,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    }


@router.get("/tables/{table_id}/fields")
async def get_table_fields(
    table_id: int,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Get fields for a specific table."""
    from sqlalchemy import select
    from backend.app.models.table_registry import TableRegistry
    
    result = await db.execute(
        select(TableRegistry).where(
            TableRegistry.id == table_id,
            TableRegistry.is_deleted == False
        )
    )
    table = result.scalar_one_or_none()
    
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    fields = table.parsed_fields or []
    total = len(fields)
    
    # Paginate fields
    start = (page - 1) * page_size
    end = start + page_size
    paginated_fields = fields[start:end]
    
    return {
        "code": 0,
        "data": {
            "table_name": f"{table.database_name}.{table.table_name}",
            "items": [
                {
                    "id": f"{table_id}_{i}",
                    "field_name": f.get("name", ""),
                    "field_type": f.get("type", ""),
                    "comment": f.get("comment", ""),
                    "status": "pending",
                }
                for i, f in enumerate(paginated_fields)
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    }


@router.get("/mappings/reviews")
async def get_review_items(
    review_status: Optional[str] = "pending",
    database: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Get table mappings that need human review."""
    from sqlalchemy import select, func
    from backend.app.models.table_mapping import TableMapping, FieldMapping
    from backend.app.models.mapping_review import MappingReview

    query = select(TableMapping).where(TableMapping.is_deleted == False)
    if review_status:
        query = query.where(TableMapping.review_status == review_status)
    if database:
        query = query.where(TableMapping.database_name == database)

    count_query = select(func.count()).select_from(TableMapping).where(TableMapping.is_deleted == False)
    if review_status:
        count_query = count_query.where(TableMapping.review_status == review_status)
    if database:
        count_query = count_query.where(TableMapping.database_name == database)

    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(TableMapping.id.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).scalars().all()

    # Fetch review comments for these mappings
    mapping_ids = [m.id for m in rows]
    review_map: dict = {}
    if mapping_ids:
        rev_result = await db.execute(
            select(MappingReview).where(
                MappingReview.table_mapping_id.in_(mapping_ids),
                MappingReview.is_deleted == False,
                MappingReview.is_resolved == False,
            )
        )
        for rev in rev_result.scalars().all():
            review_map.setdefault(rev.table_mapping_id, []).append({
                "id": rev.id,
                "issue_type": rev.issue_type,
                "severity": rev.severity,
                "is_must_fix": rev.is_must_fix,
                "issue_description": rev.issue_description,
                "suggested_fix": rev.suggested_fix,
                "review_round": rev.review_round,
                "created_at": rev.created_at.isoformat() if rev.created_at else None,
            })

    # Fetch field mappings
    field_map: dict = {}
    if mapping_ids:
        fm_result = await db.execute(
            select(FieldMapping).where(
                FieldMapping.table_mapping_id.in_(mapping_ids),
                FieldMapping.is_deleted == False,
            )
        )
        for fm in fm_result.scalars().all():
            field_map.setdefault(fm.table_mapping_id, []).append({
                "id": fm.id,
                "field_name": fm.field_name,
                "field_type": fm.field_type,
                "fibo_property_uri": fm.fibo_property_uri,
                "confidence_level": fm.confidence_level,
                "mapping_reason": fm.mapping_reason,
            })

    items = []
    for m in rows:
        items.append({
            "id": m.id,
            "job_id": m.job_id,
            "database_name": m.database_name,
            "table_name": m.table_name,
            "fibo_class_uri": m.fibo_class_uri,
            "confidence_level": m.confidence_level,
            "mapping_reason": m.mapping_reason,
            "mapping_status": m.mapping_status,
            "review_status": m.review_status,
            "revision_count": m.revision_count,
            "model_used": m.model_used,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            "reviews": review_map.get(m.id, []),
            "field_mappings": field_map.get(m.id, []),
        })

    return {
        "code": 0,
        "data": {"items": items, "total": total, "page": page, "page_size": page_size},
    }


@router.post("/mappings/{table_mapping_id}/review")
async def submit_review(
    table_mapping_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a review decision for a table mapping.
    payload: { action: 'approve'|'reject', comment?: str, new_fibo_class_uri?: str }
    """
    from sqlalchemy import select
    from backend.app.models.table_mapping import TableMapping
    from backend.app.models.mapping_review import MappingReview

    action = payload.get("action")  # 'approve' or 'reject'
    comment = payload.get("comment", "")
    new_fibo_class_uri = payload.get("new_fibo_class_uri")

    if action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

    result = await db.execute(
        select(TableMapping).where(
            TableMapping.id == table_mapping_id,
            TableMapping.is_deleted == False,
        )
    )
    mapping = result.scalar_one_or_none()
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    # Update review_status
    mapping.review_status = "approved" if action == "approve" else "rejected"

    # Optionally update FIBO class URI if reviewer provides a correction
    if new_fibo_class_uri:
        mapping.fibo_class_uri = new_fibo_class_uri
        mapping.mapping_status = "mapped"

    # Mark all open review comments as resolved
    rev_result = await db.execute(
        select(MappingReview).where(
            MappingReview.table_mapping_id == table_mapping_id,
            MappingReview.is_resolved == False,
            MappingReview.is_deleted == False,
        )
    )
    for rev in rev_result.scalars().all():
        rev.is_resolved = True

    # If reviewer left a comment, record it as a new resolved review entry
    if comment:
        new_rev = MappingReview(
            table_mapping_id=table_mapping_id,
            review_round=mapping.revision_count,
            issue_type="human_review",
            severity="low",
            is_must_fix=False,
            issue_description=comment,
            suggested_fix=None,
            is_resolved=True,
        )
        db.add(new_rev)

    await db.commit()
    return {"code": 0, "message": "审核完成", "data": {"review_status": mapping.review_status}}


@router.get("/mappings/{table_mapping_id}")
async def get_mapping_detail(
    table_mapping_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get detail for a single table mapping."""
    from sqlalchemy import select
    from backend.app.models.table_mapping import TableMapping, FieldMapping
    from backend.app.models.table_registry import TableRegistry
    from backend.app.models.ontology_index import OntologyClassIndex

    result = await db.execute(
        select(TableMapping, TableRegistry).join(
            TableRegistry,
            (TableMapping.database_name == TableRegistry.database_name) &
            (TableMapping.table_name == TableRegistry.table_name)
        ).where(
            TableMapping.id == table_mapping_id,
            TableMapping.is_deleted == False,
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Mapping not found")

    m, r = row
    # Fetch field mappings
    fm_result = await db.execute(
        select(FieldMapping).where(
            FieldMapping.table_mapping_id == m.id,
            FieldMapping.is_deleted == False,
        )
    )
    field_mappings = fm_result.scalars().all()

    # Get class label
    class_label = ""
    if m.fibo_class_uri:
        cls_result = await db.execute(
            select(OntologyClassIndex.label_zh, OntologyClassIndex.label_en).where(
                OntologyClassIndex.class_uri == m.fibo_class_uri,
                OntologyClassIndex.is_deleted == False,
            )
        )
        cls_row = cls_result.first()
        class_label = cls_row.label_zh if cls_row and cls_row.label_zh else (cls_row.label_en if cls_row and cls_row.label_en else "")

    parsed_fields = r.parsed_fields or []
    fields = []
    for f in parsed_fields:
        fname = f.get("field_name", "")
        fm_data = next((fm for fm in field_mappings if fm.field_name == fname), None)
        fields.append({
            "name": fname,
            "type": f.get("field_type", ""),
            "comment": f.get("comment") or "",
            "fibo_entity": m.fibo_class_uri if m.mapping_status == "mapped" else None,
            "fibo_entity_label": class_label,
            "fibo_property": fm_data.fibo_property_uri if fm_data else None,
            "fibo_property_confidence": fm_data.confidence_level if fm_data else None,
            "is_mapped": fm_data is not None and fm_data.fibo_property_uri is not None,
        })

    return {
        "code": 0,
        "data": {
            "id": m.id,
            "job_id": m.job_id,
            "database_name": m.database_name,
            "table_name": m.table_name,
            "table_comment": r.table_comment or "",
            "fibo_class_uri": m.fibo_class_uri,
            "confidence_level": m.confidence_level,
            "mapping_reason": m.mapping_reason or "",
            "mapping_status": m.mapping_status,
            "review_status": m.review_status,
            "revision_count": m.revision_count,
            "model_used": m.model_used,
            "parsed_fields": fields,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
    }


@router.patch("/mappings/{table_mapping_id}")
async def update_mapping(
    table_mapping_id: int,
    update: schemas.MappingUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Manually update a table mapping."""
    # TODO: Implement mapping update
    return {"code": 0, "message": "Mapping updated"}


@router.patch("/field-mappings/{field_mapping_id}")
async def update_field_mapping(
    field_mapping_id: int,
    update: schemas.FieldMappingUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Manually update a field mapping."""
    # TODO: Implement field mapping update
    return {"code": 0, "message": "Field mapping updated"}


@router.post("/mappings/{table_mapping_id}/remap")
async def remap_table(table_mapping_id: int, db: AsyncSession = Depends(get_db)):
    """Trigger remapping for a single table."""
    # TODO: Implement remap
    return {"code": 0, "message": "Remap triggered"}


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get mapping statistics overview with pipeline node stats."""
    from sqlalchemy import select, func
    from backend.app.models.table_registry import TableRegistry
    from backend.app.models.table_mapping import TableMapping
    from backend.app.models.ontology_index import OntologyClassIndex
    
    # Get table counts by status
    result = await db.execute(
        select(TableRegistry.mapping_status, func.count())
        .where(TableRegistry.is_deleted == False)
        .group_by(TableRegistry.mapping_status)
    )
    table_status_counts = {status: count for status, count in result.fetchall()}
    
    total_tables = sum(table_status_counts.values())
    mapped_tables = table_status_counts.get('mapped', 0)
    pending_tables = table_status_counts.get('pending', 0)
    
    # Get field counts (from parsed_fields)
    result = await db.execute(
        select(func.sum(func.jsonb_array_length(TableRegistry.parsed_fields)))
        .where(TableRegistry.is_deleted == False)
    )
    total_fields = result.scalar() or 0
    
    # Get ontology class count
    result = await db.execute(
        select(func.count()).select_from(OntologyClassIndex)
        .where(OntologyClassIndex.is_deleted == False)
    )
    ontology_classes = result.scalar() or 0
    
    # Get latest job to determine pipeline execution status
    from backend.app.models.mapping_job import MappingJob
    result = await db.execute(
        select(MappingJob)
        .where(MappingJob.is_deleted == False)
        .order_by(MappingJob.created_at.desc())
        .limit(1)
    )
    latest_job = result.scalar_one_or_none()
    
    # Determine node statuses based on job and data state
    has_job = latest_job is not None
    job_status = latest_job.status if latest_job else None
    
    # Get mapping counts
    result = await db.execute(
        select(func.count()).select_from(TableMapping)
        .where(TableMapping.is_deleted == False)
    )
    total_mappings = result.scalar() or 0
    
    # Pipeline node execution stats
    node_stats = {
        "parse_ddl": {
            "executed": total_tables > 0,
            "processed": total_tables,
            "status": "completed" if total_tables > 0 else "pending"
        },
        "index_ttl": {
            "executed": ontology_classes > 0,
            "processed": ontology_classes,
            "status": "completed" if ontology_classes > 0 else "pending"
        },
        "fetch_batch": {
            "executed": has_job and total_mappings > 0,
            "processed": total_mappings,
            "status": "completed" if (has_job and total_mappings > 0) else "pending"
        },
        "retrieve_candidates": {
            "executed": has_job and total_mappings > 0,
            "processed": total_mappings,
            "status": "completed" if (has_job and total_mappings > 0) else "pending"
        },
        "mapping_llm": {
            "executed": has_job and total_mappings > 0,
            "processed": total_mappings,
            "status": "completed" if (has_job and total_mappings > 0) else "pending"
        },
        "critic": {
            "executed": has_job and job_status in ['completed', 'running'],
            "processed": total_mappings if has_job and job_status in ['completed', 'running'] else 0,
            "status": "completed" if (has_job and job_status == 'completed') else ("running" if has_job and job_status == 'running' else "pending")
        },
        "check_revision": {
            "executed": has_job and job_status == 'completed',
            "processed": total_mappings if has_job and job_status == 'completed' else 0,
            "status": "completed" if (has_job and job_status == 'completed') else "pending"
        },
        "revision": {
            "executed": has_job and job_status == 'completed',
            "processed": total_mappings if has_job and job_status == 'completed' else 0,
            "status": "completed" if (has_job and job_status == 'completed') else "pending"
        },
        "report": {
            "executed": has_job and job_status == 'completed',
            "processed": total_mappings if has_job and job_status == 'completed' else 0,
            "status": "completed" if (has_job and job_status == 'completed') else "pending"
        },
    }
    
    unmappable_tables = table_status_counts.get('unmappable', 0)
    
    return {
        "code": 0,
        "data": {
            "total_tables": total_tables,
            "mapped_tables": mapped_tables,
            "pending_tables": pending_tables,
            "total_fields": total_fields,
            "mapped_fields": 0,
            "ontology_classes": ontology_classes,
            "stages": {
                "rule_match": 0,
                "vector_search": 0,
                "llm_mapping": 0,
                "ignored": unmappable_tables,
            },
            "pipeline_nodes": node_stats,
        }
    }


@router.get("/export")
async def export_mappings(
    db: Optional[str] = None,
    mapping_status: Optional[str] = None,
    db_session: AsyncSession = Depends(get_db),
):
    """Export mapping results as JSON."""
    # TODO: Implement export
    return {"code": 0, "data": []}


@router.post("/ttl/index")
async def trigger_ttl_index(db: AsyncSession = Depends(get_db)):
    """Trigger TTL index build."""
    # TODO: Implement TTL index trigger
    return {"code": 0, "message": "TTL indexing started"}


@router.get("/ttl/index/status")
async def get_ttl_index_status(db: AsyncSession = Depends(get_db)):
    """Get TTL index status."""
    # TODO: Implement TTL index status
    return {"code": 0, "data": {"status": "idle"}}
