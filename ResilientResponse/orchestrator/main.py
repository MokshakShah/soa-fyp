import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import CORS_ORIGINS
from app.database import get_db, close_db
from app.routers.workflows import router as workflows_router
from app.registry_client import register_with_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("orchestrator")


@asynccontextmanager
async def lifespan(app: FastAPI):
    registered = await register_with_registry()
    logger.info("[startup] Orchestrator started — registry_registered=%s", registered)
    yield
    await close_db()


app = FastAPI(
    title="Orchestrator",
    description="Dynamic workflow execution engine for emergency response",
    version="0.7.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workflows_router)


@app.get("/health")
async def health():
    db = get_db()
    try:
        await db.command("ping")
        db_status = "ok"
    except Exception:
        db_status = "unavailable"
    return {"status": "ok", "service": "orchestrator", "version": "0.7.0", "db": db_status}


@app.get("/")
async def root():
    return {"message": "ResilientResponse Orchestrator", "version": "0.7.0"}
