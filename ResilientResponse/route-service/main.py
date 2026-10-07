import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS, ROUTING_PROVIDER_NAME, ROUTING_PROVIDER_URL
from app.database import get_db, close_db
from app.registry_client import register_with_registry
from app.routers.routes import router as routes_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("route-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    registered = await register_with_registry()
    logger.info(
        "[startup] Route Service started — provider=%s registry_registered=%s",
        ROUTING_PROVIDER_NAME, registered,
    )
    yield
    await close_db()


app = FastAPI(
    title="Route Service",
    description="Emergency route calculation for workflow coordination",
    version="0.8.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_router)


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
        "service": "route-service",
        "version": "0.8.0",
        "db": db_status,
        "routing_provider": ROUTING_PROVIDER_NAME,
        "routing_provider_url": ROUTING_PROVIDER_URL,
    }


@app.get("/")
async def root():
    return {"message": "ResilientResponse Route Service", "version": "0.8.0"}
