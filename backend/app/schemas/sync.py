"""同步相关Schema"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ─── 版本管理 ──────────────────────────────────────────────────

class VersionCreate(BaseModel):
    """创建版本请求"""
    version_tag: str = Field(..., description="版本标签，如 v1.0.0")
    description: Optional[str] = Field(None, description="版本描述")
    snapshot_data: Optional[Dict[str, Any]] = Field(None, description="快照数据（留空自动生成）")
    created_by: Optional[str] = Field(None, description="创建者")


class VersionResponse(BaseModel):
    """版本响应"""
    id: str
    version_tag: str
    description: Optional[str] = None
    status: str
    snapshot_data: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = None
    published_at: Optional[str] = None
    synced_at: Optional[str] = None
    created_at: Optional[str] = None


class VersionPublishRequest(BaseModel):
    """发布版本请求"""
    description: Optional[str] = Field(None, description="发布说明")


# ─── 实例管理 ──────────────────────────────────────────────────

class InstanceCreate(BaseModel):
    """创建 GraphDB 实例请求"""
    name: str = Field(..., description="实例名称")
    server_url: str = Field(..., description="GraphDB 服务器 URL")
    repo_id: str = Field(..., description="仓库 ID")
    domain: Optional[str] = Field(None, description="领域")
    namespace_prefix: str = Field(default="loanfibo", description="命名空间前缀")


class InstanceResponse(BaseModel):
    """实例响应"""
    id: str
    name: str
    server_url: str
    repo_id: str
    domain: Optional[str] = None
    namespace_prefix: str = "loanfibo"
    is_active: bool = True
    created_at: Optional[str] = None


class InstanceHealthResponse(BaseModel):
    """实例健康检查响应"""
    instance_id: str
    status: str  # healthy / unhealthy / unreachable
    repository_size: Optional[int] = None
    statement_count: Optional[int] = None
    last_checked: str


# ─── 同步任务 ──────────────────────────────────────────────────

class SyncTaskCreate(BaseModel):
    """创建同步任务请求"""
    version_id: str = Field(..., description="发布版本 ID")
    instance_id: str = Field(..., description="目标 GraphDB 实例 ID")
    mode: str = Field(default="upsert", description="同步模式: upsert / replace")


class SyncTaskResponse(BaseModel):
    """同步任务响应"""
    id: str
    version_id: str
    instance_id: str
    mode: str
    status: str  # pending / running / completed / failed
    progress: float = 0.0
    triples_synced: int = 0
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


# ─── 外键推断 ──────────────────────────────────────────────────

class ForeignKeyInferRequest(BaseModel):
    """外键推断请求"""
    table_names: List[str] = Field(..., description="需要推断外键的表名列表")


class ForeignKeyResponse(BaseModel):
    """外键推断结果响应"""
    id: str
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    confidence: float
    status: str  # pending / approved / rejected
    inferred_by: str  # llm / manual


class ForeignKeyApproveRequest(BaseModel):
    """外键审核请求"""
    action: str = Field(..., description="approve 或 reject")
