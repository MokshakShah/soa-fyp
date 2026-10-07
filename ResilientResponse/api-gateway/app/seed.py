"""
Seed script: creates the initial ADMIN account if it does not exist.
Run: python -m app.seed
"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from app.database import get_db, close_db
from app.repositories.admin_repo import create_admin_if_not_exists


async def seed():
    email = os.getenv("ADMIN_EMAIL", "admin@resilientresponse.local")
    password = os.getenv("ADMIN_PASSWORD", "Admin@1234!")
    name = os.getenv("ADMIN_NAME", "System Administrator")

    db = get_db()
    created = await create_admin_if_not_exists(db, email, password, name)
    if created:
        print(f"[seed] Admin account created: {email}")
    else:
        print(f"[seed] Admin account already exists: {email}")
    await close_db()


if __name__ == "__main__":
    asyncio.run(seed())
