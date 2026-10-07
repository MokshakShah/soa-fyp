from datetime import datetime
from typing import Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


def _serialize(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


async def list_workflows(
    db: AsyncIOMotorDatabase,
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
) -> list:
    query: dict = {}
    if status:
        query["status"] = status.upper()
    cursor = db.workflows.find(query).skip(skip).limit(limit).sort("created_at", -1)
    return [_serialize(doc) async for doc in cursor]


async def count_workflows(
    db: AsyncIOMotorDatabase,
    status: Optional[str] = None,
) -> int:
    query: dict = {}
    if status:
        query["status"] = status.upper()
    return await db.workflows.count_documents(query)


async def workflow_status_summary(db: AsyncIOMotorDatabase) -> dict:
    """Return counts grouped by status for monitoring."""
    pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    cursor = db.workflows.aggregate(pipeline)
    counts: dict[str, int] = {}
    async for doc in cursor:
        counts[doc["_id"]] = doc["count"]
    total = sum(counts.values())
    return {
        "total": total,
        "by_status": counts,
        "running": counts.get("RUNNING", 0) + counts.get("PENDING", 0),
        "completed": counts.get("COMPLETED", 0),
        "partial": counts.get("PARTIAL", 0),
        "failed": counts.get("FAILED", 0),
    }


async def get_workflow(db: AsyncIOMotorDatabase, workflow_id: str) -> Optional[dict]:
    try:
        doc = await db.workflows.find_one({"_id": ObjectId(workflow_id)})
    except Exception:
        return None
    return _serialize(doc) if doc else None


async def create_workflow(db: AsyncIOMotorDatabase, data: dict) -> dict:
    now = datetime.utcnow()
    doc = {
        **data,
        "created_at": now,
        "updated_at": now,
        "started_at": data.get("started_at"),
        "completed_at": data.get("completed_at"),
    }
    result = await db.workflows.insert_one(doc)
    saved = await db.workflows.find_one({"_id": result.inserted_id})
    return _serialize(saved)


async def update_workflow(
    db: AsyncIOMotorDatabase,
    workflow_id: str,
    data: dict,
) -> Optional[dict]:
    data["updated_at"] = datetime.utcnow()
    try:
        result = await db.workflows.find_one_and_update(
            {"_id": ObjectId(workflow_id)},
            {"$set": data},
            return_document=True,
        )
    except Exception:
        return None
    return _serialize(result) if result else None


async def create_workflow_event(db: AsyncIOMotorDatabase, data: dict) -> dict:
    now = datetime.utcnow()
    doc = {**data, "timestamp": now}
    result = await db.workflow_events.insert_one(doc)
    saved = await db.workflow_events.find_one({"_id": result.inserted_id})
    return _serialize(saved)


async def list_workflow_events(
    db: AsyncIOMotorDatabase,
    workflow_id: str,
) -> list:
    cursor = db.workflow_events.find({"workflow_id": workflow_id}).sort("step_index", 1)
    return [_serialize(doc) async for doc in cursor]
