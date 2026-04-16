"""Jobs API routes."""

from fastapi import APIRouter, Query
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    ddl_file_id: int
    ttl_file_id: int
    concurrency: int = 5
    batch_size: int = 5


class JobResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    ddl_file_id: int
    ddl_file_tag: str
    ttl_file_id: int
    ttl_file_tag: str
    status: str
    progress: int
    total_tables: int
    mapped_tables: int
    total_fields: int
    mapped_fields: int
    created_at: str


@router.post("")
async def create_job(request: JobCreateRequest):
    """Create a new mapping job."""
    return {
        "code": 0,
        "data": {
            "id": 1,
            "name": request.name,
            "description": request.description,
            "ddl_file_id": request.ddl_file_id,
            "ddl_file_tag": "BIPV5-财务域-v1.0",
            "ttl_file_id": request.ttl_file_id,
            "ttl_file_tag": "FIBO-v4.4",
            "status": "pending",
            "progress": 0,
            "total_tables": 0,
            "mapped_tables": 0,
            "total_fields": 0,
            "mapped_fields": 0,
            "created_at": datetime.now().isoformat(),
        },
    }


@router.get("")
async def get_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
):
    """Get job list."""
    return {
        "code": 0,
        "data": {
            "items": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get("/{job_id}")
async def get_job(job_id: int):
    """Get job details."""
    return {
        "code": 0,
        "data": {
            "id": job_id,
            "name": "示例任务",
            "description": "",
            "ddl_file_id": 1,
            "ddl_file_tag": "BIPV5-财务域-v1.0",
            "ttl_file_id": 1,
            "ttl_file_tag": "FIBO-v4.4",
            "status": "running",
            "progress": 45,
            "total_tables": 13548,
            "mapped_tables": 5000,
            "total_fields": 1001483,
            "mapped_fields": 25011,
            "created_at": datetime.now().isoformat(),
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
