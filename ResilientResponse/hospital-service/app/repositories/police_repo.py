"""
Police station repository — Phase 2 CRUD + Phase 6 search.
"""
from datetime import datetime
from typing import Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


def _serialize(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


# ── Phase 2: CRUD ─────────────────────────────────────────────────────────────

async def create_police_station(db: AsyncIOMotorDatabase, data: dict) -> dict:
    now = datetime.utcnow()
    data.update({"created_at": now, "updated_at": now})
    result = await db.police_stations.insert_one(data)
    doc = await db.police_stations.find_one({"_id": result.inserted_id})
    return _serialize(doc)


async def list_police_stations(
    db: AsyncIOMotorDatabase,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
) -> list:
    query: dict = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"city": {"$regex": search, "$options": "i"}},
        ]
    cursor = db.police_stations.find(query).skip(skip).limit(limit).sort("created_at", -1)
    return [_serialize(doc) async for doc in cursor]


async def count_police_stations(
    db: AsyncIOMotorDatabase,
    search: Optional[str] = None,
) -> int:
    query: dict = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"city": {"$regex": search, "$options": "i"}},
        ]
    return await db.police_stations.count_documents(query)


async def get_police_station(
    db: AsyncIOMotorDatabase,
    station_id: str,
) -> Optional[dict]:
    try:
        doc = await db.police_stations.find_one({"_id": ObjectId(station_id)})
    except Exception:
        return None
    return _serialize(doc) if doc else None


async def update_police_station(
    db: AsyncIOMotorDatabase,
    station_id: str,
    data: dict,
) -> Optional[dict]:
    data["updated_at"] = datetime.utcnow()
    try:
        result = await db.police_stations.find_one_and_update(
            {"_id": ObjectId(station_id)},
            {"$set": data},
            return_document=True,
        )
    except Exception:
        return None
    return _serialize(result) if result else None


async def delete_police_station(
    db: AsyncIOMotorDatabase,
    station_id: str,
) -> bool:
    try:
        result = await db.police_stations.delete_one({"_id": ObjectId(station_id)})
    except Exception:
        return False
    return result.deleted_count > 0


# ── Phase 6: Search ───────────────────────────────────────────────────────────

async def search_police_stations(
    db: AsyncIOMotorDatabase,
    city: Optional[str] = None,
    active_only: bool = True,
    limit: int = 50,
) -> list:
    """
    Filter police stations by city and active status.
    Caller applies geo-filtering (haversine) after fetching from DB.
    """
    query: dict = {}
    if active_only:
        query["status"] = "ACTIVE"
    if city:
        query["city"] = {"$regex": city, "$options": "i"}
    cursor = db.police_stations.find(query).limit(limit).sort("name", 1)
    return [_serialize(doc) async for doc in cursor]
