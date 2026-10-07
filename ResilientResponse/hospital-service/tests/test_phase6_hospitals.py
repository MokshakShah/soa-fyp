"""
Phase 6 — Hospital operational tests.

Covers:
  - Geo utility (haversine, within_radius)
  - search_hospitals repo function
  - search_police_stations repo function
  - reserve_beds: success, insufficient capacity, inactive hospital
  - release_beds: success, cap at emergency_capacity
  - capacity never goes negative
  - API: GET /api/hospitals/search
  - API: POST /api/hospitals/{id}/reserve
  - API: POST /api/hospitals/{id}/release
  - API: GET /api/police-stations/search
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from main import app


# ─── helpers ──────────────────────────────────────────────────────────────────

def _hospital(
    hid="507f1f77bcf86cd799439011",
    name="Test Hospital",
    city="Central City",
    lat=40.7128,
    lon=-74.0060,
    available_beds=50,
    emergency_capacity=100,
    icu_beds=10,
    status="ACTIVE",
):
    return {
        "id": hid,
        "name": name,
        "registration_number": "HOS-001",
        "phone": "+1-555-0100",
        "emergency_phone": "+1-555-0911",
        "email": None,
        "address": "1 Medical Drive",
        "city": city,
        "state": "CC",
        "latitude": lat,
        "longitude": lon,
        "emergency_capacity": emergency_capacity,
        "available_beds": available_beds,
        "icu_beds": icu_beds,
        "status": status,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


def _police(
    pid="507f1f77bcf86cd799439022",
    name="Central Station",
    city="Central City",
    lat=40.7130,
    lon=-74.0055,
    status="ACTIVE",
):
    return {
        "id": pid,
        "name": name,
        "station_code": "CPSD-01",
        "phone": "+1-555-0400",
        "emergency_phone": "+1-555-0100",
        "email": None,
        "address": "1 Police Plaza",
        "city": city,
        "state": "CC",
        "latitude": lat,
        "longitude": lon,
        "status": status,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


# ─── Geo utility ──────────────────────────────────────────────────────────────

def test_haversine_same_point_is_zero():
    from app.geo import haversine_km
    assert haversine_km(40.0, -74.0, 40.0, -74.0) == pytest.approx(0.0, abs=1e-6)


def test_haversine_known_distance():
    from app.geo import haversine_km
    # NYC (40.7128, -74.0060) to roughly 1 degree north
    dist = haversine_km(40.7128, -74.0060, 41.7128, -74.0060)
    assert 110.0 < dist < 115.0  # ~111 km per degree latitude


def test_within_radius_true():
    from app.geo import within_radius
    assert within_radius(40.71, -74.00, 40.71, -74.00, 10.0) is True


def test_within_radius_false():
    from app.geo import within_radius
    # ~111 km away
    assert within_radius(41.71, -74.00, 40.71, -74.00, 50.0) is False


def test_within_radius_none_coords():
    from app.geo import within_radius
    assert within_radius(None, None, 40.71, -74.00, 100.0) is False


def test_within_radius_partial_none():
    from app.geo import within_radius
    assert within_radius(40.71, None, 40.71, -74.00, 100.0) is False


# ─── search_hospitals repo ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_hospitals_active_only():
    from app.repositories.hospital_repo import search_hospitals
    mock_db = MagicMock()

    async def fake_cursor():
        # Documents must have _id (as repo calls _serialize which pops _id)
        yield {**_hospital(), "_id": "507f1f77bcf86cd799439011"}

    mock_cursor = MagicMock()
    mock_cursor.__aiter__ = lambda s: fake_cursor()
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.sort.return_value = mock_cursor
    mock_db.hospitals.find.return_value = mock_cursor

    results = await search_hospitals(mock_db, active_only=True, limit=10)
    call_args = mock_db.hospitals.find.call_args[0][0]
    assert call_args.get("status") == "ACTIVE"


@pytest.mark.asyncio
async def test_search_hospitals_min_beds_filter():
    from app.repositories.hospital_repo import search_hospitals
    mock_db = MagicMock()

    async def fake_cursor():
        for h in []:
            yield h

    mock_cursor = MagicMock()
    mock_cursor.__aiter__ = lambda s: fake_cursor()
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.sort.return_value = mock_cursor
    mock_db.hospitals.find.return_value = mock_cursor

    await search_hospitals(mock_db, min_available_beds=10, active_only=True, limit=10)
    query = mock_db.hospitals.find.call_args[0][0]
    assert "available_beds" in query
    assert query["available_beds"]["$gte"] == 10


# ─── reserve_beds repo ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reserve_beds_success():
    from app.repositories.hospital_repo import reserve_beds
    updated_doc = {**_hospital(), "available_beds": 45}
    del updated_doc["id"]
    updated_doc["_id"] = "507f1f77bcf86cd799439011"

    mock_db = MagicMock()
    mock_db.hospitals.find_one_and_update = AsyncMock(return_value=updated_doc)

    result = await reserve_beds(mock_db, "507f1f77bcf86cd799439011", 5)
    assert result is not None
    assert result["available_beds"] == 45


@pytest.mark.asyncio
async def test_reserve_beds_insufficient_returns_none():
    from app.repositories.hospital_repo import reserve_beds
    mock_db = MagicMock()
    # Simulate MongoDB returning None because filter $gte not matched
    mock_db.hospitals.find_one_and_update = AsyncMock(return_value=None)

    result = await reserve_beds(mock_db, "507f1f77bcf86cd799439011", 999)
    assert result is None


@pytest.mark.asyncio
async def test_reserve_beds_invalid_quantity_raises():
    from app.repositories.hospital_repo import reserve_beds
    mock_db = MagicMock()
    with pytest.raises(ValueError):
        await reserve_beds(mock_db, "507f1f77bcf86cd799439011", 0)


# ─── release_beds repo ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_release_beds_success():
    from app.repositories.hospital_repo import release_beds
    current_doc = {**_hospital(available_beds=40, emergency_capacity=100)}
    current_doc["_id"] = current_doc.pop("id")
    updated_doc = {**current_doc, "available_beds": 50}

    mock_db = MagicMock()
    mock_db.hospitals.find_one = AsyncMock(return_value=current_doc)
    mock_db.hospitals.find_one_and_update = AsyncMock(return_value=updated_doc)

    result = await release_beds(mock_db, "507f1f77bcf86cd799439011", 10)
    assert result is not None
    assert result["available_beds"] == 50


@pytest.mark.asyncio
async def test_release_beds_capped_at_capacity():
    from app.repositories.hospital_repo import release_beds
    current_doc = {**_hospital(available_beds=95, emergency_capacity=100)}
    current_doc["_id"] = current_doc.pop("id")
    # Release 20, but capacity is 100 → should cap at 100
    updated_doc = {**current_doc, "available_beds": 100}

    mock_db = MagicMock()
    mock_db.hospitals.find_one = AsyncMock(return_value=current_doc)
    mock_db.hospitals.find_one_and_update = AsyncMock(return_value=updated_doc)

    result = await release_beds(mock_db, "507f1f77bcf86cd799439011", 20)
    assert result is not None
    # Confirm $set was called with capped value
    set_args = mock_db.hospitals.find_one_and_update.call_args[0][1]["$set"]
    assert set_args["available_beds"] == 100  # capped


@pytest.mark.asyncio
async def test_release_beds_not_found():
    from app.repositories.hospital_repo import release_beds
    mock_db = MagicMock()
    mock_db.hospitals.find_one = AsyncMock(return_value=None)

    result = await release_beds(mock_db, "507f1f77bcf86cd799439011", 5)
    assert result is None


@pytest.mark.asyncio
async def test_release_beds_invalid_quantity_raises():
    from app.repositories.hospital_repo import release_beds
    mock_db = MagicMock()
    with pytest.raises(ValueError):
        await release_beds(mock_db, "507f1f77bcf86cd799439011", -1)


# ─── Capacity never negative ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_capacity_guard_prevents_negative():
    """The $gte filter in reserve_beds must prevent available_beds going negative."""
    from app.repositories.hospital_repo import reserve_beds
    mock_db = MagicMock()
    mock_db.hospitals.find_one_and_update = AsyncMock(return_value=None)

    # Hospital has 5 beds, request 100 → must return None (guard triggered)
    result = await reserve_beds(mock_db, "507f1f77bcf86cd799439011", 100)
    assert result is None

    # Confirm the $gte guard was in the query
    query_filter = mock_db.hospitals.find_one_and_update.call_args[0][0]
    assert "available_beds" in query_filter
    assert query_filter["available_beds"]["$gte"] == 100


# ─── API: hospital search ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_hospital_search_returns_results():
    hospitals = [_hospital(), _hospital(hid="507f1f77bcf86cd799439099", name="Other Hospital", lat=40.72, lon=-74.01)]
    with patch("app.routers.hospitals.search_hospitals", new_callable=AsyncMock, return_value=hospitals):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/hospitals/search?lat=40.71&lon=-74.00&radius_km=20")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_api_hospital_search_no_geo_returns_all():
    hospitals = [_hospital()]
    with patch("app.routers.hospitals.search_hospitals", new_callable=AsyncMock, return_value=hospitals):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/hospitals/search")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


@pytest.mark.asyncio
async def test_api_hospital_search_excludes_out_of_radius():
    # Hospital far away should be excluded by geo filter
    far_hospital = _hospital(lat=50.0, lon=-74.0)  # ~1030 km north
    with patch("app.routers.hospitals.search_hospitals", new_callable=AsyncMock, return_value=[far_hospital]):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/hospitals/search?lat=40.71&lon=-74.00&radius_km=50")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ─── API: hospital reserve ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_reserve_beds_success():
    h = _hospital(available_beds=50)
    updated = {**h, "available_beds": 45}
    with patch("app.routers.hospitals.get_hospital", new_callable=AsyncMock, return_value=h):
        with patch("app.routers.hospitals.reserve_beds", new_callable=AsyncMock, return_value=updated):
            with patch("app.routers.hospitals.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.post(f"/api/hospitals/{h['id']}/reserve", json={"beds": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["operation"] == "reserve"
    assert data["available_beds_before"] == 50
    assert data["available_beds_after"] == 45


@pytest.mark.asyncio
async def test_api_reserve_beds_insufficient_returns_409():
    h = _hospital(available_beds=3)
    with patch("app.routers.hospitals.get_hospital", new_callable=AsyncMock, return_value=h):
        with patch("app.routers.hospitals.reserve_beds", new_callable=AsyncMock, return_value=None):
            with patch("app.routers.hospitals.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.post(f"/api/hospitals/{h['id']}/reserve", json={"beds": 10})
    assert resp.status_code == 409
    assert "Insufficient" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_api_reserve_beds_inactive_hospital_returns_409():
    h = _hospital(status="INACTIVE")
    with patch("app.routers.hospitals.get_hospital", new_callable=AsyncMock, return_value=h):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(f"/api/hospitals/{h['id']}/reserve", json={"beds": 5})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_api_reserve_beds_not_found():
    with patch("app.routers.hospitals.get_hospital", new_callable=AsyncMock, return_value=None):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/hospitals/nonexistent/reserve", json={"beds": 5})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_reserve_beds_zero_quantity_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/hospitals/someid/reserve", json={"beds": 0})
    assert resp.status_code == 422


# ─── API: hospital release ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_release_beds_success():
    h = _hospital(available_beds=40)
    updated = {**h, "available_beds": 50}
    with patch("app.routers.hospitals.get_hospital", new_callable=AsyncMock, return_value=h):
        with patch("app.routers.hospitals.release_beds", new_callable=AsyncMock, return_value=updated):
            with patch("app.routers.hospitals.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.post(f"/api/hospitals/{h['id']}/release", json={"beds": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["operation"] == "release"
    assert data["available_beds_after"] == 50


@pytest.mark.asyncio
async def test_api_release_beds_not_found():
    with patch("app.routers.hospitals.get_hospital", new_callable=AsyncMock, return_value=None):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/hospitals/nonexistent/release", json={"beds": 5})
    assert resp.status_code == 404


# ─── API: police station search ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_police_search_returns_active():
    stations = [_police()]
    with patch("app.routers.police_stations.search_police_stations", new_callable=AsyncMock, return_value=stations):
        with patch("app.routers.police_stations.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/police-stations/search")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Central Station"


@pytest.mark.asyncio
async def test_api_police_search_with_geo_filter():
    near = _police(lat=40.71, lon=-74.00)
    far = _police(pid="507f1f77bcf86cd799439033", lat=50.0, lon=-74.0)
    with patch("app.routers.police_stations.search_police_stations", new_callable=AsyncMock, return_value=[near, far]):
        with patch("app.routers.police_stations.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/police-stations/search?lat=40.71&lon=-74.00&radius_km=50")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_api_police_search_empty():
    with patch("app.routers.police_stations.search_police_stations", new_callable=AsyncMock, return_value=[]):
        with patch("app.routers.police_stations.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/police-stations/search?city=NoSuchCity")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_api_police_alias_search():
    """GET /api/police/search mirrors /api/police-stations/search."""
    stations = [_police()]
    with patch("app.routers.police_stations.search_police_stations", new_callable=AsyncMock, return_value=stations):
        with patch("app.routers.police_stations.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/police/search")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
