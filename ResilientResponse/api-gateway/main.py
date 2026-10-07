import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from app.config import CORS_ORIGINS
from app.database import get_db, close_db
from app.repositories.admin_repo import create_admin_if_not_exists
from app.routers.auth import router as auth_router
from app.routers.proxy import router as proxy_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-seed admin on startup
    admin_email = os.getenv("ADMIN_EMAIL", "admin@resilientresponse.local")
    admin_password = os.getenv("ADMIN_PASSWORD", "Admin@1234!")
    admin_name = os.getenv("ADMIN_NAME", "System Administrator")
    db = get_db()
    created = await create_admin_if_not_exists(db, admin_email, admin_password, admin_name)
    if created:
        print(f"[startup] Admin seeded: {admin_email}")
    yield
    await close_db()


app = FastAPI(
    title="API Gateway",
    description="Single entry point for all ResilientResponse client requests",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(proxy_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "api-gateway"}


@app.get("/")
async def root():
    return {"message": "ResilientResponse API Gateway", "version": "0.2.0"}
