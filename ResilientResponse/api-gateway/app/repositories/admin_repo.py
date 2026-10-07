from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.auth import hash_password


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


async def find_admin_by_email(db: AsyncIOMotorDatabase, email: str):
    doc = await db.admins.find_one({"email": email.lower()})
    if doc:
        doc["id"] = str(doc["_id"])
    return doc


async def find_admin_by_id(db: AsyncIOMotorDatabase, admin_id: str):
    try:
        doc = await db.admins.find_one({"_id": ObjectId(admin_id)})
    except Exception:
        return None
    if doc:
        doc["id"] = str(doc["_id"])
    return doc


async def create_admin_if_not_exists(db: AsyncIOMotorDatabase, email: str, password: str, name: str) -> bool:
    """Returns True if created, False if already existed."""
    existing = await db.admins.find_one({"email": email.lower()})
    if existing:
        return False
    now = datetime.utcnow()
    await db.admins.insert_one({
        "email": email.lower(),
        "password_hash": hash_password(password),
        "role": "ADMIN",
        "name": name,
        "created_at": now,
        "updated_at": now,
    })
    return True
