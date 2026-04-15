from typing import TypedDict, Optional, List
from enum import Enum

class PipelinePhase(str, Enum):
    """Pipeline execution phases."""
    PARSE_DDL = "parse_ddl"
    INDEX_TTL = "index_ttl"
    MAPPING = "mapping"
    CRITIC = "critic"
    REVISION = "revision"
    DONE = "done"

class PipelineState(TypedDict):
    """LangGraph Pipeline state definition.
    
    This state is passed between nodes in the LangGraph workflow.
    """
    job_id: int
    current_table_id: Optional[int]
    current_batch: List[int]  # Current batch of table_registry IDs
    revision_round: int  # Current revision round (0-3)
    phase: str  # Current pipeline phase
    error: Optional[str]
