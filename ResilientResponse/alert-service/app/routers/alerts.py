import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.models.alert import AlertCreate, AlertResponse, FetchResult
from app.repositories.alert_repo import create_alert, list_alerts, count_alerts, get_alert
from app.adapters.base import AdapterError
from app.services.ingestion import ingest_alerts
from app.database import get_db

logger = logging.getLogger("router.alerts")
router = APIRouter(prefix="/api/alerts", tags=["alerts"])


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=dict)
async def get_alerts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """List alerts with optional filtering by search, source, severity, and status."""
    db = get_db()
    items = await list_alerts(
        db, skip=skip, limit=limit,
        search=search, source=source,
        severity=severity, status=status,
    )
    total = await count_alerts(db, search=search, source=source, severity=severity, status=status)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


# ── Detail ─────────────────────────────────────────────────────────────────────

@router.get("/{alert_id}", response_model=AlertResponse)
async def get_single_alert(alert_id: str):
    db = get_db()
    alert = await get_alert(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


# ── Demo ───────────────────────────────────────────────────────────────────────

@router.post("/demo", response_model=AlertResponse, status_code=201)
async def create_demo_alert(body: AlertCreate):
    """
    DEMO/TEST ONLY — Creates a single test alert for development purposes.
    Clearly marked with source='DEMO'. NOT a real government or external alert.
    """
    db = get_db()
    data = body.model_dump()
    data["source"] = "DEMO"
    # Serialize enums
    if hasattr(data.get("severity"), "value"):
        data["severity"] = data["severity"].value
    if hasattr(data.get("status"), "value"):
        data["status"] = data["status"].value
    return await create_alert(db, data)


# ── Fetch ──────────────────────────────────────────────────────────────────────

@router.post("/fetch", response_model=FetchResult)
async def fetch_alerts(source: Optional[str] = Query(None, description="GDACS | DEMO")):
    """
    Trigger ingestion from the configured external alert source.

    - Fetches alerts from the source (default: GDACS RSS feed)
    - Deduplicates against existing database records
    - Returns a summary of what was created, updated, or failed

    Returns 503 if the external source is completely unreachable.
    """
    db = get_db()
    try:
        result = await ingest_alerts(db, source=source)
        return result
    except AdapterError as exc:
        logger.warning("Adapter error during fetch: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"External alert source unavailable: {exc}",
        )
    except Exception as exc:
        logger.error("Unexpected error during fetch: %s", exc)
        raise HTTPException(status_code=500, detail="Internal error during alert fetch")
