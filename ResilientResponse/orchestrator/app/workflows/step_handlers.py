"""
Execute individual workflow step actions against downstream services.
Phase 9: dispatch_notification now calls the Notification Service via discovery.
"""
import logging
import asyncio
import time
from typing import Any

from app.clients.service_client import call_service, ServiceCallError
from app.workflows.definitions import WorkflowStepDef

logger = logging.getLogger("orchestrator.step_handlers")

SEVERITY_BEDS = {"LOW": 10, "MEDIUM": 20, "HIGH": 30, "CRITICAL": 50}


def _required_beds(context: dict[str, Any], params: dict[str, Any]) -> int:
    severity = (context.get("classification") or {}).get("severity", "MEDIUM")
    beds = SEVERITY_BEDS.get(str(severity).upper(), int(params.get("beds", 1)))
    context["reserve_beds"] = beds
    return beds


async def _search_with_expanding_radius(
    service_name: str,
    path: str,
    params: dict[str, Any],
    context: dict[str, Any],
    initial_radius: float,
) -> tuple[list[dict[str, Any]], float]:
    radius = initial_radius
    while True:
        response = await call_service(
            service_name, "GET", path,
            params={**params, "radius_km": radius},
        )
        items = response.get("items", [])
        if items or not context.get("expand_search"):
            return items, radius
        deadline = context.get("search_deadline")
        remaining = (deadline - time.monotonic()) if deadline else 0
        if remaining <= 0 or radius >= 500:
            return [], radius
        await asyncio.sleep(min(5, remaining))
        radius = min(radius * 2, 500)


