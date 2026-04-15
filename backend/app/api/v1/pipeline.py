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
async def query_mappings(
    db: Optional[str] = None,
    mapping_status: Optional[str] = None,
    review_status: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    db_session: AsyncSession = Depends(get_db),
):
    """Query mapping results with pagination."""
    # TODO: Implement mapping query
    return {
        "code": 0,
        "data": {
            "items": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
        }
    }


@router.get("/mappings/{table_mapping_id}")
async def get_mapping_detail(table_mapping_id: int, db: AsyncSession = Depends(get_db)):
    """Get detailed mapping for a single table."""
    # TODO: Implement mapping detail query
    return {"code": 0, "data": {}}


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
    """Get mapping statistics overview."""
    # TODO: Implement statistics
    return {
        "code": 0,
        "data": {
            "total_tables": 0,
            "mapped": 0,
            "unmappable": 0,
            "pending": 0,
            "review_breakdown": {},
            "confidence_distribution": {},
            "top_fibo_classes": [],
            "total_tokens_consumed": 0,
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
