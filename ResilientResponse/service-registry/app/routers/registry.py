"""
Registry API — Registration, listing, and discovery endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.models.service import (
    RegisterRequest, RegisterResponse,
    RegistryRecord, DiscoveryResponse, DiscoveryInstance,
)
from app.repositories.registry_repo import (
    upsert_registration,
    list_registry,
    list_registry_by_service,
    get_registry_record,
    list_health,
    get_health,
)
from app.database import get_db

logger = logging.getLogger("registry.api")

router = APIRouter(prefix="/api/registry", tags=["registry"])

# Statuses considered "healthy enough" for discovery
HEALTHY_STATUSES = {"UP", "RECOVERING", "DEGRADED"}
# Statuses preferred for primary selection
PRIMARY_STATUSES = {"UP", "DEGRADED"}


# ── Registration ──────────────────────────────────────────────────────────────

@router.post("/register", response_model=RegisterResponse, status_code=200)
async def register_service(body: RegisterRequest):
    """
    Register or re-register a service instance.
    Idempotent: calling this twice with the same instance_id updates the record.
    """
    db = get_db()
    try:
        record = await upsert_registration(db, body.model_dump())
        logger.info(
            "[register] service=%s instance=%s role=%s url=%s",
            body.service_name, body.instance_id, body.instance_role, body.base_url,
        )
        return RegisterResponse(
            success=True,
            message="Registration successful",
            instance_id=record["instance_id"],
            service_name=record["service_name"],
        )
    except Exception as exc:
        logger.error("[register] Failed: %s", exc)
        raise HTTPException(status_code=500, detail="Registration failed")


# ── Listing ────────────────────────────────────────────────────────────────────

@router.get("/services", response_model=dict)
async def list_services(service_name: Optional[str] = Query(None)):
    """
    List all registered service instances, optionally filtered by service_name.
    Enriches each record with the latest health data.
    """
    db = get_db()
    if service_name:
        instances = await list_registry_by_service(db, service_name)
    else:
        instances = await list_registry(db)

    health_records = await list_health(db)
    health_map = {(h["service_name"], h["instance_id"]): h for h in health_records}

    enriched = []
    for inst in instances:
        h = health_map.get((inst["service_name"], inst["instance_id"]), {})
        enriched.append({
            **inst,
            "response_time_ms": h.get("response_time_ms"),
            "last_checked": h.get("last_checked"),
            "error": h.get("error"),
        })

    return {"items": enriched, "total": len(enriched)}


@router.get("/services/{service_name}", response_model=dict)
async def get_service_instances(service_name: str):
    """Return all instances for a specific logical service name."""
    db = get_db()
    instances = await list_registry_by_service(db, service_name)
    if not instances:
        raise HTTPException(status_code=404, detail=f"No instances registered for service: {service_name}")

    health_records = await list_health(db)
    health_map = {(h["service_name"], h["instance_id"]): h for h in health_records}

    enriched = []
    for inst in instances:
        h = health_map.get((inst["service_name"], inst["instance_id"]), {})
        enriched.append({
            **inst,
            "response_time_ms": h.get("response_time_ms"),
            "last_checked": h.get("last_checked"),
            "error": h.get("error"),
        })

    return {"service_name": service_name, "items": enriched, "total": len(enriched)}


# ── Discovery ─────────────────────────────────────────────────────────────────

@router.get("/discover/{service_name}", response_model=DiscoveryResponse)
async def discover_service(service_name: str):
    """
    Discover healthy instances for a logical service.

    Selection rules:
      1. Only return instances in HEALTHY_STATUSES (UP, RECOVERING, DEGRADED).
      2. selected = prefer PRIMARY with UP/DEGRADED status.
      3. If no healthy PRIMARY, select a healthy BACKUP.
      4. If no healthy instances at all → 503.
    """
    db = get_db()
    instances = await list_registry_by_service(db, service_name)

    if not instances:
        raise HTTPException(status_code=404, detail=f"Service not registered: {service_name}")

    health_map = {(h["service_name"], h["instance_id"]): h for h in await list_health(db)}

    healthy: list[DiscoveryInstance] = []
    for inst in instances:
        if inst["status"] not in HEALTHY_STATUSES:
            continue
        h = health_map.get((inst["service_name"], inst["instance_id"]), {})
        healthy.append(DiscoveryInstance(
            instance_id=inst["instance_id"],
            base_url=inst["base_url"],
            status=inst["status"],
            instance_role=inst["instance_role"],
            version=inst.get("version", "unknown"),
            response_time_ms=h.get("response_time_ms"),
            last_heartbeat=inst.get("last_heartbeat"),
        ))

    if not healthy:
        raise HTTPException(
            status_code=503,
            detail=f"No healthy instances available for service: {service_name}",
        )

    # Selection: prefer PRIMARY with UP/DEGRADED, then any BACKUP
    selected = None
    for inst in healthy:
        if inst.instance_role == "PRIMARY" and inst.status in PRIMARY_STATUSES:
            selected = inst
            break
    if selected is None:
        selected = healthy[0]  # First healthy (could be BACKUP or RECOVERING PRIMARY)

    return DiscoveryResponse(
        service_name=service_name,
        instances=healthy,
        selected=selected,
    )


# ── Health detail ──────────────────────────────────────────────────────────────

@router.get("/health/{service_name}/{instance_id}")
async def get_instance_health(service_name: str, instance_id: str):
    """Get health details for a specific instance."""
    db = get_db()
    record = await get_registry_record(db, service_name, instance_id)
    if not record:
        raise HTTPException(status_code=404, detail="Instance not registered")
    health = await get_health(db, service_name, instance_id)
    return {**record, "health": health}


# ── Summary ────────────────────────────────────────────────────────────────────

@router.get("/summary")
async def get_registry_summary():
    """
    Return a full health breakdown across all registered instances.

    Includes:
    - overall totals (total_instances, healthy_instances, status_counts)
    - per-service breakdown with PRIMARY/BACKUP role data and last health check
    Used by the admin dashboard and Phase 12 monitoring.
    """
    db = get_db()
    instances = await list_registry(db)
    health_records = await list_health(db)
    health_map = {(h["service_name"], h["instance_id"]): h for h in health_records}

    status_counts: dict[str, int] = {}
    healthy_count = 0
    HEALTHY = {"UP", "RECOVERING", "DEGRADED"}

    # Build per-service breakdown keyed by service_name
    services_map: dict[str, dict] = {}

    for inst in instances:
        st = inst.get("status", "UNKNOWN")
        status_counts[st] = status_counts.get(st, 0) + 1
        if st in HEALTHY:
            healthy_count += 1

        svc = inst["service_name"]
        if svc not in services_map:
            services_map[svc] = {
                "service_name": svc,
                "total_instances": 0,
                "healthy_instances": 0,
                "status_breakdown": {},
                "instances": [],
            }

        h = health_map.get((svc, inst["instance_id"]), {})
        services_map[svc]["total_instances"] += 1
        if st in HEALTHY:
            services_map[svc]["healthy_instances"] += 1
        services_map[svc]["status_breakdown"][st] = (
            services_map[svc]["status_breakdown"].get(st, 0) + 1
        )
        services_map[svc]["instances"].append({
            "instance_id": inst["instance_id"],
            "role": inst.get("instance_role", "PRIMARY"),
            "status": st,
            "last_health_check": h.get("last_checked"),
            "response_time_ms": h.get("response_time_ms"),
            "error": h.get("error"),
            "base_url": inst.get("base_url"),
            "version": inst.get("version"),
            "last_heartbeat": inst.get("last_heartbeat"),
            "registered_at": inst.get("registered_at"),
        })

    # Sort instances within each service: PRIMARY first
    for svc_data in services_map.values():
        svc_data["instances"].sort(key=lambda i: (0 if i["role"] == "PRIMARY" else 1))

    return {
        "total_instances": len(instances),
        "healthy_instances": healthy_count,
        "status_counts": status_counts,
        "services": list(services_map.values()),
    }
