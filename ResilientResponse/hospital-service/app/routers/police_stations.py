"""
Police station router — Phase 2 CRUD + Phase 6 search.
/search declared BEFORE /{station_id} to avoid route conflict.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.models.police_station import (
    PoliceStationCreate, PoliceStationUpdate, PoliceStationResponse,
)
from app.repositories.police_repo import (
    create_police_station, list_police_stations, count_police_stations,
    get_police_station, update_police_station, delete_police_station,
    search_police_stations,
)
from app.geo import within_radius, haversine_km
from app.database import get_db

router = APIRouter(prefix="/api/police-stations", tags=["police-stations"])


# ── Phase 2: List / Create ────────────────────────────────────────────────────

@router.get("", response_model=dict)
async def get_police_stations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
):
    db = get_db()
    items = await list_police_stations(db, skip=skip, limit=limit, search=search)
    total = await count_police_stations(db, search=search)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.post("", response_model=PoliceStationResponse, status_code=201)
async def add_police_station(body: PoliceStationCreate):
    db = get_db()
    return await create_police_station(db, body.model_dump())


# ── Phase 6: Search (BEFORE /{station_id}) ────────────────────────────────────

async def _search_police_impl(
    lat: Optional[float],
    lon: Optional[float],
    radius_km: float,
    city: Optional[str],
    active_only: bool,
    limit: int,
) -> dict:
    """Shared search logic for /api/police-stations/search and /api/police/search."""
    db = get_db()
    candidates = await search_police_stations(
        db, city=city, active_only=active_only, limit=limit * 5,
    )

    if lat is not None and lon is not None:
        results = []
        for s in candidates:
            if within_radius(s.get("latitude"), s.get("longitude"), lat, lon, radius_km):
                dist = haversine_km(lat, lon, s["latitude"], s["longitude"])
                results.append({**s, "distance_km": round(dist, 2)})
        results.sort(key=lambda x: x["distance_km"])
        results = results[:limit]
    else:
        results = candidates[:limit]

    return {"items": results, "total": len(results)}


@router.get("/search", response_model=dict)
async def search_police_stations_endpoint(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    radius_km: float = Query(50.0, ge=0.1, le=500.0),
    city: Optional[str] = Query(None),
    active_only: bool = Query(True),
    limit: int = Query(20, ge=1, le=100),
):
    """Search police stations by location and/or city."""
    return await _search_police_impl(lat, lon, radius_km, city, active_only, limit)


# Orchestrator-friendly alias: GET /api/police/search
police_alias_router = APIRouter(prefix="/api/police", tags=["police"])


@police_alias_router.get("/search", response_model=dict)
async def search_police_alias(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    radius_km: float = Query(50.0, ge=0.1, le=500.0),
    city: Optional[str] = Query(None),
    active_only: bool = Query(True),
    limit: int = Query(20, ge=1, le=100),
):
    """Alias for police station location search."""
    return await _search_police_impl(lat, lon, radius_km, city, active_only, limit)


# ── Phase 2: Detail / Update / Delete (/{station_id} AFTER /search) ──────────

@router.get("/{station_id}", response_model=PoliceStationResponse)
async def get_single_station(station_id: str):
    db = get_db()
    station = await get_police_station(db, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Police station not found")
    return station


@router.put("/{station_id}", response_model=PoliceStationResponse)
async def edit_police_station(station_id: str, body: PoliceStationUpdate):
    db = get_db()
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await update_police_station(db, station_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Police station not found")
    return updated


@router.delete("/{station_id}", status_code=204)
async def remove_police_station(station_id: str):
    db = get_db()
    deleted = await delete_police_station(db, station_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Police station not found")
