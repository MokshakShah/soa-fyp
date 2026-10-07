"""
Operational models for Phase 6 — search and capacity operations.
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class SearchRequest(BaseModel):
    """Used as query params (defined here for documentation)."""
    pass


class ReserveBedsRequest(BaseModel):
    beds: int = Field(..., ge=1, description="Number of beds to reserve")
    incident_id: Optional[str] = Field(None, description="Optional incident reference")


class ReleaseBedsRequest(BaseModel):
    beds: int = Field(..., ge=1, description="Number of beds to release")
    incident_id: Optional[str] = Field(None, description="Optional incident reference")


class CapacityOperationResult(BaseModel):
    hospital_id: str
    operation: str          # "reserve" | "release"
    beds: int
    available_beds_before: Optional[int]
    available_beds_after: Optional[int]
    success: bool
    message: str
