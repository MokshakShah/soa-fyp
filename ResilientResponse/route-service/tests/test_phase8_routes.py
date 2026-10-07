"""Phase 8 — Route Service tests."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from main import app
from app.providers.osrm import RoutingProviderError


MOCK_ROUTE_DOC = {
    "id": "507f1f77bcf86cd799439011",
    "incident_id": "inc-1",
    "workflow_id": None,
    "origin_lat": 40.7128,
    "origin_lon": -74.0060,
    "destination_lat": 40.7580,
    "destination_lon": -73.9855,
    "distance_km": 5.2,
    "estimated_travel_minutes": 12.5,
    "status": "CALCULATED",
    "provider": "osrm",
    "geometry": [[40.7128, -74.0060], [40.7580, -73.9855]],
    "error": None,
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
    assert resp.json()["service"] == "route-service"


@pytest.mark.asyncio
async def test_calculate_route_success():
    provider_result = {
        "distance_km": 5.2,
        "estimated_travel_minutes": 12.5,
        "geometry": [[40.71, -74.0], [40.75, -73.98]],
    }
    with patch("app.routers.routes.fetch_route", new_callable=AsyncMock, return_value=provider_result):
        with patch("app.routers.routes.create_route", new_callable=AsyncMock, return_value=MOCK_ROUTE_DOC):
            with patch("app.routers.routes.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.post("/api/routes/calculate", json={
                        "origin_lat": 40.7128,
                        "origin_lon": -74.0060,
                        "destination_lat": 40.7580,
                        "destination_lon": -73.9855,
                        "incident_id": "inc-1",
                    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["route"]["status"] == "CALCULATED"
    assert body["route"]["distance_km"] == 5.2


@pytest.mark.asyncio
async def test_calculate_invalid_coordinates():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/routes/calculate", json={
            "origin_lat": 40.0,
            "origin_lon": -74.0,
            "destination_lat": 40.0,
            "destination_lon": -74.0,
        })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_provider_failure_persists_and_returns_503():
    unavailable_doc = {**MOCK_ROUTE_DOC, "status": "PROVIDER_UNAVAILABLE", "distance_km": None, "error": "down"}
    with patch("app.routers.routes.fetch_route", new_callable=AsyncMock, side_effect=RoutingProviderError("down")):
        with patch("app.routers.routes.create_route", new_callable=AsyncMock, return_value=unavailable_doc):
            with patch("app.routers.routes.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.post("/api/routes/calculate", json={
                        "origin_lat": 40.7128,
                        "origin_lon": -74.0060,
                        "destination_lat": 40.7580,
                        "destination_lon": -73.9855,
                    })
    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert detail["route"]["status"] == "PROVIDER_UNAVAILABLE"


@pytest.mark.asyncio
async def test_get_route_by_id():
    with patch("app.routers.routes.get_route", new_callable=AsyncMock, return_value=MOCK_ROUTE_DOC):
        with patch("app.routers.routes.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get(f"/api/routes/{MOCK_ROUTE_DOC['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == MOCK_ROUTE_DOC["id"]


@pytest.mark.asyncio
async def test_get_route_not_found():
    with patch("app.routers.routes.get_route", new_callable=AsyncMock, return_value=None):
        with patch("app.routers.routes.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/routes/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_registry_registration():
    from app.registry_client import register_with_registry

    class FakeResp:
        status_code = 200

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, url, json):
            assert json["service_name"] == "route-service"
            return FakeResp()

    with patch.dict("os.environ", {"SERVICE_BASE_URL": "http://route-service:8006"}, clear=False):
        with patch("app.registry_client.httpx.AsyncClient", return_value=FakeClient()):
            ok = await register_with_registry()
    assert ok is True


@pytest.mark.asyncio
async def test_osrm_provider_parses_response():
    from app.providers.osrm import fetch_route

    class FakeResp:
        status_code = 200

        def json(self):
            return {
                "code": "Ok",
                "routes": [{
                    "distance": 5000,
                    "duration": 600,
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-74.0, 40.71], [-73.98, 40.75]],
                    },
                }],
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def get(self, url):
            return FakeResp()

    with patch("app.providers.osrm.httpx.AsyncClient", return_value=FakeClient()):
        result = await fetch_route(40.71, -74.0, 40.75, -73.98)
    assert result["distance_km"] == 5.0
    assert result["geometry"][0] == [40.71, -74.0]
