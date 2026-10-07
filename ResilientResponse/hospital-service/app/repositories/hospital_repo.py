"""
Hospital repository — all MongoDB operations for the hospitals collection.

Phase 2: create, list, get, update, delete
Phase 6: search (location + availability filter), reserve_beds, release_beds
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

async def create_hospital(db: AsyncIOMotorDatabase, data: dict) -> dict:
    now = datetime.utcnow()
    data.update({"created_at": now, "updated_at": now})
    result = await db.hospitals.insert_one(data)
    doc = await db.hospitals.find_one({"_id": result.inserted_id})
    return _serialize(doc)


async def list_hospitals(
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
    cursor = db.hospitals.find(query).skip(skip).limit(limit).sort("created_at", -1)
    return [_serialize(doc) async for doc in cursor]


async def count_hospitals(db: AsyncIOMotorDatabase, search: Optional[str] = None) -> int:
    query: dict = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"city": {"$regex": search, "$options": "i"}},
        ]
    return await db.hospitals.count_documents(query)


async def get_hospital(db: AsyncIOMotorDatabase, hospital_id: str) -> Optional[dict]:
    try:
        doc = await db.hospitals.find_one({"_id": ObjectId(hospital_id)})
    except Exception:
        return None
    return _serialize(doc) if doc else None


async def update_hospital(
    db: AsyncIOMotorDatabase,
    hospital_id: str,
    data: dict,
) -> Optional[dict]:
    data["updated_at"] = datetime.utcnow()
    try:
        result = await db.hospitals.find_one_and_update(
            {"_id": ObjectId(hospital_id)},
            {"$set": data},
            return_document=True,
        )
    except Exception:
        return None
    return _serialize(result) if result else None


async def delete_hospital(db: AsyncIOMotorDatabase, hospital_id: str) -> bool:
    try:
        result = await db.hospitals.delete_one({"_id": ObjectId(hospital_id)})
    except Exception:
        return False
    return result.deleted_count > 0


# ── Phase 6: Search ───────────────────────────────────────────────────────────

async def search_hospitals(
    db: AsyncIOMotorDatabase,
    city: Optional[str] = None,
    min_available_beds: Optional[int] = None,
    active_only: bool = True,
    limit: int = 50,
) -> list:
    """
    Filter hospitals by city, minimum available beds, and active status.
    Caller applies geo-filtering (haversine) after fetching from DB.
    """
    query: dict = {}
    if active_only:
        query["status"] = "ACTIVE"
    if city:
        query["city"] = {"$regex": city, "$options": "i"}
    if min_available_beds is not None and min_available_beds > 0:
        query["available_beds"] = {"$gte": min_available_beds}
    cursor = db.hospitals.find(query).limit(limit).sort("available_beds", -1)
    return [_serialize(doc) async for doc in cursor]


# ── Phase 6: Reserve / Release beds ──────────────────────────────────────────

async def reserve_beds(
    db: AsyncIOMotorDatabase,
    hospital_id: str,
    beds: int,
) -> Optional[dict]:
    """
    Atomically decrement available_beds by `beds`.

    Returns the updated hospital document, or None if:
    - Hospital not found
    - Not enough available beds (capacity guard — never goes negative)
    """
    if beds <= 0:
        raise ValueError("beds must be a positive integer")
    try:
        oid = ObjectId(hospital_id)
    except Exception:
        return None

    result = await db.hospitals.find_one_and_update(
        {
            "_id": oid,
            "available_beds": {"$gte": beds},   # capacity guard
            "status": "ACTIVE",
        },
        {
            "$inc": {"available_beds": -beds},
            "$set": {"updated_at": datetime.utcnow()},
        },
        return_document=True,
    )
    return _serialize(result) if result else None


async def release_beds(
    db: AsyncIOMotorDatabase,
    hospital_id: str,
    beds: int,
) -> Optional[dict]:
    """
    Atomically increment available_beds by `beds`, capped at emergency_capacity.

    Returns the updated document, or None if hospital not found.
    """
    if beds <= 0:
        raise ValueError("beds must be a positive integer")
    try:
        oid = ObjectId(hospital_id)
    except Exception:
        return None

    # Fetch current document to enforce cap
    doc = await db.hospitals.find_one({"_id": oid})
    if not doc:
        return None

    current = doc.get("available_beds") or 0
    capacity = doc.get("emergency_capacity")
    new_value = current + beds
    if capacity is not None:
        new_value = min(new_value, capacity)

    result = await db.hospitals.find_one_and_update(
        {"_id": oid},
        {
            "$set": {
                "available_beds": new_value,
                "updated_at": datetime.utcnow(),
            }
        },
        return_document=True,
    )
    return _serialize(result) if result else None
