import logging
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import CORS_ORIGINS, ALERT_TODAY_ONLY
from app.database import get_db, close_db
from app.routers.alerts import router as alerts_router
from app.routers.incidents import router as incidents_router
from app.registry_client import register_with_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("alert-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    registered = await register_with_registry()
    logger.info("[startup] Alert Service started — registry_registered=%s", registered)
    if ALERT_TODAY_ONLY:
        start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        cleanup = await get_db().alerts.delete_many({"issued_at": {"$lt": start}})
        if cleanup.deleted_count:
            logger.info("[startup] Removed %d alerts from previous days", cleanup.deleted_count)
    demo_cleanup = await get_db().alerts.delete_many({"source": "DEMO"})
    if demo_cleanup.deleted_count:
        logger.info("[startup] Removed %d legacy DEMO alerts", demo_cleanup.deleted_count)
    repaired = await get_db().alerts.update_many(
        {"status": {"$exists": False}},
        {"$set": {"status": "NEW"}},
    )
    if repaired.modified_count:
        logger.info("[startup] Repaired %d alerts missing status", repaired.modified_count)
    yield
    await close_db()


app = FastAPI(
    title="Alert Service",
    description="Receives, normalizes, and manages disaster alerts via adapter pattern",
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(alerts_router)
app.include_router(incidents_router)


@app.get("/health")
async def health():
    db = get_db()
    try:
        await db.command("ping")
        db_status = "ok"
    except Exception:
        db_status = "unavailable"
    return {"status": "ok", "service": "alert-service", "version": "0.4.0", "db": db_status}


@app.get("/")
async def root():
    return {"message": "ResilientResponse Alert Service", "version": "0.4.0"}
