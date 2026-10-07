from datetime import datetime
from typing import Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


def _serialize(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


async def create_route(db: AsyncIOMotorDatabase, data: dict) -> dict:
    now = datetime.utcnow()
    doc = {**data, "created_at": now, "updated_at": now}
    result = await db.routes.insert_one(doc)
    saved = await db.routes.find_one({"_id": result.inserted_id})
    return _serialize(saved)


async def list_routes(
    db: AsyncIOMotorDatabase,
    skip: int = 0,
    limit: int = 100,
    incident_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
) -> list:
    query: dict = {}
    if incident_id:
        query["incident_id"] = incident_id
    if workflow_id:
        query["workflow_id"] = workflow_id
    cursor = db.routes.find(query).skip(skip).limit(limit).sort("created_at", -1)
    return [_serialize(doc) async for doc in cursor]


async def count_routes(
    db: AsyncIOMotorDatabase,
    incident_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
) -> int:
    query: dict = {}
    if incident_id:
        query["incident_id"] = incident_id
    if workflow_id:
        query["workflow_id"] = workflow_id
    return await db.routes.count_documents(query)


async def get_route(db: AsyncIOMotorDatabase, route_id: str) -> Optional[dict]:
    try:
        doc = await db.routes.find_one({"_id": ObjectId(route_id)})
    except Exception:
        return None
    return _serialize(doc) if doc else None
