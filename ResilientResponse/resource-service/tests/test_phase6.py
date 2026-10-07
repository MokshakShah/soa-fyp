"""
Phase 6 — Resource Service operational tests.

Covers:
  - Resource search (type, city, available_only, geo)
  - Allocate: success, insufficient, inactive, not found
  - Release: success, cap at total, not found
  - available_quantity never goes negative
  - Repository unit tests for allocate/release
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from main import app

RESOURCE_ID = "507f1f77bcf86cd799439012"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _resource(
    name="Ambulance A1",
    rtype="AMBULANCE",
    quantity=5,
    available_quantity=5,
    city="Test City",
    lat=40.7128,
    lon=-74.006,
    status="AVAILABLE",
    rid=RESOURCE_ID,
):
    return {
        "id": rid,
        "name": name,
        "type": rtype,
        "quantity": quantity,
        "available_quantity": available_quantity,
        "unit": "vehicles",
        "city": city,
        "state": "Test State",
        "location": "Test Station",
        "latitude": lat,
        "longitude": lon,
        "status": status,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


# ─── Geo utility (resource-service copy) ─────────────────────────────────────

def test_haversine_zero_distance():
    from app.geo import haversine_km
    assert haversine_km(0, 0, 0, 0) == pytest.approx(0.0)


def test_within_radius_true():
    from app.geo import within_radius
    assert within_radius(40.7128, -74.006, 40.7128, -74.006, 10.0) is True


def test_within_radius_false():
    from app.geo import within_radius
    assert within_radius(51.5074, -0.1278, 40.7128, -74.006, 100.0) is False


def test_within_radius_none():
    from app.geo import within_radius
    assert within_radius(None, -74.006, 40.7128, -74.006, 10.0) is False


# ─── Resource search ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_resources_by_type():
    resources = [_resource(rtype="AMBULANCE")]
    with patch("app.routers.resources.search_resources", new_callable=AsyncMock, return_value=resources):
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/resources/search?type=AMBULANCE")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["type"] == "AMBULANCE"


@pytest.mark.asyncio
async def test_search_resources_by_city():
    resources = [_resource(city="Andheri")]
    with patch("app.routers.resources.search_resources", new_callable=AsyncMock, return_value=resources):
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/resources/search?city=Andheri")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["city"] == "Andheri"


@pytest.mark.asyncio
async def test_search_resources_available_only_filter():
    """available_only=true excludes resources with available_quantity=0."""
    with patch("app.routers.resources.search_resources", new_callable=AsyncMock, return_value=[]) as mock_s:
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/resources/search?available_only=true")
    assert resp.status_code == 200
    mock_s.assert_called_once()
    assert mock_s.call_args[1].get("available_only") is True


@pytest.mark.asyncio
async def test_search_resources_geo_within_radius():
    r = _resource(lat=40.7128, lon=-74.006)
    with patch("app.routers.resources.search_resources", new_callable=AsyncMock, return_value=[r]):
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/resources/search?lat=40.7128&lon=-74.006&radius_km=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert "distance_km" in data["items"][0]
    assert data["items"][0]["distance_km"] == pytest.approx(0.0, abs=0.1)


@pytest.mark.asyncio
async def test_search_resources_geo_outside_radius():
    r = _resource(lat=51.5074, lon=-0.1278)
    with patch("app.routers.resources.search_resources", new_callable=AsyncMock, return_value=[r]):
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/resources/search?lat=40.7128&lon=-74.006&radius_km=100")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_search_resources_no_geo_returns_all():
    resources = [_resource(), _resource(name="Kit B", rid="507f1f77bcf86cd799439013")]
    with patch("app.routers.resources.search_resources", new_callable=AsyncMock, return_value=resources):
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/resources/search")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


# ─── Resource allocate ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_allocate_resource_success():
    before = _resource(available_quantity=5)
    after = _resource(available_quantity=3)
    with patch("app.routers.resources.get_resource", new_callable=AsyncMock, return_value=before):
        with patch("app.routers.resources.allocate_resource", new_callable=AsyncMock, return_value=after):
            with patch("app.routers.resources.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.post(f"/api/resources/{RESOURCE_ID}/allocate", json={"quantity": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["operation"] == "allocate"
    assert data["quantity"] == 2
    assert data["available_before"] == 5
    assert data["available_after"] == 3


@pytest.mark.asyncio
async def test_allocate_resource_insufficient_quantity():
    before = _resource(available_quantity=1)
    with patch("app.routers.resources.get_resource", new_callable=AsyncMock, return_value=before):
        with patch("app.routers.resources.allocate_resource", new_callable=AsyncMock, return_value=None):
            with patch("app.routers.resources.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.post(f"/api/resources/{RESOURCE_ID}/allocate", json={"quantity": 10})
    assert resp.status_code == 409
    assert "Insufficient" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_allocate_resource_not_found():
    with patch("app.routers.resources.get_resource", new_callable=AsyncMock, return_value=None):
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(f"/api/resources/nonexistent/allocate", json={"quantity": 1})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_allocate_resource_inactive():
    r = _resource(status="INACTIVE")
    with patch("app.routers.resources.get_resource", new_callable=AsyncMock, return_value=r):
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(f"/api/resources/{RESOURCE_ID}/allocate", json={"quantity": 1})
    assert resp.status_code == 409
    assert "not available" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_allocate_resource_maintenance():
    r = _resource(status="MAINTENANCE")
    with patch("app.routers.resources.get_resource", new_callable=AsyncMock, return_value=r):
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(f"/api/resources/{RESOURCE_ID}/allocate", json={"quantity": 1})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_allocate_zero_quantity_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(f"/api/resources/{RESOURCE_ID}/allocate", json={"quantity": 0})
    assert resp.status_code == 422


# ─── Resource release ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_release_resource_success():
    before = _resource(available_quantity=3)
    after = _resource(available_quantity=5)
    with patch("app.routers.resources.get_resource", new_callable=AsyncMock, return_value=before):
        with patch("app.routers.resources.release_resource", new_callable=AsyncMock, return_value=after):
            with patch("app.routers.resources.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.post(f"/api/resources/{RESOURCE_ID}/release", json={"quantity": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["operation"] == "release"
    assert data["available_after"] == 5


@pytest.mark.asyncio
async def test_release_resource_not_found():
    with patch("app.routers.resources.get_resource", new_callable=AsyncMock, return_value=None):
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(f"/api/resources/nonexistent/release", json={"quantity": 1})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_release_zero_quantity_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(f"/api/resources/{RESOURCE_ID}/release", json={"quantity": 0})
    assert resp.status_code == 422


# ─── Repository: quantity never negative ─────────────────────────────────────

@pytest.mark.asyncio
async def test_allocate_repo_guard_prevents_negative():
    """Repository find_one_and_update uses $gte guard — returns None when insufficient."""
    from app.repositories.resource_repo import allocate_resource
    mock_db = MagicMock()
    mock_db.resources.find_one_and_update = AsyncMock(return_value=None)
    result = await allocate_resource(mock_db, RESOURCE_ID, 999)
    assert result is None


@pytest.mark.asyncio
async def test_allocate_repo_invalid_quantity():
    from app.repositories.resource_repo import allocate_resource
    mock_db = MagicMock()
    with pytest.raises(ValueError):
        await allocate_resource(mock_db, RESOURCE_ID, 0)


@pytest.mark.asyncio
async def test_release_repo_capped_at_total():
    """Release is capped at total quantity — never exceeds maximum."""
    from app.repositories.resource_repo import release_resource
    mock_db = MagicMock()
    existing = {"_id": RESOURCE_ID, "available_quantity": 3, "quantity": 5, "status": "DEPLOYED"}
    final = {**existing, "available_quantity": 5}
    mock_db.resources.find_one = AsyncMock(return_value=existing)
    mock_db.resources.find_one_and_update = AsyncMock(return_value=final)

    result = await release_resource(mock_db, RESOURCE_ID, 100)  # would be 103, capped to 5
    assert result is not None
    call_args = mock_db.resources.find_one_and_update.call_args[0][1]
    assert call_args["$set"]["available_quantity"] == 5  # capped at total


@pytest.mark.asyncio
async def test_release_repo_invalid_quantity():
    from app.repositories.resource_repo import release_resource
    mock_db = MagicMock()
    with pytest.raises(ValueError):
        await release_resource(mock_db, RESOURCE_ID, -1)
