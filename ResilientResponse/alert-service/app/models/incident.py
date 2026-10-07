from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class IncidentCreate(BaseModel):
    alert_id: Optional[str] = None
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    disaster_type: str = Field(..., min_length=1)
    severity: str = Field(default="MEDIUM")
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: IncidentStatus = IncidentStatus.OPEN


class IncidentResponse(BaseModel):
    id: str
    alert_id: Optional[str]
    title: str
    description: Optional[str]
    disaster_type: str
    severity: str
    location_name: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    status: IncidentStatus
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
