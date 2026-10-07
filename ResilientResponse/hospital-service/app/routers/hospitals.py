"""
Hospital router — Phase 2 CRUD + Phase 6 search and capacity operations.

IMPORTANT: /search and /reserve, /release are declared BEFORE /{hospital_id}
so FastAPI does not greedily match 'search' as a hospital ID.
"""
import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.models.hospital import HospitalCreate, HospitalUpdate, HospitalResponse
from app.models.operations import (
    ReserveBedsRequest, ReleaseBedsRequest, CapacityOperationResult,
)
from app.repositories.hospital_repo import (
    create_hospital, list_hospitals, count_hospitals,
    get_hospital, update_hospital, delete_hospital,
    search_hospitals, reserve_beds, release_beds,
)
from app.geo import within_radius, haversine_km
from app.database import get_db

logger = logging.getLogger("router.hospitals")
router = APIRouter(prefix="/api/hospitals", tags=["hospitals"])


# ── Phase 2: List / Create ────────────────────────────────────────────────────

@router.get("", response_model=dict)
async def get_hospitals(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
):
    db = get_db()
    items = await list_hospitals(db, skip=skip, limit=limit, search=search)
    total = await count_hospitals(db, search=search)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.post("", response_model=HospitalResponse, status_code=201)
async def add_hospital(body: HospitalCreate):
    db = get_db()
    return await create_hospital(db, body.model_dump())


# ── Phase 6: Search (BEFORE /{hospital_id}) ───────────────────────────────────

@router.get("/search", response_model=dict)
async def search_hospitals_endpoint(
    lat: Optional[float] = Query(None, description="Center latitude"),
    lon: Optional[float] = Query(None, description="Center longitude"),
    radius_km: float = Query(50.0, ge=0.1, le=500.0),
    city: Optional[str] = Query(None),
    min_beds: Optional[int] = Query(None, ge=1),
    active_only: bool = Query(True),
    limit: int = Query(20, ge=1, le=100),
):
    """Search hospitals by location and/or availability."""
    db = get_db()
    candidates = await search_hospitals(
        db, city=city, min_available_beds=min_beds,
        active_only=active_only, limit=limit * 5,
    )

    if lat is not None and lon is not None:
        results = []
        for h in candidates:
            if within_radius(h.get("latitude"), h.get("longitude"), lat, lon, radius_km):
                dist = haversine_km(lat, lon, h["latitude"], h["longitude"])
                results.append({**h, "distance_km": round(dist, 2)})
        results.sort(key=lambda x: x["distance_km"])
        results = results[:limit]
    else:
        results = candidates[:limit]

    return {"items": results, "total": len(results)}


# ── Phase 2: Detail / Update / Delete (/{hospital_id} AFTER /search) ──────────

@router.get("/{hospital_id}", response_model=HospitalResponse)
async def get_single_hospital(hospital_id: str):
    db = get_db()
    hospital = await get_hospital(db, hospital_id)
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return hospital


@router.put("/{hospital_id}", response_model=HospitalResponse)
async def edit_hospital(hospital_id: str, body: HospitalUpdate):
    db = get_db()
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await update_hospital(db, hospital_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return updated


@router.delete("/{hospital_id}", status_code=204)
async def remove_hospital(hospital_id: str):
    db = get_db()
    deleted = await delete_hospital(db, hospital_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Hospital not found")


# ── Phase 6: Reserve / Release (/{hospital_id}/...) ──────────────────────────

@router.post("/{hospital_id}/reserve", response_model=CapacityOperationResult)
async def reserve_hospital_beds(hospital_id: str, body: ReserveBedsRequest):
    """Atomically reserve beds. Returns 409 if insufficient capacity."""
    db = get_db()
    current = await get_hospital(db, hospital_id)
    if not current:
        raise HTTPException(status_code=404, detail="Hospital not found")
    if current.get("status") != "ACTIVE":
        raise HTTPException(status_code=409, detail="Hospital is not active")

    beds_before = current.get("available_beds") or 0
    updated = await reserve_beds(db, hospital_id, body.beds)

    if updated is None:
        logger.warning(
            "[reserve] FAILED hospital_id=%s beds_requested=%d beds_available=%d",
            hospital_id, body.beds, beds_before,
        )
        raise HTTPException(
            status_code=409,
            detail=f"Insufficient capacity: {beds_before} beds available, requested {body.beds}",
        )
    logger.info(
        "[reserve] OK hospital_id=%s hospital_name=%s beds=%d available_before=%d available_after=%d",
        hospital_id, current.get("name"), body.beds, beds_before, updated.get("available_beds"),
    )
    return CapacityOperationResult(
        hospital_id=hospital_id, operation="reserve", beds=body.beds,
        available_beds_before=beds_before,
        available_beds_after=updated.get("available_beds"),
        success=True,
        message=f"Reserved {body.beds} bed(s) successfully",
    )


@router.post("/{hospital_id}/release", response_model=CapacityOperationResult)
async def release_hospital_beds(hospital_id: str, body: ReleaseBedsRequest):
    """Release reserved beds back. Capped at emergency_capacity."""
    db = get_db()
    current = await get_hospital(db, hospital_id)
    if not current:
        raise HTTPException(status_code=404, detail="Hospital not found")

    beds_before = current.get("available_beds") or 0
    updated = await release_beds(db, hospital_id, body.beds)
    if updated is None:
        raise HTTPException(status_code=404, detail="Hospital not found")

    logger.info(
        "[release] OK hospital_id=%s beds=%d available_before=%d available_after=%d",
        hospital_id, body.beds, beds_before, updated.get("available_beds"),
    )
    return CapacityOperationResult(
        hospital_id=hospital_id, operation="release", beds=body.beds,
        available_beds_before=beds_before,
        available_beds_after=updated.get("available_beds"),
        success=True,
        message=f"Released {body.beds} bed(s) successfully",
    )
