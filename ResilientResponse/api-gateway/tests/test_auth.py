"""
Tests for API Gateway authentication endpoints.
Requires: pip install pytest pytest-asyncio httpx

Run: pytest tests/ -v
"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from main import app


MOCK_ADMIN = {
    "_id": "507f1f77bcf86cd799439011",
    "id": "507f1f77bcf86cd799439011",
    "email": "admin@test.local",
    "password_hash": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "secret"
    "role": "ADMIN",
    "name": "Test Admin",
    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow(),
}


@pytest.mark.asyncio
async def test_health():
    """Health endpoint returns ok."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["service"] == "api-gateway"


@pytest.mark.asyncio
async def test_login_invalid_credentials():
    """Login with wrong password returns 401."""
    with patch("app.routers.auth.find_admin_by_email", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = MOCK_ADMIN
        with patch("app.routers.auth.verify_password", return_value=False):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/auth/login", json={"email": "admin@test.local", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user():
    """Login with unknown email returns 401."""
    with patch("app.routers.auth.find_admin_by_email", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = None
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/auth/login", json={"email": "nobody@test.local", "password": "anything"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_success():
    """Valid credentials return access token and admin info."""
    with patch("app.routers.auth.find_admin_by_email", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = MOCK_ADMIN
        with patch("app.routers.auth.verify_password", return_value=True):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/auth/login", json={"email": "admin@test.local", "password": "secret"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["admin"]["email"] == "admin@test.local"
    assert data["admin"]["role"] == "ADMIN"


@pytest.mark.asyncio
async def test_me_unauthenticated():
    """GET /api/auth/me without token returns 403."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/auth/me")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_me_authenticated():
    """GET /api/auth/me with valid token returns admin data."""
    from app.auth import create_access_token
    token = create_access_token({"sub": MOCK_ADMIN["id"], "role": "ADMIN"})

    mock_db = MagicMock()
    mock_db.admins.find_one = AsyncMock(return_value=MOCK_ADMIN)

    with patch("app.auth.get_db", return_value=mock_db):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "admin@test.local"


@pytest.mark.asyncio
async def test_protected_endpoint_without_token():
    """Proxy endpoint without token returns 403."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/hospitals")
    assert resp.status_code == 403
