"""
Alert repository — all MongoDB operations for the alerts collection.

Deduplication key: (source, external_id)
If a record with the same source + external_id already exists, it is updated
instead of inserting a duplicate.
"""
from datetime import datetime
from typing import Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging
from app.config import ALERT_TODAY_ONLY

logger = logging.getLogger("alert_repo")


def _today_filter() -> dict:
    if not ALERT_TODAY_ONLY:
        return {}
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start.replace(hour=23, minute=59, second=59, microsecond=999999)
    return {"issued_at": {"$gte": start, "$lte": end}}


def _serialize(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


async def upsert_alert(db: AsyncIOMotorDatabase, data: dict) -> tuple[dict, bool]:
    """
    Insert or update an alert using (source, external_id) as the deduplication key.

    Returns (record, was_created):
      was_created=True  → new record inserted
      was_created=False → existing record updated
    """
    now = datetime.utcnow()

    # Only deduplicate when external_id is set
    if data.get("external_id") and data.get("source"):
        key = {"source": data["source"], "external_id": data["external_id"]}
        existing = await db.alerts.find_one(key)
        if existing:
            update_fields = {k: v for k, v in data.items() if v is not None}
            update_fields["updated_at"] = now
            await db.alerts.update_one({"_id": existing["_id"]}, {"$set": update_fields})
            doc = await db.alerts.find_one({"_id": existing["_id"]})
            logger.debug("Alert updated: source=%s external_id=%s", data["source"], data["external_id"])
            return _serialize(doc), False

    # New record
    data.setdefault("issued_at", now)
    data["created_at"] = now
    data["updated_at"] = now
    data.setdefault("status", "NEW")
    result = await db.alerts.insert_one(data)
    doc = await db.alerts.find_one({"_id": result.inserted_id})
    logger.debug("Alert created: source=%s external_id=%s", data.get("source"), data.get("external_id"))
    return _serialize(doc), True


async def create_alert(db: AsyncIOMotorDatabase, data: dict) -> dict:
    """Simple insert — used for DEMO alerts that intentionally bypass dedup."""
    now = datetime.utcnow()
    data.setdefault("issued_at", now)
    data.setdefault("status", "NEW")
    data["created_at"] = now
    data["updated_at"] = now
    result = await db.alerts.insert_one(data)
    doc = await db.alerts.find_one({"_id": result.inserted_id})
    return _serialize(doc)


async def list_alerts(
    db: AsyncIOMotorDatabase,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    source: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
) -> list:
    query: dict = {}
    filters = []
    if search:
        filters.append({"$or": [
            {"title": {"$regex": search, "$options": "i"}},
            {"disaster_type": {"$regex": search, "$options": "i"}},
            {"location_name": {"$regex": search, "$options": "i"}},
        ]})
    if source:
        filters.append({"source": {"$regex": source, "$options": "i"}})
    if severity:
        filters.append({"severity": severity.upper()})
    if status:
        filters.append({"status": status.upper()})
    if ALERT_TODAY_ONLY:
        filters.append(_today_filter())
    if filters:
        query = {"$and": filters} if len(filters) > 1 else filters[0]
    cursor = db.alerts.find(query).skip(skip).limit(limit).sort("created_at", -1)
    return [_serialize(doc) async for doc in cursor]


async def count_alerts(
    db: AsyncIOMotorDatabase,
    search: Optional[str] = None,
    source: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
) -> int:
    query: dict = {}
    filters = []
    if search:
        filters.append({"$or": [
            {"title": {"$regex": search, "$options": "i"}},
            {"disaster_type": {"$regex": search, "$options": "i"}},
        ]})
    if source:
        filters.append({"source": {"$regex": source, "$options": "i"}})
    if severity:
        filters.append({"severity": severity.upper()})
    if status:
        filters.append({"status": status.upper()})
    if ALERT_TODAY_ONLY:
        filters.append(_today_filter())
    if filters:
        query = {"$and": filters} if len(filters) > 1 else filters[0]
    return await db.alerts.count_documents(query)


async def get_alert(db: AsyncIOMotorDatabase, alert_id: str) -> Optional[dict]:
    try:
        doc = await db.alerts.find_one({"_id": ObjectId(alert_id)})
    except Exception:
        return None
    return _serialize(doc) if doc else None
