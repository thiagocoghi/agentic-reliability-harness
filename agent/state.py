from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExecutionStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CIRCUIT_TRIPPED = "circuit_tripped"
    FAILED = "failed"


class ToolCallRecord(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    output: Optional[Any] = None
    status_code: int = 200
    timestamp_ms: int = 0


class AgentState(BaseModel):
    query: str
    status: ExecutionStatus = ExecutionStatus.IN_PROGRESS
    iteration_count: int = 0
    max_iterations: int = 6
    token_budget_cap: int = 4000
    estimated_tokens_used: int = 0
    circuit_breaker_tripped: bool = False
    breaker_reason: Optional[str] = None
    tool_history: List[ToolCallRecord] = Field(default_factory=list)
    pending_tool_call: Optional[Dict[str, Any]] = None
    investigation_summary: Optional[str] = None
    discrepancy_found: bool = False
    discrepancy_amount: float = 0.0
    recommendation: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
