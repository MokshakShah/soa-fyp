"""
Development seed: creates sample resources if they don't exist. Idempotent.
"""
import asyncio
from datetime import datetime
from app.database import get_db, close_db

SAMPLE_RESOURCES = [
    {
        "name": "Ambulance Unit A1",
        "type": "AMBULANCE",
        "quantity": 3,
        "available_quantity": 3,
        "unit": "vehicles",
        "location": "Connaught Place Fire Station",
        "city": "New Delhi",
        "state": "Delhi",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "status": "AVAILABLE",
    },
    {
        "name": "Medical Supply Kit - Level 1",
        "type": "MEDICAL_KIT",
        "quantity": 50,
        "available_quantity": 50,
        "unit": "kits",
        "location": "New Delhi Central Depot",
        "city": "New Delhi",
        "state": "Delhi",
        "latitude": 28.6140,
        "longitude": 77.2088,
        "status": "AVAILABLE",
    },
    {
        "name": "Rescue Vehicle B2",
        "type": "RESCUE_VEHICLE",
        "quantity": 2,
        "available_quantity": 2,
        "unit": "vehicles",
        "location": "Bandra Rescue Station",
        "city": "Mumbai",
        "state": "Maharashtra",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "status": "AVAILABLE",
    },
    {
        "name": "Emergency Water Tanks",
        "type": "WATER",
        "quantity": 20,
        "available_quantity": 15,
        "unit": "tanks",
        "location": "Bengaluru Emergency Depot",
        "city": "Bengaluru",
        "state": "Karnataka",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "status": "AVAILABLE",
    },
    {
        "name": "Emergency Food Rations",
        "type": "FOOD",
        "quantity": 500,
        "available_quantity": 500,
        "unit": "packs",
        "location": "New Delhi Central Depot",
        "city": "New Delhi",
        "state": "Delhi",
        "latitude": 28.6140,
        "longitude": 77.2088,
        "status": "AVAILABLE",
    },
]


async def seed():
    db = get_db()
    now = datetime.utcnow()
    await db.resources.delete_many({"name": "Medical Supply Kit — Level 1"})
    for resource in SAMPLE_RESOURCES:
        await db.resources.update_one(
            {"name": resource["name"]},
            {"$set": {**resource, "updated_at": now}, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    print(f"[seed] Upserted {len(SAMPLE_RESOURCES)} India resource records")
    await close_db()


if __name__ == "__main__":
    asyncio.run(seed())
