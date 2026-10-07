"""
Repository layer for the service_registry and service_health collections.
All MongoDB interactions live here — routers and monitors only call these functions.
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


# ── Registry ─────────────────────────────────────────────────────────────────

async def upsert_registration(db: AsyncIOMotorDatabase, data: dict) -> dict:
    """
    Create or update a registry record keyed on (service_name, instance_id).
    Returns the final document.
    """
    now = datetime.utcnow()
    key = {"service_name": data["service_name"], "instance_id": data["instance_id"]}

    existing = await db.service_registry.find_one(key)
    if existing:
        update_fields = {
            "base_url": data["base_url"],
            "version": data["version"],
            "instance_role": data["instance_role"],
            "metadata": data.get("metadata"),
            "status": existing.get("status", "UNKNOWN"),
            "updated_at": now,
            "last_heartbeat": now,
        }
        await db.service_registry.update_one(key, {"$set": update_fields})
        doc = await db.service_registry.find_one(key)
    else:
        insert = {
            **key,
            "base_url": data["base_url"],
            "version": data["version"],
            "instance_role": data["instance_role"],
            "metadata": data.get("metadata"),
            "status": "UNKNOWN",
            "last_heartbeat": now,
            "registered_at": now,
            "updated_at": now,
        }
        await db.service_registry.insert_one(insert)
        doc = await db.service_registry.find_one(key)

    return _serialize(doc)


async def list_registry(db: AsyncIOMotorDatabase) -> list:
    cursor = db.service_registry.find({}).sort([("service_name", 1), ("instance_role", 1)])
    return [_serialize(doc) async for doc in cursor]


async def list_registry_by_service(db: AsyncIOMotorDatabase, service_name: str) -> list:
    cursor = db.service_registry.find({"service_name": service_name}).sort("instance_role", 1)
    return [_serialize(doc) async for doc in cursor]


async def get_registry_record(db: AsyncIOMotorDatabase, service_name: str, instance_id: str) -> Optional[dict]:
    doc = await db.service_registry.find_one({"service_name": service_name, "instance_id": instance_id})
    return _serialize(doc) if doc else None


async def update_instance_status(
    db: AsyncIOMotorDatabase,
    service_name: str,
    instance_id: str,
    status: str,
    last_heartbeat: Optional[datetime] = None,
) -> None:
    update: dict = {"status": status, "updated_at": datetime.utcnow()}
    if last_heartbeat:
        update["last_heartbeat"] = last_heartbeat
    await db.service_registry.update_one(
        {"service_name": service_name, "instance_id": instance_id},
        {"$set": update},
    )


# ── Health ────────────────────────────────────────────────────────────────────

async def upsert_health(
    db: AsyncIOMotorDatabase,
    service_name: str,
    instance_id: str,
    status: str,
    response_time_ms: Optional[int],
    error: Optional[str],
    details: Optional[dict] = None,
) -> None:
    now = datetime.utcnow()
    await db.service_health.update_one(
        {"service_name": service_name, "instance_id": instance_id},
        {
            "$set": {
                "service_name": service_name,
                "instance_id": instance_id,
                "status": status,
                "response_time_ms": response_time_ms,
                "last_checked": now,
                "error": error,
                "details": details,
            }
        },
        upsert=True,
    )


async def get_health(db: AsyncIOMotorDatabase, service_name: str, instance_id: str) -> Optional[dict]:
    doc = await db.service_health.find_one({"service_name": service_name, "instance_id": instance_id})
    if not doc:
        return None
    doc = dict(doc)
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


async def list_health(db: AsyncIOMotorDatabase) -> list:
    cursor = db.service_health.find({}).sort("service_name", 1)
    docs = []
    async for doc in cursor:
        doc = dict(doc)
        doc["id"] = str(doc["_id"])
        del doc["_id"]
        docs.append(doc)
    return docs
