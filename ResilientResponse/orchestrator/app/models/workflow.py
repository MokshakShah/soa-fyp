from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class WorkflowStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    RECOVERING = "RECOVERING"


class WorkflowEventStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class WorkflowResponse(BaseModel):
    id: str
    incident_id: Optional[str]
    workflow_type: str
    status: WorkflowStatus
    current_step: int
    total_steps: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class WorkflowEventResponse(BaseModel):
    id: str
    workflow_id: str
    service: str
    action: str
    status: WorkflowEventStatus
    error: Optional[str]
    duration_ms: Optional[int]
    timestamp: datetime


class ClassificationSnapshot(BaseModel):
    alert_id: Optional[str] = None
    disaster_type: str
    severity: Optional[str] = "MEDIUM"
    confidence: Optional[float] = None
    matched_rules: list[str] = []
    reason: Optional[str] = None


class ExecuteWorkflowRequest(BaseModel):
    """Trigger workflow execution from a classified incident."""
    incident_id: str
    disaster_type: str
    severity: Optional[str] = "MEDIUM"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    classification: Optional[ClassificationSnapshot] = None
    expand_search: bool = False
    search_timeout_seconds: int = 25
