"""规则相关Schema"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RuleCreate(BaseModel):
    """创建规则请求"""
    tenant_id: str = Field(..., description="租户ID")
    name: str = Field(..., description="规则名称")
    rule_type: str = Field(..., description="规则类型")
    definition: Dict[str, Any] = Field(..., description="规则定义")
    priority: int = Field(default=0, description="优先级")
    enabled: bool = Field(default=True, description="是否启用")


class RuleResponse(BaseModel):
    """规则响应"""
    id: str
    tenant_id: str
    name: str
    rule_type: str
    definition: Dict[str, Any]
    priority: int = 0
    enabled: bool = True


class CompileStatusResponse(BaseModel):
    """编译状态响应"""
    tenant_id: str
    status: str
    current_version: Optional[str] = None
    last_compiled_at: Optional[str] = None
    staleness_seconds: int = 0
