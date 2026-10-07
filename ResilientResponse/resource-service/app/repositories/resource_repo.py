"""
Resource repository — Phase 2 CRUD + Phase 6 search, allocate, release.
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

async def create_resource(db: AsyncIOMotorDatabase, data: dict) -> dict:
    now = datetime.utcnow()
    data.update({"created_at": now, "updated_at": now})
    result = await db.resources.insert_one(data)
    doc = await db.resources.find_one({"_id": result.inserted_id})
    return _serialize(doc)


async def list_resources(
    db: AsyncIOMotorDatabase,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    resource_type: Optional[str] = None,
) -> list:
    query: dict = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"type": {"$regex": search, "$options": "i"}},
            {"city": {"$regex": search, "$options": "i"}},
        ]
    if resource_type:
        query["type"] = {"$regex": resource_type, "$options": "i"}
    cursor = db.resources.find(query).skip(skip).limit(limit).sort("created_at", -1)
    return [_serialize(doc) async for doc in cursor]


async def count_resources(
    db: AsyncIOMotorDatabase,
    search: Optional[str] = None,
    resource_type: Optional[str] = None,
) -> int:
    query: dict = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"type": {"$regex": search, "$options": "i"}},
            {"city": {"$regex": search, "$options": "i"}},
        ]
    if resource_type:
        query["type"] = {"$regex": resource_type, "$options": "i"}
    return await db.resources.count_documents(query)


async def get_resource(db: AsyncIOMotorDatabase, resource_id: str) -> Optional[dict]:
    try:
        doc = await db.resources.find_one({"_id": ObjectId(resource_id)})
    except Exception:
        return None
    return _serialize(doc) if doc else None


async def update_resource(
    db: AsyncIOMotorDatabase,
    resource_id: str,
    data: dict,
) -> Optional[dict]:
    data["updated_at"] = datetime.utcnow()
    try:
        result = await db.resources.find_one_and_update(
            {"_id": ObjectId(resource_id)},
            {"$set": data},
            return_document=True,
        )
    except Exception:
        return None
    return _serialize(result) if result else None


async def delete_resource(db: AsyncIOMotorDatabase, resource_id: str) -> bool:
    try:
        result = await db.resources.delete_one({"_id": ObjectId(resource_id)})
    except Exception:
        return False
    return result.deleted_count > 0


# ── Phase 6: Search ───────────────────────────────────────────────────────────

async def search_resources(
    db: AsyncIOMotorDatabase,
    resource_type: Optional[str] = None,
    city: Optional[str] = None,
    available_only: bool = True,
    min_quantity: Optional[int] = None,
    limit: int = 50,
) -> list:
    """
    Filter resources by type, city, availability, and minimum quantity.
    Caller applies geo-filtering after this returns.
    """
    query: dict = {}
    if available_only:
        query["available_quantity"] = {"$gt": 0}
        query["status"] = {"$in": ["AVAILABLE", "DEPLOYED"]}
    if resource_type:
        query["type"] = {"$regex": resource_type, "$options": "i"}
    if city:
        query["city"] = {"$regex": city, "$options": "i"}
    if min_quantity is not None and min_quantity > 0:
        # Override available_quantity filter with specific minimum
        query["available_quantity"] = {"$gte": min_quantity}
    cursor = db.resources.find(query).limit(limit).sort("available_quantity", -1)
    return [_serialize(doc) async for doc in cursor]


# ── Phase 6: Allocate / Release ────────────────────────────────────────────────

async def allocate_resource(
    db: AsyncIOMotorDatabase,
    resource_id: str,
    quantity: int,
) -> Optional[dict]:
    """
    Atomically decrement available_quantity by `quantity`.

    Returns updated document, or None if:
    - Resource not found
    - Insufficient available_quantity (guard: never goes negative)
    - Resource status is INACTIVE or MAINTENANCE
    """
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    try:
        oid = ObjectId(resource_id)
    except Exception:
        return None

    result = await db.resources.find_one_and_update(
        {
            "_id": oid,
            "available_quantity": {"$gte": quantity},   # allocation guard
            "status": {"$in": ["AVAILABLE", "DEPLOYED"]},
        },
        {
            "$inc": {"available_quantity": -quantity},
            "$set": {"updated_at": datetime.utcnow()},
        },
        return_document=True,
    )
    if not result:
        return None

    # Update status to DEPLOYED if no units left
    updated = _serialize(result)
    if updated.get("available_quantity", 0) == 0:
        await db.resources.update_one(
            {"_id": oid},
            {"$set": {"status": "DEPLOYED", "updated_at": datetime.utcnow()}},
        )
        updated["status"] = "DEPLOYED"

    return updated


async def release_resource(
    db: AsyncIOMotorDatabase,
    resource_id: str,
    quantity: int,
) -> Optional[dict]:
    """
    Atomically increment available_quantity by `quantity`, capped at total quantity.
    """
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    try:
        oid = ObjectId(resource_id)
    except Exception:
        return None

    doc = await db.resources.find_one({"_id": oid})
    if not doc:
        return None

    current_avail = doc.get("available_quantity", 0)
    total = doc.get("quantity", 0)
    new_avail = min(current_avail + quantity, total)

    result = await db.resources.find_one_and_update(
        {"_id": oid},
        {
            "$set": {
                "available_quantity": new_avail,
                "status": "AVAILABLE" if new_avail > 0 else doc.get("status", "AVAILABLE"),
                "updated_at": datetime.utcnow(),
            }
        },
        return_document=True,
    )
    return _serialize(result) if result else None
