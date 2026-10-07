import logging
from fastapi import APIRouter, HTTPException, Query
from app.models.incident import IncidentCreate, IncidentResponse
from app.repositories.incident_repo import create_incident, list_incidents, count_incidents, get_incident
from app.database import get_db

logger = logging.getLogger("router.incidents")
router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("", response_model=dict)
async def get_incidents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    db = get_db()
    items = await list_incidents(db, skip=skip, limit=limit)
    total = await count_incidents(db)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_single_incident(incident_id: str):
    db = get_db()
    incident = await get_incident(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("", response_model=IncidentResponse, status_code=201)
async def create_new_incident(body: IncidentCreate):
    """Create an incident manually (for development/testing)."""
    db = get_db()
    data = body.model_dump()
    incident = await create_incident(db, data)
    logger.info(
        "[incident] CREATED incident_id=%s disaster_type=%s severity=%s",
        incident.get("id"), data.get("disaster_type"), data.get("severity"),
    )
    return incident
