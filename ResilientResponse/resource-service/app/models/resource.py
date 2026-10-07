from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class ResourceStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    DEPLOYED = "DEPLOYED"
    MAINTENANCE = "MAINTENANCE"
    INACTIVE = "INACTIVE"


class ResourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    type: str = Field(..., min_length=1, max_length=100)
    quantity: int = Field(..., ge=0)
    available_quantity: int = Field(..., ge=0)
    unit: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: ResourceStatus = ResourceStatus.AVAILABLE


class ResourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    type: Optional[str] = None
    quantity: Optional[int] = Field(None, ge=0)
    available_quantity: Optional[int] = Field(None, ge=0)
    unit: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: Optional[ResourceStatus] = None


class ResourceResponse(BaseModel):
    id: str
    name: str
    type: str
    quantity: int
    available_quantity: int
    unit: Optional[str]
    location: Optional[str]
    city: Optional[str]
    state: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    status: ResourceStatus
    created_at: datetime
    updated_at: datetime