async def execute_step_action(
    step: WorkflowStepDef,
    context: dict[str, Any],
) -> dict[str, Any]:
    action = step.action
    params = {**step.params, **context.get("step_overrides", {})}

    # ── Classification recording ───────────────────────────────────────────────
    if action == "record_classification":
        return {"recorded": True, "classification": context.get("classification")}

    lat = context.get("latitude")
    lon = context.get("longitude")

    # ── Hospital search ────────────────────────────────────────────────────────
    if action == "search_hospitals":
        q: dict[str, Any] = {"active_only": True, "limit": 10}
        q["min_beds"] = _required_beds(context, params)
        if lat is not None and lon is not None:
            q["lat"] = lat
            q["lon"] = lon
            items, radius = await _search_with_expanding_radius(
                "hospital-service", "/api/hospitals/search", q, context,
                params.get("radius_km", 50),
            )
        else:
            data = await call_service("hospital-service", "GET", "/api/hospitals/search", params=q)
            items, radius = data.get("items", []), 0
        context["hospitals"] = items
        context["hospital_search_radius_km"] = radius
        if not items:
            context["no_nearby_hospital"] = True
        return {"count": len(items), "items": items, "radius_km": radius}

    # ── Reserve hospital beds ──────────────────────────────────────────────────
    if action == "reserve_hospital_beds":
        beds = _required_beds(context, params)
        hospitals = context.get("hospitals") or []
        if not hospitals:
            context["no_nearby_hospital"] = True
            return {"reserved": False, "beds_required": beds, "message": "No nearby hospitals found"}
        errors = []
        for h in hospitals:
            hid = h.get("id")
            if not hid:
                continue
            try:
                result = await call_service(
                    "hospital-service", "POST",
                    f"/api/hospitals/{hid}/reserve",
                    json_body={"beds": beds},
                )
                context["reserved_hospital_id"] = hid
                context["reserved_hospital"] = h
                return {"hospital_id": hid, "beds": beds, **result}
            except ServiceCallError as exc:
                errors.append(str(exc))
        # Return failure message instead of raising error
        return {
            "reserved": False, 
            "beds_required": beds, 
            "message": f"Could not reserve beds at any hospital: {'; '.join(errors[:3])}"
        }

    # ── Police search ──────────────────────────────────────────────────────────
    if action == "search_police":
        q: dict[str, Any] = {"active_only": True, "limit": 10}
        if lat is not None and lon is not None:
            q["lat"] = lat
            q["lon"] = lon
            items, radius = await _search_with_expanding_radius(
                "hospital-service", "/api/police-stations/search", q, context,
                params.get("radius_km", 50),
            )
        else:
            data = await call_service("hospital-service", "GET", "/api/police-stations/search", params=q)
            items, radius = data.get("items", []), 0
        context["police_stations"] = items
        context["police_search_radius_km"] = radius
        if not items:
            context["no_nearby_police"] = True
        return {"count": len(items), "items": items, "radius_km": radius}

    # ── Resource search ────────────────────────────────────────────────────────
    if action == "search_resources":
        q: dict[str, Any] = {"available_only": True, "limit": 10}
        if params.get("resource_type"):
            q["type"] = params["resource_type"]
        if lat is not None and lon is not None:
            q["lat"] = lat
            q["lon"] = lon
            q["radius_km"] = params.get("radius_km", 100)
        data = await call_service("resource-service", "GET", "/api/resources/search", params=q)
        items = data.get("items", [])
        context["resources"] = items
        return {"count": len(items), "items": items}

    # ── Allocate resource ──────────────────────────────────────────────────────
    if action == "allocate_resource":
        qty = int(params.get("quantity", 1))
        resources = context.get("resources") or []
        if not resources:
            context["no_nearby_resource"] = True
            return {"allocated": False, "quantity_requested": qty, "message": "No nearby resources found"}
        errors = []
        for r in resources:
            rid = r.get("id")
            if not rid:
                continue
            try:
                result = await call_service(
                    "resource-service", "POST",
                    f"/api/resources/{rid}/allocate",
                    json_body={"quantity": qty},
                )
                context["allocated_resource_id"] = rid
                context["allocated_resource"] = r
                return {"resource_id": rid, "quantity": qty, **result}
            except ServiceCallError as exc:
                errors.append(str(exc))
        # Return failure message instead of raising error
        return {
            "allocated": False,
            "quantity_requested": qty,
            "message": f"Could not allocate at any resource: {'; '.join(errors[:3])}"
        }

    # ── Plan route ─────────────────────────────────────────────────────────────
    if action == "plan_route":
        if lat is None or lon is None:
            raise ServiceCallError("Incident location required for route planning")
        dest_lat, dest_lon = _destination_coords(context)
        if dest_lat is None or dest_lon is None:
            raise ServiceCallError("No destination available for route planning")
        payload = {
            "origin_lat": lat,
            "origin_lon": lon,
            "destination_lat": dest_lat,
            "destination_lon": dest_lon,
            "incident_id": context.get("incident_id"),
            "workflow_id": context.get("workflow_id"),
        }
        data = await call_service(
            "route-service", "POST", "/api/routes/calculate", json_body=payload,
        )
        route = data.get("route") or data
        context["route_id"] = route.get("id")
        context["route"] = route
        return route

    # ── Phase 9: Dispatch notification ────────────────────────────────────────
    if action == "dispatch_notification":
        return await _dispatch_notification(context, params)

    raise ServiceCallError(f"Unknown workflow action: {action}")


# ── Notification dispatch ─────────────────────────────────────────────────────

