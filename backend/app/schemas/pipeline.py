"""Pipeline Pydantic schemas for request/response validation."""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# Job schemas
class JobCreate(BaseModel):
    """Schema for creating a new mapping job."""
    job_name: Optional[str] = None
    scope_databases: Optional[List[str]] = None
    concurrency: int = Field(default=5, ge=1, le=20)


class JobResponse(BaseModel):
    """Schema for job response."""
    code: int = 0
    data: dict


# Mapping schemas
class MappingUpdate(BaseModel):
    """Schema for updating a table mapping."""
    fibo_class_uri: Optional[str] = None
    confidence_level: Optional[str] = None
    mapping_reason: Optional[str] = None


class FieldMappingUpdate(BaseModel):
    """Schema for updating a field mapping."""
    fibo_property_uri: Optional[str] = None
    proj_ext_uri: Optional[str] = None
    confidence_level: Optional[str] = None
    mapping_reason: Optional[str] = None
