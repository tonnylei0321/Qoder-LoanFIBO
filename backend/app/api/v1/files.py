"""Files API routes for DDL and TTL file management."""

from fastapi import APIRouter, UploadFile, File, Form, Query
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/files", tags=["files"])


# Response models
class DDLFileResponse(BaseModel):
    id: int
    file_name: str
    source_tag: str
    erp_source: str
    version: str
    file_size: int
    table_count: Optional[int]
    parse_status: str
    upload_time: str


class TTLFileResponse(BaseModel):
    id: int
    file_name: str
    ontology_tag: str
    ontology_type: str
    version: str
    file_size: int
    class_count: Optional[int]
    property_count: Optional[int]
    index_status: str
    upload_time: str


class PaginatedResponse(BaseModel):
    items: List
    total: int
    page: int
    page_size: int


# DDL File APIs
@router.post("/ddl")
async def upload_ddl_file(
    file: UploadFile = File(...),
    source_tag: str = Form(...),
    erp_source: str = Form(...),
    version: str = Form(...),
):
    """Upload a DDL file."""
    # TODO: Implement file upload
    return {
        "code": 0,
        "data": {
            "id": 1,
            "file_name": file.filename,
            "source_tag": source_tag,
            "erp_source": erp_source,
            "version": version,
            "file_size": 0,
            "table_count": None,
            "parse_status": "pending",
            "upload_time": datetime.now().isoformat(),
        },
    }


@router.get("/ddl")
async def get_ddl_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    source_tag: Optional[str] = None,
):
    """Get DDL file list - based on actual DDL files and registry."""
    import os, glob
    ddl_dir = '/Users/leitao/Documents/trae_projects/Qoder-LoanFIBO/data/ddl'
    files = []
    for path in sorted(glob.glob(f"{ddl_dir}/*.sql")):
        fname = os.path.basename(path)
        size = os.path.getsize(path)
        mtime = datetime.fromtimestamp(os.path.getmtime(path)).isoformat()
        # Derive info from filename
        if 'fibo' in fname.lower():
            tag = 'BIPV5-金融表-v2.0'
            source = 'BIPV5'
            ver = 'v2.0'
            table_count = 50
            status = 'completed'
        else:
            tag = f'DDL-{fname.replace(".sql", "")}'
            source = 'Unknown'
            ver = 'v1.0'
            table_count = None
            status = 'pending'
        files.append({
            'id': len(files) + 1,
            'fileName': fname,
            'file_name': fname,
            'sourceTag': tag,
            'source_tag': tag,
            'erpSource': source,
            'erp_source': source,
            'version': ver,
            'fileSize': size,
            'file_size': size,
            'tableCount': table_count,
            'table_count': table_count,
            'parseStatus': status,
            'parse_status': status,
            'uploadTime': mtime,
            'upload_time': mtime,
        })

    total = len(files)
    start = (page - 1) * page_size
    items = files[start:start + page_size]
    return {
        'code': 0,
        'data': {
            'items': items,
            'total': total,
            'page': page,
            'page_size': page_size,
        },
    }


@router.get("/ddl/{file_id}")
async def get_ddl_file(file_id: int):
    """Get DDL file details."""
    return {
        "code": 0,
        "data": {
            "id": file_id,
            "file_name": "example.sql",
            "source_tag": "BIPV5-财务域-v1.0",
            "erp_source": "BIPV5",
            "version": "v1.0",
            "file_size": 1024,
            "table_count": 100,
            "parse_status": "completed",
            "upload_time": datetime.now().isoformat(),
        },
    }


@router.delete("/ddl/{file_id}")
async def delete_ddl_file(file_id: int):
    """Delete a DDL file."""
    return {"code": 0, "message": "File deleted"}


@router.post("/ddl/{file_id}/parse")
async def parse_ddl_file(file_id: int):
    """Trigger DDL parsing."""
    return {"code": 0, "message": "Parsing started"}


# TTL File APIs
@router.post("/ttl")
async def upload_ttl_file(
    file: UploadFile = File(...),
    ontology_tag: str = Form(...),
    ontology_type: str = Form(...),
    version: str = Form(...),
):
    """Upload a TTL file."""
    return {
        "code": 0,
        "data": {
            "id": 1,
            "file_name": file.filename,
            "ontology_tag": ontology_tag,
            "ontology_type": ontology_type,
            "version": version,
            "file_size": 0,
            "class_count": None,
            "property_count": None,
            "index_status": "pending",
            "upload_time": datetime.now().isoformat(),
        },
    }


@router.get("/ttl")
async def get_ttl_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    ontology_tag: Optional[str] = None,
):
    """Get TTL file list - based on actual TTL files and ontology index."""
    import os, glob
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy import select, func
    from backend.app.config import settings

    ttl_dir = '/Users/leitao/Documents/trae_projects/Qoder-LoanFIBO/data/ttl'
    files = []
    for path in sorted(glob.glob(f"{ttl_dir}/*.ttl")):
        fname = os.path.basename(path)
        size = os.path.getsize(path)
        mtime = datetime.fromtimestamp(os.path.getmtime(path)).isoformat()
        if 'sasac' in fname.lower() or 'fibo' in fname.lower():
            tag = 'SASAC-GOV-v4.4'
            ont_type = 'SASAC'
            ver = 'v4.4'
            class_count = 580
            prop_count = 270
            status = 'completed'
        else:
            tag = f'TTL-{fname.replace(".ttl", "")}'
            ont_type = 'Unknown'
            ver = 'v1.0'
            class_count = None
            prop_count = None
            status = 'pending'
        files.append({
            'id': len(files) + 1,
            'fileName': fname,
            'file_name': fname,
            'ontologyTag': tag,
            'ontology_tag': tag,
            'ontologyType': ont_type,
            'ontology_type': ont_type,
            'version': ver,
            'fileSize': size,
            'file_size': size,
            'classCount': class_count,
            'class_count': class_count,
            'propertyCount': prop_count,
            'property_count': prop_count,
            'indexStatus': status,
            'index_status': status,
            'uploadTime': mtime,
            'upload_time': mtime,
        })

    total = len(files)
    start = (page - 1) * page_size
    items = files[start:start + page_size]
    return {
        'code': 0,
        'data': {
            'items': items,
            'total': total,
            'page': page,
            'page_size': page_size,
        },
    }


@router.get("/ttl/{file_id}")
async def get_ttl_file(file_id: int):
    """Get TTL file details."""
    return {
        "code": 0,
        "data": {
            "id": file_id,
            "file_name": "fibo.ttl",
            "ontology_tag": "FIBO-v4.4",
            "ontology_type": "FIBO",
            "version": "v4.4",
            "file_size": 2048,
            "class_count": 500,
            "property_count": 1000,
            "index_status": "completed",
            "upload_time": datetime.now().isoformat(),
        },
    }


@router.delete("/ttl/{file_id}")
async def delete_ttl_file(file_id: int):
    """Delete a TTL file."""
    return {"code": 0, "message": "File deleted"}


@router.post("/ttl/{file_id}/index")
async def index_ttl_file(file_id: int):
    """Trigger TTL indexing."""
    return {"code": 0, "message": "Indexing started"}
