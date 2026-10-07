from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
from datetime import datetime
from enum import Enum


class AlertStatus(str, Enum):
    NEW = "NEW"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    # Keep legacy values so existing DB records are still valid
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


class AlertSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ── Normalized alert (stored in MongoDB) ─────────────────────────────────────

class NormalizedAlert(BaseModel):
    """
    The canonical internal alert format.
    All adapters produce this model — the rest of the service never depends
    on source-specific formats.
    """
    external_id: Optional[str] = None
    source: str                              # GDACS | CAP | DEMO
    title: str
    description: Optional[str] = None
    disaster_type: str
    severity: AlertSeverity = AlertSeverity.MEDIUM
    city: Optional[str] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    affected_area: Optional[str] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    source_url: Optional[str] = None
    status: AlertStatus = AlertStatus.NEW
    raw_data: Optional[Dict[str, Any]] = None  # original payload for auditability


# ── Create / response schemas ─────────────────────────────────────────────────

class AlertCreate(BaseModel):
    """Used ONLY for DEMO/test alert creation via the API."""
    external_id: Optional[str] = None
    source: str = Field(default="DEMO")
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    disaster_type: str = Field(..., min_length=1)
    severity: AlertSeverity = AlertSeverity.MEDIUM
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None
    affected_area: Optional[str] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    source_url: Optional[str] = None


class AlertResponse(BaseModel):
    id: str
    external_id: Optional[str]
    source: str
    title: str
    description: Optional[str]
    disaster_type: str
    severity: AlertSeverity
    city: Optional[str] = None
    location_name: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    affected_area: Optional[str] = None
    issued_at: Optional[datetime]
    expires_at: Optional[datetime]
    source_url: Optional[str] = None
    status: AlertStatus
    created_at: datetime
    updated_at: datetime


class FetchResult(BaseModel):
    """Returned by POST /api/alerts/fetch"""
    source: str
    fetched: int
    created: int
    updated: int
    failed: int
    errors: list[str] = []
