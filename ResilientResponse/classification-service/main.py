import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.config import CORS_ORIGINS
from app.registry_client import register_with_registry
from app.routers.classification import router as classification_router

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


logger = logging.getLogger("classification-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    registered = await register_with_registry()
    logger.info("[startup] Classification Service started — registry_registered=%s", registered)
    yield


app = FastAPI(
    title="Classification Service",
    description="Rule-based disaster alert classification — transparent, deterministic, no AI/LLM",
    version="0.5.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(classification_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "classification-service", "version": "0.5.0"}


@app.get("/")
async def root():
    return {"message": "ResilientResponse Classification Service", "version": "0.5.0"}
