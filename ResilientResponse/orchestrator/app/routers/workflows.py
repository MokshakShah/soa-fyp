import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.database import get_db
from app.models.workflow import ExecuteWorkflowRequest
from app.repositories.workflow_repo import (
    list_workflows, count_workflows, get_workflow,
    list_workflow_events, workflow_status_summary,
)
from app.workflows.engine import run_workflow, select_workflow

logger = logging.getLogger("router.workflows")
router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.post("/execute", response_model=dict)
async def execute_workflow(body: ExecuteWorkflowRequest):
    """Receive a classified incident, select the matching workflow, and execute it sequentially."""
    if select_workflow(body.disaster_type) is None:
        raise HTTPException(
            status_code=400,
            detail=f"No workflow defined for disaster type: {body.disaster_type}",
        )

    classification = body.classification.model_dump() if body.classification else {
        "disaster_type": body.disaster_type,
        "severity": body.severity,
    }
    classification.setdefault("disaster_type", body.disaster_type)
    classification.setdefault("severity", body.severity or "MEDIUM")

    db = get_db()
    try:
        result = await run_workflow(
            db,
            incident_id=body.incident_id,
            disaster_type=body.disaster_type,
            classification=classification,
            latitude=body.latitude,
            longitude=body.longitude,
            expand_search=body.expand_search,
            search_timeout_seconds=body.search_timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("[execute] workflow failed unexpectedly")
        raise HTTPException(status_code=500, detail=f"Workflow execution error: {exc}")

    return result


# ── Summary (before /{workflow_id} to avoid route conflict) ───────────────────

@router.get("/summary")
async def get_workflow_summary():
    """Return workflow execution counts grouped by status — used by dashboard monitoring."""
    db = get_db()
    return await workflow_status_summary(db)


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=dict)
async def get_workflows(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None, description="Filter by status: RUNNING|COMPLETED|PARTIAL|FAILED|PENDING"),
):
    db = get_db()
    items = await list_workflows(db, skip=skip, limit=limit, status=status)
    total = await count_workflows(db, status=status)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


# ── Detail + events ────────────────────────────────────────────────────────────

@router.get("/{workflow_id}/events", response_model=dict)
async def get_workflow_events(workflow_id: str):
    db = get_db()
    workflow = await get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    events = await list_workflow_events(db, workflow_id)
    return {"workflow_id": workflow_id, "items": events, "total": len(events)}


@router.get("/{workflow_id}")
async def get_single_workflow(workflow_id: str):
    db = get_db()
    workflow = await get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    events = await list_workflow_events(db, workflow_id)
    return {**workflow, "events": events}
