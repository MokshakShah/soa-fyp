import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import CORS_ORIGINS
from app.database import get_db, close_db
from app.routers.resources import router as resources_router
from app.seed import seed as run_seed
from app.registry_client import register_with_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("resource-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_seed()
    registered = await register_with_registry()
    logger.info("[startup] Resource Service started — registry_registered=%s", registered)
    yield
    await close_db()


app = FastAPI(
    title="Resource Service",
    description="Tracks, searches, and manages emergency resource allocation",
    version="0.6.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resources_router)


@app.get("/health")
async def health():
    db = get_db()
    try:
        await db.command("ping")
        db_status = "ok"
    except Exception:
        db_status = "unavailable"
    return {"status": "ok", "service": "resource-service", "version": "0.6.0", "db": db_status}


@app.get("/")
async def root():
    return {"message": "ResilientResponse Resource Service", "version": "0.6.0"}
