"""
Notification router — Phase 9 + Phase 12 monitoring.
POST /send and GET /summary declared before /{notification_id} to avoid route conflict.
"""
import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from bson import ObjectId

from app.config import NOTIFICATION_PROVIDER
from app.models.notification import SendNotificationRequest, NotificationResponse
from app.providers.factory import get_provider
from app.repositories.notification_repo import (
    list_notifications, count_notifications, get_notification,
    notification_status_summary,
)
from app.services.send_service import send_notification
from app.database import get_db
from fastapi.responses import StreamingResponse
from app.services.sse import subscribe

logger = logging.getLogger("router.notifications")
router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/stream")
async def sse_stream():
    """Server-Sent Events endpoint for real-time notifications."""
    return StreamingResponse(subscribe(), media_type="text/event-stream")

@router.post("/{notification_id}/reply")
async def reply_to_notification(notification_id: str, reply: dict):
    """Responder submits available resources (beds/ambulances) for an alert."""
    db = get_db()
    try:
        oid = ObjectId(notification_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid notification ID")
    result = await db.notifications.update_one({"_id": oid}, {"$set": {"reply": reply}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    logger.info(f"[reply] Notification {notification_id} received reply: {reply}")
    return {"status": "recorded", "reply": reply}



# ── POST /send ────────────────────────────────────────────────────────────────

@router.post("/send", response_model=NotificationResponse, status_code=201)
async def send(body: SendNotificationRequest):
    """Create and deliver a notification. Provider failure returns FAILED record, not 5xx."""
    db = get_db()
    provider = get_provider(NOTIFICATION_PROVIDER)
    record = await send_notification(db, body, provider)
    return record


# ── GET /summary (before /{notification_id}) ──────────────────────────────────

@router.get("/summary")
async def get_notification_summary():
    """Return notification counts grouped by status — used by dashboard monitoring."""
    db = get_db()
    return await notification_status_summary(db)


# ── GET list ──────────────────────────────────────────────────────────────────

@router.get("", response_model=dict)
async def get_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    incident_id: Optional[str] = Query(None),
    workflow_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    recipient_type: Optional[str] = Query(None),
):
    db = get_db()
    items = await list_notifications(
        db, skip=skip, limit=limit,
        incident_id=incident_id,
        workflow_id=workflow_id,
        status=status,
        recipient_type=recipient_type,
    )
    total = await count_notifications(
        db,
        incident_id=incident_id,
        workflow_id=workflow_id,
        status=status,
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}


# ── GET detail ────────────────────────────────────────────────────────────────

@router.get("/{notification_id}")
async def get_single_notification(notification_id: str):
    db = get_db()
    notification = await get_notification(db, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification
