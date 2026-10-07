import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import CORS_ORIGINS
from app.database import get_db, close_db
from app.routers.registry import router as registry_router
from app.monitor import monitor_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("registry")

_monitor_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _monitor_task
    # Run one immediate check cycle so the dashboard has data right away
    from app.monitor import run_health_check_cycle
    try:
        await run_health_check_cycle()
    except Exception as exc:
        logger.warning("Initial health check cycle failed: %s", exc)
    # Start background monitor loop
    _monitor_task = asyncio.create_task(monitor_loop())
    logger.info("Service Registry started — monitor loop running")
    yield
    if _monitor_task and not _monitor_task.done():
        _monitor_task.cancel()
        try:
            await _monitor_task
        except asyncio.CancelledError:
            pass
    await close_db()


app = FastAPI(
    title="Service Registry",
    description="Service registration, discovery, and health monitoring",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(registry_router)


# ── Backward-compatible /api/services ──────────────────────────────────────────
# The Phase 2 frontend calls GET /api/services via the API Gateway proxy.
# Keep this endpoint so the existing frontend continues to work while we
# also upgrade it to show registry data.

@app.get("/api/services")
async def get_services_compat():
    """Backward-compatible endpoint — returns all registry instances."""
    db = get_db()
    from app.repositories.registry_repo import list_registry, list_health
    instances = await list_registry(db)
    health_records = await list_health(db)
    health_map = {(h["service_name"], h["instance_id"]): h for h in health_records}
    items = []
    for inst in instances:
        h = health_map.get((inst["service_name"], inst["instance_id"]), {})
        items.append({
            "service_name": inst["service_name"],
            "instance_id": inst["instance_id"],
            "base_url": inst["base_url"],
            "status": inst.get("status", "UNKNOWN"),
            "version": inst.get("version", "unknown"),
            "instance_role": inst.get("instance_role", "PRIMARY"),
            "response_time_ms": h.get("response_time_ms"),
            "last_checked": h.get("last_checked"),
            "error": h.get("error"),
            "last_heartbeat": inst.get("last_heartbeat"),
            "registered_at": inst.get("registered_at"),
        })
    return {"items": items, "total": len(items)}


@app.get("/health")
async def health():
    db = get_db()
    try:
        await db.command("ping")
        db_status = "ok"
    except Exception:
        db_status = "unavailable"
    return {"status": "ok", "service": "service-registry", "version": "0.3.0", "db": db_status}


@app.get("/")
async def root():
    return {"message": "ResilientResponse Service Registry", "version": "0.3.0"}
