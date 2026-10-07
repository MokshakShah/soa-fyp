"""
Pydantic models for the Classification Service.

ClassificationRequest  — what callers send
ClassificationResult   — what the service returns

No external AI or LLM is used. Results are deterministic for the same input.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class DisasterType(str, Enum):
    FLOOD = "FLOOD"
    CYCLONE = "CYCLONE"
    EARTHQUAKE = "EARTHQUAKE"
    LANDSLIDE = "LANDSLIDE"
    CHEMICAL = "CHEMICAL"
    FIRE = "FIRE"
    TSUNAMI = "TSUNAMI"
    VOLCANO = "VOLCANO"
    DROUGHT = "DROUGHT"
    STORM = "STORM"
    UNKNOWN = "UNKNOWN"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ClassificationRequest(BaseModel):
    """
    Inputs accepted from the caller.

    The caller should provide as many fields as available.
    The classifier uses whichever combination yields the best match.
    """
    alert_id: Optional[str] = Field(None, description="Internal alert ID (for tracing)")
    event_type: Optional[str] = Field(None, description="Source event type code, e.g. EQ, TC, FL")
    headline: Optional[str] = Field(None, description="Alert headline / title")
    description: Optional[str] = Field(None, description="Full alert description")
    severity: Optional[str] = Field(None, description="Source severity: LOW | MEDIUM | HIGH | CRITICAL | Red | Orange | Green | Extreme | Severe | Moderate | Minor")
    urgency: Optional[str] = Field(None, description="CAP urgency: Immediate | Expected | Future | Past | Unknown")
    certainty: Optional[str] = Field(None, description="CAP certainty: Observed | Likely | Possible | Unlikely | Unknown")
    affected_area: Optional[str] = Field(None, description="Free-text affected area description")
    source: Optional[str] = Field(None, description="Alert source: GDACS | CAP | DEMO | etc.")


class ClassificationResult(BaseModel):
    """
    Output of the classification engine.

    Fully transparent: matched_rules and reason explain every decision.
    """
    alert_id: Optional[str]
    disaster_type: DisasterType
    severity: Severity
    confidence: float = Field(..., ge=0.0, le=1.0, description="Rule match confidence 0.0–1.0")
    matched_rules: List[str] = Field(default_factory=list, description="Names of rules that fired")
    reason: str = Field(..., description="Human-readable explanation of the classification")
