from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class RouteStatus(str, Enum):
    CALCULATED = "CALCULATED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_INPUT = "INVALID_INPUT"


class CalculateRouteRequest(BaseModel):
    origin_lat: float = Field(..., ge=-90, le=90)
    origin_lon: float = Field(..., ge=-180, le=180)
    destination_lat: float = Field(..., ge=-90, le=90)
    destination_lon: float = Field(..., ge=-180, le=180)
    incident_id: Optional[str] = None
    workflow_id: Optional[str] = None

    @model_validator(mode="after")
    def coordinates_not_identical(self):
        if (
            self.origin_lat == self.destination_lat
            and self.origin_lon == self.destination_lon
        ):
            raise ValueError("Origin and destination coordinates must differ")
        return self


class RouteResponse(BaseModel):
    id: str
    incident_id: Optional[str]
    workflow_id: Optional[str]
    origin_lat: float
    origin_lon: float
    destination_lat: float
    destination_lon: float
    distance_km: Optional[float]
    estimated_travel_minutes: Optional[float]
    status: RouteStatus
    provider: str
    geometry: Optional[list[list[float]]] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CalculateRouteResponse(BaseModel):
    route: RouteResponse
    message: str
