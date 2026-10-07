import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import CORS_ORIGINS, NOTIFICATION_PROVIDER
from app.database import get_db, close_db
from app.repositories.notification_repo import ensure_indexes
from app.routers.notifications import router as notifications_router
from app.registry_client import register_with_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("notification-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_db()
    await ensure_indexes(db)
    await register_with_registry()
    logger.info("Notification Service started — provider=%s", NOTIFICATION_PROVIDER)
    yield
    await close_db()


app = FastAPI(
    title="Notification Service",
    description="Creates, delivers, and tracks emergency notifications",
    version="0.9.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notifications_router)


@app.get("/health")
async def health():
    db = get_db()
    try:
        await db.command("ping")
        db_status = "ok"
    except Exception:
        db_status = "unavailable"
    return {
        "status": "ok",
        "service": "notification-service",
        "version": "0.9.0",
        "provider": NOTIFICATION_PROVIDER,
        "db": db_status,
    }


@app.get("/")
async def root():
    return {"message": "ResilientResponse Notification Service", "version": "0.9.0"}
