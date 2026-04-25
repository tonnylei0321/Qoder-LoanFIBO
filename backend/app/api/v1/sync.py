"""GraphDB 同步 API - 版本管理、实例管理、同步任务"""
import asyncio
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.sync import (
    VersionResponse, VersionPublishRequest, VersionUpdateRequest,
    InstanceCreate, InstanceResponse, InstanceHealthResponse,
    SyncTaskCreate, SyncTaskResponse,
    ForeignKeyInferRequest, ForeignKeyResponse, ForeignKeyApproveRequest,
)
from backend.app.services.sync.version_manager import VersionManager

router = APIRouter()


# ─── 版本管理 ──────────────────────────────────────────────────

@router.post("/versions/upload", response_model=VersionResponse, status_code=status.HTTP_201_CREATED)
async def upload_version_ttl(
    version_tag: str = Form(...),
    description: Optional[str] = Form(None),
    created_by: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """上传 TTL 文件创建版本"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="请选择文件")
    if not file.filename.endswith(('.ttl', '.rdf')):
        raise HTTPException(status_code=400, detail="仅支持 .ttl 或 .rdf 格式文件")

    content = await file.read()
    mgr = VersionManager(db)
    try:
        version = await mgr.create_version_with_ttl(
            version_tag=version_tag,
            ttl_content=content,
            ttl_file_name=file.filename,
            description=description,
            created_by=created_by,
        )
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return _version_to_response(version)


@router.post("/versions", response_model=VersionResponse, status_code=status.HTTP_201_CREATED)
async def create_version(data: dict, db: AsyncSession = Depends(get_db)):
    """创建版本快照（从映射数据自动采集）"""
    from backend.app.schemas.sync import VersionCreate as VC
    from pydantic import ValidationError
    try:
        parsed = VC(**data)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    mgr = VersionManager(db)
    try:
        version = await mgr.create_snapshot(
            version_tag=parsed.version_tag,
            description=parsed.description,
            snapshot_data=parsed.snapshot_data,
            created_by=parsed.created_by,
        )
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return _version_to_response(version)


@router.get("/versions", response_model=List[VersionResponse])
async def list_versions(
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """列出版本"""
    mgr = VersionManager(db)
    versions = await mgr.list_versions(status=status_filter, limit=limit, offset=offset)
    return [_version_to_response(v) for v in versions]


@router.get("/versions/{version_id}", response_model=VersionResponse)
async def get_version(version_id: str, db: AsyncSession = Depends(get_db)):
    """获取版本详情"""
    mgr = VersionManager(db)
    version = await mgr.get_version(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="版本不存在")
    return _version_to_response(version)


@router.patch("/versions/{version_id}/publish", response_model=VersionResponse)
async def publish_version(
    version_id: str,
    data: VersionPublishRequest,
    db: AsyncSession = Depends(get_db),
):
    """发布版本（draft → published）"""
    mgr = VersionManager(db)
    try:
        version = await mgr.publish(version_id, description=data.description)
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return _version_to_response(version)


@router.patch("/versions/{version_id}", response_model=VersionResponse)
async def update_version(
    version_id: str,
    data: VersionUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新版本信息"""
    mgr = VersionManager(db)
    try:
        version = await mgr.update_version(
            version_id=version_id,
            version_tag=data.version_tag,
            description=data.description,
        )
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return _version_to_response(version)


@router.delete("/versions/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_version(version_id: str, db: AsyncSession = Depends(get_db)):
    """删除版本（仅 draft 状态可删）"""
    mgr = VersionManager(db)
    try:
        await mgr.delete_version(version_id)
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


def _version_to_response(v) -> VersionResponse:
    return VersionResponse(
        id=v.id,
        version_tag=v.version_tag,
        description=v.description,
        status=v.status,
        snapshot_data=v.snapshot_data,
        created_by=v.created_by,
        ttl_file_name=v.ttl_file_name,
        ttl_file_size=v.ttl_file_size,
        ttl_valid=v.ttl_valid,
        ttl_validation_msg=v.ttl_validation_msg,
        class_count=v.class_count,
        property_count=v.property_count,
        published_at=v.published_at.isoformat() if v.published_at else None,
        synced_at=v.synced_at.isoformat() if v.synced_at else None,
        created_at=v.created_at.isoformat() if v.created_at else None,
    )


# ─── 实例管理 ──────────────────────────────────────────────────

@router.post("/instances", response_model=InstanceResponse, status_code=status.HTTP_201_CREATED)
async def create_instance(data: InstanceCreate, db: AsyncSession = Depends(get_db)):
    """创建 GraphDB 实例"""
    from backend.app.models.graphdb_instance import GraphDBInstance
    instance = GraphDBInstance(
        name=data.name,
        server_url=data.server_url,
        repo_id=data.repo_id,
        domain=data.domain,
        namespace_prefix=data.namespace_prefix,
        version_id=data.version_id,
    )
    db.add(instance)
    await db.commit()
    await db.refresh(instance)
    return _instance_to_response(instance)


@router.get("/instances", response_model=List[InstanceResponse])
async def list_instances(db: AsyncSession = Depends(get_db)):
    """列出 GraphDB 实例"""
    from sqlalchemy import select
    from backend.app.models.graphdb_instance import GraphDBInstance
    result = await db.execute(select(GraphDBInstance).order_by(GraphDBInstance.created_at.desc()))
    instances = result.scalars().all()
    return [_instance_to_response(i) for i in instances]


@router.get("/instances/{instance_id}", response_model=InstanceResponse)
async def get_instance(instance_id: str, db: AsyncSession = Depends(get_db)):
    """获取实例详情"""
    from sqlalchemy import select
    from backend.app.models.graphdb_instance import GraphDBInstance
    result = await db.execute(select(GraphDBInstance).where(GraphDBInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        raise HTTPException(status_code=404, detail="实例不存在")
    return _instance_to_response(instance)


@router.put("/instances/{instance_id}", response_model=InstanceResponse)
async def update_instance(instance_id: str, data: InstanceCreate, db: AsyncSession = Depends(get_db)):
    """更新 GraphDB 实例"""
    from sqlalchemy import select
    from backend.app.models.graphdb_instance import GraphDBInstance
    result = await db.execute(select(GraphDBInstance).where(GraphDBInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        raise HTTPException(status_code=404, detail="实例不存在")
    instance.name = data.name
    instance.server_url = data.server_url
    instance.repo_id = data.repo_id
    instance.domain = data.domain
    instance.namespace_prefix = data.namespace_prefix
    instance.version_id = data.version_id
    await db.commit()
    await db.refresh(instance)
    return _instance_to_response(instance)


@router.delete("/instances/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_instance(instance_id: str, db: AsyncSession = Depends(get_db)):
    """删除 GraphDB 实例"""
    from sqlalchemy import select
    from backend.app.models.graphdb_instance import GraphDBInstance
    result = await db.execute(select(GraphDBInstance).where(GraphDBInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        raise HTTPException(status_code=404, detail="实例不存在")
    instance.is_active = False
    await db.commit()


@router.get("/instances/{instance_id}/health", response_model=InstanceHealthResponse)
async def check_instance_health(instance_id: str, db: AsyncSession = Depends(get_db)):
    """检查 GraphDB 实例健康状态"""
    from sqlalchemy import select
    from backend.app.models.graphdb_instance import GraphDBInstance
    result = await db.execute(select(GraphDBInstance).where(GraphDBInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        raise HTTPException(status_code=404, detail="实例不存在")

    from datetime import datetime, timezone
    try:
        from backend.app.services.sync.instance_manager import InstanceManager
        mgr = InstanceManager(db)
        health = await mgr.health_check(instance)
        return health
    except Exception as e:
        return InstanceHealthResponse(
            instance_id=instance_id,
            status="unreachable",
            last_checked=datetime.now(timezone.utc).isoformat(),
        )


def _instance_to_response(i) -> InstanceResponse:
    return InstanceResponse(
        id=i.id,
        name=i.name,
        server_url=i.server_url,
        repo_id=i.repo_id,
        domain=i.domain,
        namespace_prefix=i.namespace_prefix,
        version_id=i.version_id,
        is_active=i.is_active,
        created_at=i.created_at.isoformat() if i.created_at else None,
    )


# ─── 同步任务 ──────────────────────────────────────────────────

@router.post("/tasks", response_model=SyncTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_sync_task(data: SyncTaskCreate, db: AsyncSession = Depends(get_db)):
    """创建同步任务并自动异步执行"""
    from backend.app.services.sync.sync_scheduler import SyncScheduler
    scheduler = SyncScheduler(db)
    try:
        task = await scheduler.create_task(
            version_id=data.version_id,
            instance_id=data.instance_id,
            mode=data.mode,
        )
        await db.commit()
        # 异步执行同步任务
        asyncio.create_task(_run_sync_task(task.id, db))
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return _task_to_response(task)


async def _run_sync_task(task_id: str, db: AsyncSession):
    """后台执行同步任务"""
    from backend.app.database import async_session_factory
    from backend.app.services.sync.sync_scheduler import SyncScheduler
    async with async_session_factory() as new_db:
        scheduler = SyncScheduler(new_db)
        try:
            await scheduler.execute_sync(task_id)
            await new_db.commit()
        except Exception as e:
            await new_db.rollback()


@router.get("/tasks", response_model=List[SyncTaskResponse])
async def list_sync_tasks(db: AsyncSession = Depends(get_db)):
    """列出同步任务"""
    from sqlalchemy import select
    from backend.app.models.sync_task import SyncTask
    result = await db.execute(select(SyncTask).order_by(SyncTask.created_at.desc()))
    tasks = result.scalars().all()
    return [_task_to_response(t) for t in tasks]


@router.get("/tasks/{task_id}", response_model=SyncTaskResponse)
async def get_sync_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """获取同步任务详情"""
    from sqlalchemy import select
    from backend.app.models.sync_task import SyncTask
    result = await db.execute(select(SyncTask).where(SyncTask.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _task_to_response(task)


@router.get("/tasks/{task_id}/progress", response_model=SyncTaskResponse)
async def get_sync_task_progress(task_id: str, db: AsyncSession = Depends(get_db)):
    """获取同步任务进度"""
    from sqlalchemy import select
    from backend.app.models.sync_task import SyncTask
    result = await db.execute(select(SyncTask).where(SyncTask.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _task_to_response(task)


def _task_to_response(t) -> SyncTaskResponse:
    return SyncTaskResponse(
        id=t.id,
        version_id=t.version_id,
        instance_id=t.instance_id,
        mode=t.mode,
        status=t.status,
        progress=t.progress,
        triples_synced=t.triples_synced,
        error_message=t.error_message,
        created_at=t.created_at.isoformat() if t.created_at else None,
        completed_at=t.completed_at.isoformat() if t.completed_at else None,
    )


# ─── 外键推断 ──────────────────────────────────────────────────

@router.post("/infer-foreign-keys", response_model=List[ForeignKeyResponse])
async def infer_foreign_keys(data: ForeignKeyInferRequest, db: AsyncSession = Depends(get_db)):
    """LLM 外键推断"""
    from backend.app.services.sync.foreign_key_inferrer import ForeignKeyInferrer
    inferrer = ForeignKeyInferrer(db)
    try:
        results = await inferrer.infer_from_schema(data.table_names)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"外键推断失败: {e}")
    return [_fk_to_response(fk) for fk in results]


@router.get("/foreign-keys", response_model=List[ForeignKeyResponse])
async def list_foreign_keys(
    source_table: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """列出外键推断结果"""
    from sqlalchemy import select
    from backend.app.models.table_foreign_key import TableForeignKey
    stmt = select(TableForeignKey).order_by(TableForeignKey.created_at.desc())
    if source_table:
        stmt = stmt.where(TableForeignKey.source_table == source_table)
    if status_filter:
        stmt = stmt.where(TableForeignKey.status == status_filter)
    result = await db.execute(stmt)
    keys = result.scalars().all()
    return [_fk_to_response(fk) for fk in keys]


@router.patch("/foreign-keys/{fk_id}", response_model=ForeignKeyResponse)
async def approve_foreign_key(fk_id: str, data: ForeignKeyApproveRequest, db: AsyncSession = Depends(get_db)):
    """审核外键推断结果"""
    from sqlalchemy import select
    from backend.app.models.table_foreign_key import TableForeignKey
    result = await db.execute(select(TableForeignKey).where(TableForeignKey.id == fk_id))
    fk = result.scalar_one_or_none()
    if fk is None:
        raise HTTPException(status_code=404, detail="外键记录不存在")

    if data.action == "approve":
        fk.status = "approved"
    elif data.action == "reject":
        fk.status = "rejected"
    else:
        raise HTTPException(status_code=400, detail="action 必须为 approve 或 reject")
    await db.commit()
    await db.refresh(fk)
    return _fk_to_response(fk)


def _fk_to_response(fk) -> ForeignKeyResponse:
    return ForeignKeyResponse(
        id=fk.id,
        source_table=fk.source_table,
        source_column=fk.source_column,
        target_table=fk.target_table,
        target_column=fk.target_column,
        confidence=fk.confidence,
        status=fk.status,
        inferred_by=fk.inferred_by,
    )
