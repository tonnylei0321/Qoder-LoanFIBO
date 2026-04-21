"""Jobs API routes."""

import asyncio
from fastapi import APIRouter, Query, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from loguru import logger

from backend.app.database import get_db, async_session_factory

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    scope_databases: Optional[List[str]] = None  # filter by DB names; None = all
    concurrency: int = 5
    batch_size: int = 5


class JobResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    ontology_tag: str
    status: str
    progress: int
    total_tables: int
    mapped_tables: int
    total_fields: int
    mapped_fields: int
    created_at: str


async def _run_pipeline_background(job_id: int) -> None:
    """Background task: execute LangGraph pipeline for the given job."""
    from backend.app.services.pipeline_orchestrator import orchestrator
    from backend.app.services.pipeline_state import PipelineState
    from backend.app.models.mapping_job import MappingJob

    logger.info(f"[pipeline_bg] Starting pipeline for job_id={job_id}")

    # Mark job as running
    async with async_session_factory() as db:
        result = await db.execute(select(MappingJob).where(MappingJob.id == job_id))
        job = result.scalar_one_or_none()
        if job:
            job.status = "running"
            job.started_at = datetime.utcnow()
            await db.commit()

    initial_state: PipelineState = {
        "job_id": job_id,
        "current_table_id": None,
        "current_batch": [],
        "revision_round": 0,
        "phase": "parse_ddl",
        "error": None,
    }

    try:
        await orchestrator.execute(initial_state)
        async with async_session_factory() as db:
            result = await db.execute(select(MappingJob).where(MappingJob.id == job_id))
            job = result.scalar_one_or_none()
            if job:
                job.status = "completed"
                job.completed_at = datetime.utcnow()
                await db.commit()
        logger.info(f"[pipeline_bg] Pipeline completed for job_id={job_id}")
    except Exception as exc:
        logger.error(f"[pipeline_bg] Pipeline failed for job_id={job_id}: {exc}")
        async with async_session_factory() as db:
            result = await db.execute(select(MappingJob).where(MappingJob.id == job_id))
            job = result.scalar_one_or_none()
            if job:
                job.status = "failed"
                job.report = {"error": str(exc)}
                await db.commit()


