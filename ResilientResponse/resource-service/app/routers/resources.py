"""
Resource router — Phase 2 CRUD + Phase 6 search, allocate, release.
/search declared BEFORE /{resource_id} to avoid route conflict.
"""
import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.models.resource import ResourceCreate, ResourceUpdate, ResourceResponse
from app.models.operations import AllocateRequest, ReleaseRequest, AllocationResult
from app.repositories.resource_repo import (
    create_resource, list_resources, count_resources,
    get_resource, update_resource, delete_resource,
    search_resources, allocate_resource, release_resource,
)
from app.geo import within_radius, haversine_km
from app.database import get_db

logger = logging.getLogger("router.resources")
router = APIRouter(prefix="/api/resources", tags=["resources"])


# ── Phase 2: List / Create ────────────────────────────────────────────────────

@router.get("", response_model=dict)
async def get_resources(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="type"),
):
    db = get_db()
    items = await list_resources(db, skip=skip, limit=limit, search=search, resource_type=type)
    total = await count_resources(db, search=search, resource_type=type)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.post("", response_model=ResourceResponse, status_code=201)
async def add_resource(body: ResourceCreate):
    db = get_db()
    return await create_resource(db, body.model_dump())


# ── Phase 6: Search (BEFORE /{resource_id}) ───────────────────────────────────

@router.get("/search", response_model=dict)
async def search_resources_endpoint(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    radius_km: float = Query(100.0, ge=0.1, le=500.0),
    type: Optional[str] = Query(None, alias="type"),
    city: Optional[str] = Query(None),
    available_only: bool = Query(True),
    min_quantity: Optional[int] = Query(None, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """Search resources by type, location, city, and availability."""
    db = get_db()
    candidates = await search_resources(
        db, resource_type=type, city=city,
        available_only=available_only,
        min_quantity=min_quantity,
        limit=limit * 5,
    )

    if lat is not None and lon is not None:
        results = []
        for r in candidates:
            if within_radius(r.get("latitude"), r.get("longitude"), lat, lon, radius_km):
                dist = haversine_km(lat, lon, r["latitude"], r["longitude"])
                results.append({**r, "distance_km": round(dist, 2)})
        results.sort(key=lambda x: x["distance_km"])
        results = results[:limit]
    else:
        results = candidates[:limit]

    return {"items": results, "total": len(results)}


# ── Phase 2: Detail / Update / Delete (/{resource_id} AFTER /search) ─────────

@router.get("/{resource_id}", response_model=ResourceResponse)
async def get_single_resource(resource_id: str):
    db = get_db()
    resource = await get_resource(db, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return resource


@router.put("/{resource_id}", response_model=ResourceResponse)
async def edit_resource(resource_id: str, body: ResourceUpdate):
    db = get_db()
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await update_resource(db, resource_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Resource not found")
    return updated


@router.delete("/{resource_id}", status_code=204)
async def remove_resource(resource_id: str):
    db = get_db()
    deleted = await delete_resource(db, resource_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Resource not found")


# ── Phase 6: Allocate / Release ────────────────────────────────────────────────

@router.post("/{resource_id}/allocate", response_model=AllocationResult)
async def allocate_resource_endpoint(resource_id: str, body: AllocateRequest):
    """Atomically allocate units. Returns 409 if insufficient or unavailable."""
    db = get_db()
    current = await get_resource(db, resource_id)
    if not current:
        raise HTTPException(status_code=404, detail="Resource not found")

    if current.get("status") in ("INACTIVE", "MAINTENANCE"):
        raise HTTPException(
            status_code=409,
            detail=f"Resource not available for allocation (status: {current['status']})",
        )

    avail_before = current.get("available_quantity", 0)
    if avail_before < body.quantity:
        logger.warning(
            "[allocate] FAILED resource_id=%s type=%s qty_requested=%d qty_available=%d",
            resource_id, current.get("resource_type"), body.quantity, avail_before,
        )
        raise HTTPException(
            status_code=409,
            detail=f"Insufficient quantity: {avail_before} available, requested {body.quantity}",
        )

    updated = await allocate_resource(db, resource_id, body.quantity)
    if updated is None:
        raise HTTPException(status_code=409, detail="Allocation failed — resource may have changed concurrently")

    logger.info(
        "[allocate] OK resource_id=%s type=%s quantity=%d available_before=%d available_after=%d",
        resource_id, current.get("resource_type"), body.quantity, avail_before, updated.get("available_quantity"),
    )
    return AllocationResult(
        resource_id=resource_id, operation="allocate", quantity=body.quantity,
        available_before=avail_before,
        available_after=updated.get("available_quantity"),
        success=True,
        message=f"Allocated {body.quantity} {current.get('unit') or 'unit(s)'} successfully",
    )


@router.post("/{resource_id}/release", response_model=AllocationResult)
async def release_resource_endpoint(resource_id: str, body: ReleaseRequest):
    """Release allocated units. Capped at total quantity."""
    db = get_db()
    current = await get_resource(db, resource_id)
    if not current:
        raise HTTPException(status_code=404, detail="Resource not found")

    avail_before = current.get("available_quantity", 0)
    updated = await release_resource(db, resource_id, body.quantity)
    if updated is None:
        raise HTTPException(status_code=404, detail="Resource not found")

    logger.info(
        "[release] OK resource_id=%s type=%s quantity=%d available_before=%d available_after=%d",
        resource_id, current.get("resource_type"), body.quantity, avail_before, updated.get("available_quantity"),
    )
    return AllocationResult(
        resource_id=resource_id, operation="release", quantity=body.quantity,
        available_before=avail_before,
        available_after=updated.get("available_quantity"),
        success=True,
        message=f"Released {body.quantity} {current.get('unit') or 'unit(s)'} successfully",
    )
