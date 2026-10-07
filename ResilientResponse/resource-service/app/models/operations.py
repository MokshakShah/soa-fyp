"""Operational models for Phase 6 resource allocate/release."""
from pydantic import BaseModel, Field
from typing import Optional


class AllocateRequest(BaseModel):
    quantity: int = Field(..., ge=1, description="Units to allocate")
    incident_id: Optional[str] = Field(None, description="Optional incident reference")


class ReleaseRequest(BaseModel):
    quantity: int = Field(..., ge=1, description="Units to release")
    incident_id: Optional[str] = Field(None, description="Optional incident reference")


class AllocationResult(BaseModel):
    resource_id: str
    operation: str          # "allocate" | "release"
    quantity: int
    available_before: Optional[int]
    available_after: Optional[int]
    success: bool
    message: str
