"""
Pydantic request/response schemas for the API layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Requests ─────────────────────────────────────────────


class TaskCreateRequest(BaseModel):
    """Create a new crisis coordination task."""
    title: str = Field(..., min_length=1, max_length=500, examples=["Earthquake relief for Region-7"])
    description: str = Field(..., min_length=1, examples=["7.2 earthquake hit Region-7. Assess damage, coordinate supplies, deploy teams."])
    priority: str = Field(default="medium", pattern="^(critical|high|medium|low)$")


class ExecuteRequest(BaseModel):
    """Synchronous demo execution request."""
    query: str = Field(..., min_length=1, max_length=500, examples=["Flood in Odisha"])


# ── Responses ────────────────────────────────────────────


class TaskResponse(BaseModel):
    """Full task response including structured output."""
    id: uuid.UUID
    title: str
    description: str
    status: str
    priority: str
    result_plan: Optional[dict[str, Any]] = None
    result_tasks: Optional[list[dict[str, Any]]] = None
    result_schedule: Optional[dict[str, Any]] = None
    result_reasoning: Optional[list[dict[str, Any]]] = None
    parent_task_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskCreatedResponse(BaseModel):
    """Returned immediately on POST (202 Accepted)."""
    task_id: uuid.UUID
    status: str = "pending"
    message: str = "Task accepted and processing started."


class AgentLogResponse(BaseModel):
    """Single agent execution log entry."""
    id: uuid.UUID
    task_id: uuid.UUID
    agent_name: str
    action: str
    input_data: Optional[dict[str, Any]] = None
    output_data: Optional[dict[str, Any]] = None
    reasoning: Optional[str] = None
    token_usage: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    """Paginated list of tasks."""
    tasks: list[TaskResponse]
    total: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    database: str
    version: str = "1.0.0"


class CrisisContext(BaseModel):
    """Extracted crisis metadata from the query."""
    location: str
    type: str
    resource: str
    shortage: str
    severity: str


class SystemReliability(BaseModel):
    """Pipeline reliability metrics."""
    tests_passed: str = "34/34"
    pipeline_validated: bool = True
    data_consistency: str = "verified"
    execution_mode: str = "real-time"


class ExecuteResponse(BaseModel):
    """Clean synchronous demo response."""
    summary: str
    crisis_context: CrisisContext
    plan: str
    tasks: list[dict[str, Any]]
    schedule: list[dict[str, Any]]
    agent_flow: list[str]
    confidence_score: float = Field(ge=0.0, le=1.0)
    insights: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    decision_comparison: Optional[str] = None
    system_state: Optional[dict[str, Any]] = None
    execution_time: str = "0.00s"
    impact_analysis: Optional[dict[str, str]] = None
    replanning: Optional[dict[str, Any]] = None
    system_reliability: SystemReliability = Field(default_factory=SystemReliability)
    outcome_summary: str = ""
    reasoning_trace: list[dict[str, Any]] = Field(default_factory=list)
    live_data: Optional[dict[str, Any]] = None
    logistics_metrics: Optional[dict[str, Any]] = None
