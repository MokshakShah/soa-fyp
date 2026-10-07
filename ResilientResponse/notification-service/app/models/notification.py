"""
Notification models — Phase 9.

NotificationStatus uses three values so the state machine is clear:
  PENDING → SENT | FAILED

The older QUEUED/SENDING/DELIVERED/ACKNOWLEDGED values are kept as aliases
so any existing DB records continue to deserialise.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class RecipientType(str, Enum):
    HOSPITAL = "HOSPITAL"
    POLICE = "POLICE"
    RESPONSE_TEAM = "RESPONSE_TEAM"


class NotificationPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class NotificationStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    # Legacy aliases — kept for DB backward-compatibility
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    DELIVERED = "DELIVERED"
    ACKNOWLEDGED = "ACKNOWLEDGED"


# ── Send request ──────────────────────────────────────────────────────────────

class SendNotificationRequest(BaseModel):
    """Posted to POST /api/notifications/send"""
    recipient_type: RecipientType
    recipient_id: Optional[str] = Field(None, description="ID in Hospital/Police/Resource Service")
    recipient_name: str = Field(..., min_length=1)
    phone_number: str = Field(..., min_length=5)
    message: str = Field(..., min_length=1)
    incident_id: Optional[str] = None
    workflow_id: Optional[str] = None
    priority: NotificationPriority = NotificationPriority.NORMAL


# ── Response ──────────────────────────────────────────────────────────────────

class NotificationResponse(BaseModel):
    id: str
    recipient_type: RecipientType
    recipient_id: Optional[str]
    recipient_name: str
    phone_number: str
    message: str
    incident_id: Optional[str]
    workflow_id: Optional[str]
    priority: NotificationPriority
    status: NotificationStatus
    provider: str
    sent_at: Optional[datetime]
    failure_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
