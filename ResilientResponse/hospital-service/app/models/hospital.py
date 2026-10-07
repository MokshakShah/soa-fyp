from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class EntityStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class HospitalCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    registration_number: Optional[str] = None
    phone: str = Field(..., min_length=5)
    emergency_phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: str = Field(..., min_length=1)
    state: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    emergency_capacity: Optional[int] = Field(None, ge=0)
    available_beds: Optional[int] = Field(None, ge=0)
    icu_beds: Optional[int] = Field(None, ge=0)
    status: EntityStatus = EntityStatus.ACTIVE


class HospitalUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    registration_number: Optional[str] = None
    phone: Optional[str] = None
    emergency_phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    emergency_capacity: Optional[int] = Field(None, ge=0)
    available_beds: Optional[int] = Field(None, ge=0)
    icu_beds: Optional[int] = Field(None, ge=0)
    status: Optional[EntityStatus] = None


class HospitalResponse(BaseModel):
    id: str
    name: str
    registration_number: Optional[str]
    phone: str
    emergency_phone: Optional[str]
    email: Optional[str]
    address: Optional[str]
    city: str
    state: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    emergency_capacity: Optional[int]
    available_beds: Optional[int]
    icu_beds: Optional[int]
    status: EntityStatus
    created_at: datetime
    updated_at: datetime