async def _dispatch_notification(context: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """
    Build and send an emergency notification via the Notification Service.

    Attempts to notify:
      1. The reserved hospital (if any)
      2. The nearest police station (if any)

    Returns a summary dict. Raises ServiceCallError on hard failure
    so the engine can mark the step FAILED (non-critical → PARTIAL workflow).
    """
    classification = context.get("classification") or {}
    disaster_type = classification.get("disaster_type", "UNKNOWN")
    severity = classification.get("severity", "MEDIUM")
    incident_id = context.get("incident_id")
    workflow_id = context.get("workflow_id")
    location = _location_description(context)
    route_info = _route_summary(context)

    base_message = (
        f"EMERGENCY ALERT — {disaster_type} ({severity}). "
        f"Incident: {incident_id}. "
        f"Location: {location}. "
        f"{route_info}"
        "Immediate response required."
    )

    results: list[dict] = []
    errors: list[str] = []

    # Notify hospital
    hospital = context.get("reserved_hospital") or (
        context.get("hospitals") or [None]
    )[0]
    if hospital and hospital.get("name"):
        hospital_message = (
            f"{base_message} "
            f"Prepare {context.get('reserve_beds', 1)} emergency bed(s). "
            f"Workflow: {workflow_id}."
        )
        try:
            result = await call_service(
                "notification-service", "POST", "/api/notifications/send",
                json_body={
                    "recipient_type": "HOSPITAL",
                    "recipient_id": hospital.get("id"),
                    "recipient_name": hospital.get("name", "Hospital"),
                    "phone_number": hospital.get("emergency_phone") or hospital.get("phone", "000"),
                    "message": hospital_message,
                    "incident_id": incident_id,
                    "workflow_id": workflow_id,
                    "priority": _priority_from_severity(severity),
                },
            )
            results.append({"recipient": hospital["name"], "status": result.get("status")})
        except ServiceCallError as exc:
            errors.append(f"Hospital notification failed: {exc}")
            logger.warning("[dispatch] hospital notification failed: %s", exc)

    # Notify nearest police station
    police_stations = context.get("police_stations") or []
    if police_stations:
        station = police_stations[0]
        units_needed = {"LOW": 2, "MEDIUM": 5, "HIGH": 10, "CRITICAL": 20}.get(severity, 5)
        police_message = (
            f"{base_message} "
            f"Require {units_needed} police unit(s). Workflow: {workflow_id}."
        )
        try:
            result = await call_service(
                "notification-service", "POST", "/api/notifications/send",
                json_body={
                    "recipient_type": "POLICE",
                    "recipient_id": station.get("id"),
                    "recipient_name": station.get("name", "Police Station"),
                    "phone_number": station.get("emergency_phone") or station.get("phone", "000"),
                    "message": police_message,
                    "incident_id": incident_id,
                    "workflow_id": workflow_id,
                    "priority": _priority_from_severity(severity),
                },
            )
            results.append({"recipient": station.get("name"), "status": result.get("status")})
        except ServiceCallError as exc:
            errors.append(f"Police notification failed: {exc}")
            logger.warning("[dispatch] police notification failed: %s", exc)

    if not results and errors:
        raise ServiceCallError(
            f"All notification deliveries failed: {'; '.join(errors[:3])}"
        )

    no_nearby = bool(context.get("no_nearby_hospital") or context.get("no_nearby_police"))
    return {
        "notifications_sent": len(results),
        "results": results,
        "errors": errors,
        "no_nearby_places": no_nearby,
        "message": "No nearby hospitals or police stations found" if no_nearby and not results else None,
    }


def _priority_from_severity(severity: str) -> str:
    return {
        "CRITICAL": "CRITICAL",
        "HIGH": "HIGH",
        "MEDIUM": "NORMAL",
        "LOW": "LOW",
    }.get((severity or "MEDIUM").upper(), "NORMAL")


def _location_description(context: dict[str, Any]) -> str:
    lat = context.get("latitude")
    lon = context.get("longitude")
    if lat is not None and lon is not None:
        return f"{lat:.4f}, {lon:.4f}"
    hospital = context.get("reserved_hospital") or {}
    city = hospital.get("city")
    return city or "Unknown location"


def _route_summary(context: dict[str, Any]) -> str:
    route = context.get("route")
    if not route:
        return ""
    dist = route.get("distance_km")
    duration = route.get("estimated_duration_minutes")
    if dist and duration:
        return f"Route: {dist:.1f} km, ~{duration} min. "
    if dist:
        return f"Route: {dist:.1f} km. "
    return ""


def _destination_coords(context: dict[str, Any]) -> tuple[Any, Any]:
    hospitals = context.get("hospitals") or []
    reserved_id = context.get("reserved_hospital_id")
    if reserved_id:
        for h in hospitals:
            if h.get("id") == reserved_id:
                return h.get("latitude"), h.get("longitude")
    for h in hospitals:
        if h.get("latitude") is not None and h.get("longitude") is not None:
            return h.get("latitude"), h.get("longitude")
    resources = context.get("resources") or []
    allocated_id = context.get("allocated_resource_id")
    if allocated_id:
        for r in resources:
            if r.get("id") == allocated_id:
                return r.get("latitude"), r.get("longitude")
    for r in resources:
        if r.get("latitude") is not None and r.get("longitude") is not None:
            return r.get("latitude"), r.get("longitude")
    return None, None
