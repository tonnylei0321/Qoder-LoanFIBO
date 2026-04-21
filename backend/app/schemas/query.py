"""查询相关Schema"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """NLQ查询请求"""
    tenant_id: str = Field(..., description="租户ID")
    query: str = Field(..., description="自然语言查询文本")
    context: Dict[str, Any] = Field(default_factory=dict, description="查询上下文")
    options: Optional[Dict[str, Any]] = Field(default=None, description="查询选项")


class QueryResponse(BaseModel):
    """NLQ查询响应"""
    status: str = Field(..., description="查询状态")
    data: Optional[Dict[str, Any]] = Field(default=None, description="查询结果数据")
    sql: Optional[str] = Field(default=None, description="生成的SQL")
    message: str = Field(default="", description="状态消息")
    retry_after: Optional[int] = Field(default=None, description="建议重试等待秒数")
    admin_alert: bool = Field(default=False, description="是否需要管理员告警")
