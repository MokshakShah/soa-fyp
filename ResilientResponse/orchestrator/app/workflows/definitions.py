"""
Phase 7 — disaster workflow definitions.

Each workflow lists ordered steps (service + action). Parameters are merged at runtime
from classification severity and incident location.
"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class WorkflowStepDef:
    service: str
    action: str
    critical: bool
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowDefinition:
    workflow_type: str
    steps: tuple[WorkflowStepDef, ...]


def _base_steps(resource_type: str, reserve_beds: int, allocate_qty: int) -> tuple[WorkflowStepDef, ...]:
    return (
        WorkflowStepDef("orchestrator", "record_classification", critical=False),
        WorkflowStepDef(
            "hospital-service", "search_hospitals", critical=False,
            params={"radius_km": 50},
        ),
        WorkflowStepDef(
            "hospital-service", "reserve_hospital_beds", critical=True,
            params={"beds": reserve_beds},
        ),
        WorkflowStepDef(
            "hospital-service", "search_police", critical=False,
            params={"radius_km": 50},
        ),
        WorkflowStepDef(
            "resource-service", "search_resources", critical=False,
            params={"resource_type": resource_type, "radius_km": 100},
        ),
        WorkflowStepDef(
            "resource-service", "allocate_resource", critical=True,
            params={"quantity": allocate_qty},
        ),
        WorkflowStepDef(
            "route-service", "plan_route", critical=False,
            params={},
        ),
        WorkflowStepDef(
            "notification-service", "dispatch_notification", critical=False,
            params={},
        ),
    )


WORKFLOW_DEFINITIONS: dict[str, WorkflowDefinition] = {
    "FLOOD": WorkflowDefinition("FLOOD", _base_steps("WATER", 8, 2)),
    "CYCLONE": WorkflowDefinition("CYCLONE", _base_steps("RESCUE_VEHICLE", 10, 1)),
    "EARTHQUAKE": WorkflowDefinition("EARTHQUAKE", _base_steps("RESCUE_VEHICLE", 15, 2)),
    "LANDSLIDE": WorkflowDefinition("LANDSLIDE", _base_steps("RESCUE_VEHICLE", 6, 1)),
    "CHEMICAL": WorkflowDefinition("CHEMICAL", _base_steps("MEDICAL_KIT", 5, 3)),
    "FIRE": WorkflowDefinition("FIRE", _base_steps("AMBULANCE", 8, 2)),
    "DROUGHT": WorkflowDefinition("DROUGHT", _base_steps("WATER", 5, 2)),
    "VOLCANO": WorkflowDefinition("VOLCANO", _base_steps("RESCUE_VEHICLE", 12, 2)),
    "TSUNAMI": WorkflowDefinition("TSUNAMI", _base_steps("RESCUE_VEHICLE", 12, 2)),
    "STORM": WorkflowDefinition("STORM", _base_steps("RESCUE_VEHICLE", 8, 1)),
    "OTHER": WorkflowDefinition("OTHER", _base_steps("MEDICAL_KIT", 2, 1)),
}

SUPPORTED_DISASTER_TYPES = frozenset(WORKFLOW_DEFINITIONS.keys())


def get_workflow_definition(disaster_type: str) -> Optional[WorkflowDefinition]:
    normalized = disaster_type.upper().strip()
    return WORKFLOW_DEFINITIONS.get({"WILDFIRE": "FIRE"}.get(normalized, normalized))
