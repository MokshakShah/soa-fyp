from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class ServiceStatus(str, Enum):
    UP = "UP"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    RECOVERING = "RECOVERING"
    UNKNOWN = "UNKNOWN"


class InstanceRole(str, Enum):
    PRIMARY = "PRIMARY"
    BACKUP = "BACKUP"


# ── Registration ────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=100)
    instance_id: str = Field(..., min_length=1, max_length=100)
    base_url: str = Field(..., min_length=1)
    version: str = Field(default="0.1.0")
    instance_role: InstanceRole = InstanceRole.PRIMARY
    metadata: Optional[Dict[str, Any]] = None


class RegisterResponse(BaseModel):
    success: bool
    message: str
    instance_id: str
    service_name: str


# ── Registry record (DB shape returned to API consumers) ────────────────────

class RegistryRecord(BaseModel):
    id: str
    service_name: str
    instance_id: str
    base_url: str
    status: ServiceStatus
    version: str
    instance_role: InstanceRole
    last_heartbeat: Optional[datetime]
    registered_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = None


# ── Health record ────────────────────────────────────────────────────────────

class HealthRecord(BaseModel):
    id: str
    service_name: str
    instance_id: str
    status: ServiceStatus
    response_time_ms: Optional[int]
    last_checked: Optional[datetime]
    error: Optional[str]
    details: Optional[Dict[str, Any]] = None


# ── Discovery ────────────────────────────────────────────────────────────────

class DiscoveryInstance(BaseModel):
    instance_id: str
    base_url: str
    status: ServiceStatus
    instance_role: InstanceRole
    version: str
    response_time_ms: Optional[int]
    last_heartbeat: Optional[datetime]


class DiscoveryResponse(BaseModel):
    service_name: str
    instances: list[DiscoveryInstance]
    selected: Optional[DiscoveryInstance] = None
