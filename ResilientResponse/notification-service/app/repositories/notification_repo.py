"""
Notification repository — Phase 9.
Owns the `notifications` collection in MongoDB.
No other service may read or write this collection directly.
"""
import logging
from datetime import datetime
from typing import Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("notification.repo")


def _serialize(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


# ── Indexes ───────────────────────────────────────────────────────────────────

async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create useful indexes on startup. Idempotent."""
    col = db.notifications
    await col.create_index("incident_id")
    await col.create_index("workflow_id")
    await col.create_index("recipient_id")
    await col.create_index("status")
    await col.create_index([("created_at", -1)])
    logger.info("[repo] Notification indexes ensured")


# ── Create ────────────────────────────────────────────────────────────────────

async def create_notification(db: AsyncIOMotorDatabase, data: dict) -> dict:
    now = datetime.utcnow()
    doc = {
        **data,
        "status": "PENDING",
        "sent_at": None,
        "failure_reason": None,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.notifications.insert_one(doc)
    saved = await db.notifications.find_one({"_id": result.inserted_id})
    return _serialize(saved)


# ── Update status ─────────────────────────────────────────────────────────────

async def mark_sent(
    db: AsyncIOMotorDatabase,
    notification_id: str,
    provider_message_id: Optional[str] = None,
) -> Optional[dict]:
    now = datetime.utcnow()
    try:
        oid = ObjectId(notification_id)
    except Exception:
        return None
    result = await db.notifications.find_one_and_update(
        {"_id": oid},
        {"$set": {
            "status": "SENT",
            "sent_at": now,
            "failure_reason": None,
            "provider_message_id": provider_message_id,
            "updated_at": now,
        }},
        return_document=True,
    )
    return _serialize(result) if result else None


async def mark_failed(
    db: AsyncIOMotorDatabase,
    notification_id: str,
    failure_reason: str,
) -> Optional[dict]:
    now = datetime.utcnow()
    try:
        oid = ObjectId(notification_id)
    except Exception:
        return None
    result = await db.notifications.find_one_and_update(
        {"_id": oid},
        {"$set": {
            "status": "FAILED",
            "failure_reason": failure_reason,
            "updated_at": now,
        }},
        return_document=True,
    )
    return _serialize(result) if result else None


# ── Read ──────────────────────────────────────────────────────────────────────

async def list_notifications(
    db: AsyncIOMotorDatabase,
    skip: int = 0,
    limit: int = 100,
    incident_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    status: Optional[str] = None,
    recipient_type: Optional[str] = None,
) -> list:
    query: dict = {}
    if incident_id:
        query["incident_id"] = incident_id
    if workflow_id:
        query["workflow_id"] = workflow_id
    if status:
        query["status"] = status.upper()
    if recipient_type:
        query["recipient_type"] = recipient_type.upper()
    cursor = (
        db.notifications
        .find(query)
        .skip(skip)
        .limit(limit)
        .sort("created_at", -1)
    )
    return [_serialize(doc) async for doc in cursor]


async def count_notifications(
    db: AsyncIOMotorDatabase,
    incident_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    status: Optional[str] = None,
) -> int:
    query: dict = {}
    if incident_id:
        query["incident_id"] = incident_id
    if workflow_id:
        query["workflow_id"] = workflow_id
    if status:
        query["status"] = status.upper()
    return await db.notifications.count_documents(query)


async def notification_status_summary(db: AsyncIOMotorDatabase) -> dict:
    """Return notification counts grouped by status — used by dashboard monitoring."""
    pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    cursor = db.notifications.aggregate(pipeline)
    counts: dict[str, int] = {}
    async for doc in cursor:
        counts[doc["_id"]] = doc["count"]
    total = sum(counts.values())
    return {
        "total": total,
        "by_status": counts,
        "sent": counts.get("SENT", 0),
        "failed": counts.get("FAILED", 0),
        "pending": counts.get("PENDING", 0),
    }


async def get_notification(db: AsyncIOMotorDatabase, notification_id: str) -> Optional[dict]:
    try:
        doc = await db.notifications.find_one({"_id": ObjectId(notification_id)})
    except Exception:
        return None
    return _serialize(doc) if doc else None
