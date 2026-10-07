"""
Tests for Hospital Service CRUD endpoints.
Run: pytest tests/ -v
"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from main import app

MOCK_HOSPITAL = {
    "id": "507f1f77bcf86cd799439011",
    "name": "Test General Hospital",
    "registration_number": "HOS-TEST",
    "phone": "+1-555-0100",
    "emergency_phone": "+1-555-0911",
    "email": "test@hospital.example",
    "address": "1 Test Street",
    "city": "Test City",
    "state": "TC",
    "latitude": 40.7128,
    "longitude": -74.0060,
    "emergency_capacity": 100,
    "available_beds": 25,
    "icu_beds": 10,
    "status": "ACTIVE",
    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow(),
}


@pytest.mark.asyncio
async def test_health():
    with patch("main.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_db.command = AsyncMock(return_value={"ok": 1})
        mock_get_db.return_value = mock_db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "hospital-service"


@pytest.mark.asyncio
async def test_list_hospitals_empty():
    with patch("app.routers.hospitals.get_db") as mock_get_db:
        mock_db = MagicMock()
        with patch("app.routers.hospitals.list_hospitals", new_callable=AsyncMock, return_value=[]) as ml:
            with patch("app.routers.hospitals.count_hospitals", new_callable=AsyncMock, return_value=0):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/hospitals")
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_get_hospital_not_found():
    with patch("app.routers.hospitals.get_hospital", new_callable=AsyncMock, return_value=None):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/hospitals/nonexistentid")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_hospital():
    payload = {
        "name": "New Hospital",
        "phone": "+1-555-0200",
        "city": "New City",
        "status": "ACTIVE",
    }
    with patch("app.routers.hospitals.create_hospital", new_callable=AsyncMock, return_value=MOCK_HOSPITAL):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/hospitals", json=payload)
    assert resp.status_code == 201
    assert resp.json()["name"] == MOCK_HOSPITAL["name"]


@pytest.mark.asyncio
async def test_create_hospital_missing_required():
    """Missing required fields should return 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/hospitals", json={"name": "Only Name"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_hospital():
    with patch("app.routers.hospitals.update_hospital", new_callable=AsyncMock, return_value={**MOCK_HOSPITAL, "name": "Updated"}):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.put("/api/hospitals/507f1f77bcf86cd799439011", json={"name": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"


@pytest.mark.asyncio
async def test_update_hospital_not_found():
    with patch("app.routers.hospitals.update_hospital", new_callable=AsyncMock, return_value=None):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.put("/api/hospitals/notfound", json={"name": "X"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_hospital():
    with patch("app.routers.hospitals.delete_hospital", new_callable=AsyncMock, return_value=True):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.delete("/api/hospitals/507f1f77bcf86cd799439011")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_hospital_not_found():
    with patch("app.routers.hospitals.delete_hospital", new_callable=AsyncMock, return_value=False):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.delete("/api/hospitals/notfound")
    assert resp.status_code == 404