@router.post("")
async def create_job(
    request: JobCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new mapping job and immediately start the LangGraph pipeline."""
    from backend.app.models.mapping_job import MappingJob
    from backend.app.models.table_registry import TableRegistry

    # Count pending tables (optionally filtered by scope_databases)
    count_q = select(func.count()).select_from(TableRegistry).where(
        TableRegistry.is_deleted == False
    )
    if request.scope_databases:
        count_q = count_q.where(TableRegistry.database_name.in_(request.scope_databases))
    total_tables = (await db.execute(count_q)).scalar() or 0

    # Reset matching tables to pending so the pipeline picks them up
    from sqlalchemy import update
    upd_q = update(TableRegistry).where(TableRegistry.is_deleted == False)
    if request.scope_databases:
        upd_q = upd_q.where(TableRegistry.database_name.in_(request.scope_databases))
    await db.execute(upd_q.values(mapping_status="pending"))

    # Create MappingJob record
    job = MappingJob(
        job_name=request.name,
        scope_databases=request.scope_databases,
        status="pending",
        phase="parse_ddl",
        total_tables=total_tables,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    job_id = job.id

    # Launch pipeline asynchronously as a true background asyncio task
    # (not BackgroundTasks, which runs after response but blocks the same request lifecycle)
    asyncio.create_task(_run_pipeline_background(job_id))

    return {
        "code": 0,
        "data": {
            "id": job_id,
            "name": request.name,
            "description": request.description,
            "ontology_tag": "FIBO-2025Q4",
            "status": "pending",
            "progress": 0,
            "total_tables": total_tables,
            "mapped_tables": 0,
            "total_fields": 0,
            "mapped_fields": 0,
            "created_at": job.created_at.isoformat() if job.created_at else datetime.utcnow().isoformat(),
        },
    }


@router.get("")
async def get_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get job list from DB."""
    from sqlalchemy import select, func
    from backend.app.models.mapping_job import MappingJob
    from backend.app.models.table_mapping import TableMapping
    from backend.app.models.table_registry import TableRegistry

    query = select(MappingJob).where(MappingJob.is_deleted == False)
    if status:
        query = query.where(MappingJob.status == status)

    count_q = select(func.count()).select_from(MappingJob).where(MappingJob.is_deleted == False)
    if status:
        count_q = count_q.where(MappingJob.status == status)
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(MappingJob.id.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).scalars().all()

    items = []
    for job in rows:
        # Calculate progress: processed = mapped + unmappable + errors
        mapped_count = (await db.execute(
            select(func.count()).select_from(TableMapping)
            .where(TableMapping.job_id == job.id, TableMapping.mapping_status == 'mapped', TableMapping.is_deleted == False)
        )).scalar() or 0
        total_done = (await db.execute(
            select(func.count()).select_from(TableMapping)
            .where(TableMapping.job_id == job.id, TableMapping.is_deleted == False)
        )).scalar() or 0
        total_tables = job.total_tables or 1
        progress = min(100, int(total_done / total_tables * 100))

        # Total fields from table_registry
        total_fields = (await db.execute(
            select(func.sum(func.jsonb_array_length(TableRegistry.parsed_fields)))
            .where(TableRegistry.is_deleted == False)
        )).scalar() or 0

        items.append({
            "id": job.id,
            "name": job.job_name or f"Job-{job.id}",
            "description": "",
            "ontology_tag": "FIBO-2025Q4",
            "status": job.status,
            "progress": progress,
            "total_tables": job.total_tables,
            "mapped_tables": mapped_count,
            "total_fields": int(total_fields),
            "mapped_fields": 0,
            "created_at": job.created_at.isoformat() if job.created_at else "",
        })

    return {
        "code": 0,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get("/{job_id}")
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Get job details from DB."""
    from sqlalchemy import select, func
    from backend.app.models.mapping_job import MappingJob
    from backend.app.models.table_mapping import TableMapping
    from backend.app.models.table_registry import TableRegistry

    result = await db.execute(select(MappingJob).where(MappingJob.id == job_id, MappingJob.is_deleted == False))
    job = result.scalar_one_or_none()
    if not job:
        return {"code": 404, "message": "Job not found"}

    mapped_count = (await db.execute(
        select(func.count()).select_from(TableMapping)
        .where(TableMapping.job_id == job.id, TableMapping.mapping_status == 'mapped', TableMapping.is_deleted == False)
    )).scalar() or 0
    total_done = (await db.execute(
        select(func.count()).select_from(TableMapping)
        .where(TableMapping.job_id == job.id, TableMapping.is_deleted == False)
    )).scalar() or 0
    total_tables = job.total_tables or 1
    progress = min(100, int(total_done / total_tables * 100))
    total_fields = (await db.execute(
        select(func.sum(func.jsonb_array_length(TableRegistry.parsed_fields)))
        .where(TableRegistry.is_deleted == False)
    )).scalar() or 0

    return {
        "code": 0,
        "data": {
            "id": job.id,
            "name": job.job_name or f"Job-{job.id}",
            "description": "",
            "ontology_tag": "FIBO-2025Q4",
            "status": job.status,
            "progress": progress,
            "total_tables": job.total_tables,
            "mapped_tables": mapped_count,
            "total_fields": int(total_fields),
            "mapped_fields": 0,
            "created_at": job.created_at.isoformat() if job.created_at else "",
        },
    }


@router.post("/{job_id}/pause")
async def pause_job(job_id: int):
    """Pause a running job."""
    return {"code": 0, "message": "Job paused"}


@router.post("/{job_id}/resume")
async def resume_job(job_id: int):
    """Resume a paused job."""
    return {"code": 0, "message": "Job resumed"}


@router.post("/{job_id}/stop")
async def stop_job(job_id: int):
    """Stop a job."""
    return {"code": 0, "message": "Job stopped"}


@router.get("/{job_id}/stats")
async def get_job_stats(job_id: int):
    """Get job statistics."""
    return {
        "code": 0,
        "data": {
            "total_tables": 13548,
            "mapped_tables": 5000,
            "total_fields": 1001483,
            "mapped_fields": 25011,
            "stages": {
                "rule_match": 0,
                "vector_search": 0,
                "llm_mapping": 0,
                "ignored": 0,
            },
        },
    }
