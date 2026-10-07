from datetime import datetime
from typing import Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


async def create_incident(db: AsyncIOMotorDatabase, data: dict) -> dict:
    now = datetime.utcnow()
    data.update({"created_at": now, "updated_at": now, "resolved_at": None})
    result = await db.incidents.insert_one(data)
    doc = await db.incidents.find_one({"_id": result.inserted_id})
    return _serialize(doc)


async def list_incidents(db: AsyncIOMotorDatabase, skip: int = 0, limit: int = 100) -> list:
    cursor = db.incidents.find({}).skip(skip).limit(limit).sort("created_at", -1)
    return [_serialize(doc) async for doc in cursor]


async def count_incidents(db: AsyncIOMotorDatabase) -> int:
    return await db.incidents.count_documents({})


async def get_incident(db: AsyncIOMotorDatabase, incident_id: str) -> Optional[dict]:
    try:
        doc = await db.incidents.find_one({"_id": ObjectId(incident_id)})
    except Exception:
        return None
    return _serialize(doc) if doc else None
