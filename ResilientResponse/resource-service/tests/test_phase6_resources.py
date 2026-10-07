"""
Phase 6 — Resource operational tests.

Covers:
  - Geo utility
  - search_resources repo
  - allocate_resource: success, insufficient, inactive/maintenance
  - release_resource: success, cap at total quantity
  - available_quantity never goes negative
  - API: GET /api/resources/search
  - API: POST /api/resources/{id}/allocate
  - API: POST /api/resources/{id}/release
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from main import app


# ─── helpers ──────────────────────────────────────────────────────────────────

def _resource(
    rid="507f1f77bcf86cd799439012",
    name="Ambulance Unit A1",
    rtype="AMBULANCE",
    quantity=5,
    available=5,
    city="Central City",
    lat=40.7128,
    lon=-74.0060,
    status="AVAILABLE",
):
    return {
        "id": rid,
        "name": name,
        "type": rtype,
        "quantity": quantity,
        "available_quantity": available,
        "unit": "vehicles",
        "location": "Central Station",
        "city": city,
        "state": "CC",
        "latitude": lat,
        "longitude": lon,
        "status": status,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


# ─── Geo utility ──────────────────────────────────────────────────────────────

def test_resource_geo_haversine():
    from app.geo import haversine_km
    d = haversine_km(40.0, -74.0, 40.0, -74.0)
    assert d == pytest.approx(0.0, abs=1e-6)


def test_resource_geo_within_radius_true():
    from app.geo import within_radius
    assert within_radius(40.71, -74.00, 40.71, -74.00, 5.0) is True


def test_resource_geo_within_radius_false():
    from app.geo import within_radius
    assert within_radius(50.0, -74.0, 40.0, -74.0, 50.0) is False


def test_resource_geo_none_coords():
    from app.geo import within_radius
    assert within_radius(None, -74.0, 40.0, -74.0, 100.0) is False


# ─── search_resources repo ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_resources_available_only_filter():
    from app.repositories.resource_repo import search_resources
    mock_db = MagicMock()

    async def fake_cursor():
        for r in []:
            yield r

    mock_cursor = MagicMock()
    mock_cursor.__aiter__ = lambda s: fake_cursor()
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.sort.return_value = mock_cursor
    mock_db.resources.find.return_value = mock_cursor

    await search_resources(mock_db, available_only=True, limit=10)
    query = mock_db.resources.find.call_args[0][0]
    assert "available_quantity" in query
    assert query["available_quantity"]["$gt"] == 0


@pytest.mark.asyncio
async def test_search_resources_type_filter():
    from app.repositories.resource_repo import search_resources
    mock_db = MagicMock()

    async def fake_cursor():
        for r in []:
            yield r

    mock_cursor = MagicMock()
    mock_cursor.__aiter__ = lambda s: fake_cursor()
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.sort.return_value = mock_cursor
    mock_db.resources.find.return_value = mock_cursor

    await search_resources(mock_db, resource_type="AMBULANCE", available_only=False, limit=10)
    query = mock_db.resources.find.call_args[0][0]
    assert "type" in query


# ─── allocate_resource repo ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_allocate_resource_success():
    from app.repositories.resource_repo import allocate_resource
    updated = {**_resource(available=3), "_id": "507f1f77bcf86cd799439012"}
    del updated["id"]

    mock_db = MagicMock()
    mock_db.resources.find_one_and_update = AsyncMock(return_value=updated)
    mock_db.resources.update_one = AsyncMock()

    result = await allocate_resource(mock_db, "507f1f77bcf86cd799439012", 2)
    assert result is not None
    assert result["available_quantity"] == 3


@pytest.mark.asyncio
async def test_allocate_resource_insufficient_returns_none():
    from app.repositories.resource_repo import allocate_resource
    mock_db = MagicMock()
    mock_db.resources.find_one_and_update = AsyncMock(return_value=None)

    result = await allocate_resource(mock_db, "507f1f77bcf86cd799439012", 999)
    assert result is None


@pytest.mark.asyncio
async def test_allocate_resource_invalid_quantity_raises():
    from app.repositories.resource_repo import allocate_resource
    mock_db = MagicMock()
    with pytest.raises(ValueError):
        await allocate_resource(mock_db, "507f1f77bcf86cd799439012", 0)


@pytest.mark.asyncio
async def test_allocate_resource_negative_quantity_raises():
    from app.repositories.resource_repo import allocate_resource
    mock_db = MagicMock()
    with pytest.raises(ValueError):
        await allocate_resource(mock_db, "507f1f77bcf86cd799439012", -5)


@pytest.mark.asyncio
async def test_allocate_resource_guard_prevents_negative():
    """The $gte guard in allocate_resource must prevent available_quantity going negative."""
    from app.repositories.resource_repo import allocate_resource
    mock_db = MagicMock()
    mock_db.resources.find_one_and_update = AsyncMock(return_value=None)

    result = await allocate_resource(mock_db, "507f1f77bcf86cd799439012", 100)
    assert result is None

    # Verify the guard was in the query
    query = mock_db.resources.find_one_and_update.call_args[0][0]
    assert "available_quantity" in query
    assert query["available_quantity"]["$gte"] == 100


# ─── release_resource repo ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_release_resource_success():
    from app.repositories.resource_repo import release_resource
    current = {**_resource(available=2, quantity=5)}
    current["_id"] = current.pop("id")
    updated = {**current, "available_quantity": 4}

    mock_db = MagicMock()
    mock_db.resources.find_one = AsyncMock(return_value=current)
    mock_db.resources.find_one_and_update = AsyncMock(return_value=updated)

    result = await release_resource(mock_db, "507f1f77bcf86cd799439012", 2)
    assert result is not None
    assert result["available_quantity"] == 4


@pytest.mark.asyncio
async def test_release_resource_capped_at_total():
    from app.repositories.resource_repo import release_resource
    current = {**_resource(available=4, quantity=5)}
    current["_id"] = current.pop("id")
    updated = {**current, "available_quantity": 5}

    mock_db = MagicMock()
    mock_db.resources.find_one = AsyncMock(return_value=current)
    mock_db.resources.find_one_and_update = AsyncMock(return_value=updated)

    await release_resource(mock_db, "507f1f77bcf86cd799439012", 10)
    set_val = mock_db.resources.find_one_and_update.call_args[0][1]["$set"]["available_quantity"]
    assert set_val == 5   # capped at total=5


@pytest.mark.asyncio
async def test_release_resource_not_found():
    from app.repositories.resource_repo import release_resource
    mock_db = MagicMock()
    mock_db.resources.find_one = AsyncMock(return_value=None)

    result = await release_resource(mock_db, "507f1f77bcf86cd799439012", 2)
    assert result is None


@pytest.mark.asyncio
async def test_release_resource_invalid_quantity_raises():
    from app.repositories.resource_repo import release_resource
    mock_db = MagicMock()
    with pytest.raises(ValueError):
        await release_resource(mock_db, "507f1f77bcf86cd799439012", 0)


# ─── API: resource search ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_resource_search_returns_results():
    resources = [_resource(), _resource(rid="507f1f77bcf86cd799439099", name="Kit B")]
    with patch("app.routers.resources.search_resources", new_callable=AsyncMock, return_value=resources):
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/resources/search")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


@pytest.mark.asyncio
async def test_api_resource_search_geo_filters():
    near = _resource(lat=40.71, lon=-74.00)
    far = _resource(rid="507f1f77bcf86cd799439099", lat=50.0, lon=-74.0)
    with patch("app.routers.resources.search_resources", new_callable=AsyncMock, return_value=[near, far]):
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/resources/search?lat=40.71&lon=-74.00&radius_km=50")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_api_resource_search_type_filter():
    with patch("app.routers.resources.search_resources", new_callable=AsyncMock, return_value=[]) as mock_fn:
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                await ac.get("/api/resources/search?type=AMBULANCE")
    mock_fn.assert_called_once()
    assert mock_fn.call_args.kwargs.get("resource_type") == "AMBULANCE"


# ─── API: allocate ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_allocate_success():
    r = _resource(available=5)
    updated = {**r, "available_quantity": 3}
    with patch("app.routers.resources.get_resource", new_callable=AsyncMock, return_value=r):
        with patch("app.routers.resources.allocate_resource", new_callable=AsyncMock, return_value=updated):
            with patch("app.routers.resources.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.post(f"/api/resources/{r['id']}/allocate", json={"quantity": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["operation"] == "allocate"
    assert data["available_before"] == 5
    assert data["available_after"] == 3


@pytest.mark.asyncio
async def test_api_allocate_insufficient_returns_409():
    r = _resource(available=2)
    with patch("app.routers.resources.get_resource", new_callable=AsyncMock, return_value=r):
        with patch("app.routers.resources.allocate_resource", new_callable=AsyncMock, return_value=None):
            with patch("app.routers.resources.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.post(f"/api/resources/{r['id']}/allocate", json={"quantity": 10})
    assert resp.status_code == 409
    assert "Insufficient" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_api_allocate_inactive_resource_returns_409():
    r = _resource(status="INACTIVE")
    with patch("app.routers.resources.get_resource", new_callable=AsyncMock, return_value=r):
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(f"/api/resources/{r['id']}/allocate", json={"quantity": 1})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_api_allocate_maintenance_resource_returns_409():
    r = _resource(status="MAINTENANCE")
    with patch("app.routers.resources.get_resource", new_callable=AsyncMock, return_value=r):
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(f"/api/resources/{r['id']}/allocate", json={"quantity": 1})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_api_allocate_not_found():
    with patch("app.routers.resources.get_resource", new_callable=AsyncMock, return_value=None):
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/resources/nonexistent/allocate", json={"quantity": 1})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_allocate_zero_quantity_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/resources/someid/allocate", json={"quantity": 0})
    assert resp.status_code == 422


# ─── API: release ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_release_success():
    r = _resource(available=2, quantity=5)
    updated = {**r, "available_quantity": 4}
    with patch("app.routers.resources.get_resource", new_callable=AsyncMock, return_value=r):
        with patch("app.routers.resources.release_resource", new_callable=AsyncMock, return_value=updated):
            with patch("app.routers.resources.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.post(f"/api/resources/{r['id']}/release", json={"quantity": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["operation"] == "release"
    assert data["available_after"] == 4


@pytest.mark.asyncio
async def test_api_release_not_found():
    with patch("app.routers.resources.get_resource", new_callable=AsyncMock, return_value=None):
        with patch("app.routers.resources.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/resources/nonexistent/release", json={"quantity": 1})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_release_zero_quantity_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/resources/someid/release", json={"quantity": 0})
    assert resp.status_code == 422
