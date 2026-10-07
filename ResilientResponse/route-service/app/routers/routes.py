import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.database import get_db
from app.models.route import (
    CalculateRouteRequest,
    CalculateRouteResponse,
    RouteResponse,
    RouteStatus,
)
from app.providers.osrm import RoutingProviderError, fetch_route
from app.repositories.route_repo import create_route, get_route, list_routes, count_routes
from app.config import ROUTING_PROVIDER_NAME

logger = logging.getLogger("router.routes")
router = APIRouter(prefix="/api/routes", tags=["routes"])


@router.get("", response_model=dict)
async def get_routes(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    incident_id: Optional[str] = Query(None),
    workflow_id: Optional[str] = Query(None),
):
    db = get_db()
    items = await list_routes(db, skip=skip, limit=limit, incident_id=incident_id, workflow_id=workflow_id)
    total = await count_routes(db, incident_id=incident_id, workflow_id=workflow_id)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.post("/calculate", response_model=CalculateRouteResponse, status_code=201)
async def calculate_route(body: CalculateRouteRequest):
    """Calculate and persist a route between origin and destination."""
    db = get_db()
    base_doc = {
        "incident_id": body.incident_id,
        "workflow_id": body.workflow_id,
        "origin_lat": body.origin_lat,
        "origin_lon": body.origin_lon,
        "destination_lat": body.destination_lat,
        "destination_lon": body.destination_lon,
        "provider": ROUTING_PROVIDER_NAME,
        "distance_km": None,
        "estimated_travel_minutes": None,
        "geometry": None,
        "error": None,
    }

    try:
        result = await fetch_route(
            body.origin_lat, body.origin_lon,
            body.destination_lat, body.destination_lon,
        )
        saved = await create_route(db, {
            **base_doc,
            "status": RouteStatus.CALCULATED.value,
            "distance_km": result["distance_km"],
            "estimated_travel_minutes": result["estimated_travel_minutes"],
            "geometry": result.get("geometry"),
        })
        route = RouteResponse(**saved)
        logger.info(
            "[calculate] OK incident_id=%s workflow_id=%s distance_km=%.1f travel_min=%.1f provider=%s",
            body.incident_id, body.workflow_id,
            result.get("distance_km", 0), result.get("estimated_travel_minutes", 0),
            ROUTING_PROVIDER_NAME,
        )
        return CalculateRouteResponse(
            route=route,
            message="Route calculated successfully",
        )
    except RoutingProviderError as exc:
        logger.warning(
            "[calculate] PROVIDER_UNAVAILABLE incident_id=%s workflow_id=%s provider=%s error=%s",
            body.incident_id, body.workflow_id, ROUTING_PROVIDER_NAME, exc,
        )
        saved = await create_route(db, {
            **base_doc,
            "status": RouteStatus.PROVIDER_UNAVAILABLE.value,
            "error": str(exc),
        })
        route = RouteResponse(**saved)
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Routing provider unavailable",
                "route": route.model_dump(mode="json"),
            },
        )


@router.get("/{route_id}", response_model=RouteResponse)
async def get_route_by_id(route_id: str):
    db = get_db()
    doc = await get_route(db, route_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Route not found")
    return RouteResponse(**doc)
