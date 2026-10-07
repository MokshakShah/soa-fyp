"""
Tests for Resource Service CRUD endpoints.
Run: pytest tests/ -v
"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from main import app

MOCK_RESOURCE = {
    "id": "507f1f77bcf86cd799439012",
    "name": "Ambulance Unit A1",
    "type": "AMBULANCE",
    "quantity": 3,
    "available_quantity": 3,
    "unit": "vehicles",
    "location": "Central Station",
    "city": "Test City",
    "state": "TC",
    "latitude": 40.7128,
    "longitude": -74.0060,
    "status": "AVAILABLE",
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
    assert resp.json()["service"] == "resource-service"


@pytest.mark.asyncio
async def test_list_resources():
    with patch("app.routers.resources.list_resources", new_callable=AsyncMock, return_value=[MOCK_RESOURCE]):
        with patch("app.routers.resources.count_resources", new_callable=AsyncMock, return_value=1):
            with patch("app.routers.resources.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/resources")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == MOCK_RESOURCE["name"]


@pytest.mark.asyncio
async def test_create_resource():
    payload = {"name": "Test Kit", "type": "MEDICAL_KIT", "quantity": 10, "available_quantity": 10}
    with patch("app.routers.resources.create_resource", new_callable=AsyncMock, return_value=MOCK_RESOURCE):
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/resources", json=payload)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_resource_missing_fields():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/resources", json={"name": "incomplete"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_resource_not_found():
    with patch("app.routers.resources.get_resource", new_callable=AsyncMock, return_value=None):
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/resources/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_resource():
    with patch("app.routers.resources.update_resource", new_callable=AsyncMock, return_value={**MOCK_RESOURCE, "status": "DEPLOYED"}):
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.put("/api/resources/507f1f77bcf86cd799439012", json={"status": "DEPLOYED"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_resource():
    with patch("app.routers.resources.delete_resource", new_callable=AsyncMock, return_value=True):
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.delete("/api/resources/507f1f77bcf86cd799439012")
    assert resp.status_code == 204
