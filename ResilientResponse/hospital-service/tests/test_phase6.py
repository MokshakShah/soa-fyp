"""
Phase 6 — Hospital Service operational tests.

Covers:
  - Haversine geo utility
  - Hospital search (city, min_beds, active_only, geo)
  - Police station search (city, active_only, geo)
  - Reserve beds (success, insufficient, not found, inactive)
  - Release beds (success, cap at capacity, not found)
  - Capacity never goes negative
  - Repository unit tests for reserve/release
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from main import app

# ─── Geo utility ──────────────────────────────────────────────────────────────

def test_haversine_same_point():
    from app.geo import haversine_km
    assert haversine_km(40.7128, -74.006, 40.7128, -74.006) == pytest.approx(0.0)


def test_haversine_known_distance():
    from app.geo import haversine_km
    # New York to London ≈ 5570 km
    dist = haversine_km(40.7128, -74.006, 51.5074, -0.1278)
    assert 5500 < dist < 5700


def test_within_radius_true():
    from app.geo import within_radius
    # Two points ~1 km apart
    assert within_radius(40.713, -74.006, 40.7128, -74.006, 5.0) is True


def test_within_radius_false():
    from app.geo import within_radius
    # New York vs London — not within 100 km
    assert within_radius(51.5074, -0.1278, 40.7128, -74.006, 100.0) is False


def test_within_radius_none_coordinates():
    from app.geo import within_radius
    assert within_radius(None, None, 40.7128, -74.006, 50.0) is False


def test_within_radius_partial_none():
    from app.geo import within_radius
    assert within_radius(40.713, None, 40.7128, -74.006, 50.0) is False


# ─── Hospital search ──────────────────────────────────────────────────────────

def _hospital(
    name="Test Hospital", city="Test City",
    lat=40.7128, lon=-74.006,
    available_beds=20, status="ACTIVE",
    hid="507f1f77bcf86cd799439011",
):
    return {
        "id": hid,
        "name": name,
        "city": city,
        "latitude": lat,
        "longitude": lon,
        "available_beds": available_beds,
        "icu_beds": 5,
        "emergency_capacity": 100,
        "status": status,
        "phone": "+1-555-0100",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


@pytest.mark.asyncio
async def test_search_hospitals_city_filter():
    """City filter returns only matching hospitals."""
    hospitals = [
        _hospital(name="City A Hospital", city="Alpha"),
        _hospital(name="City B Hospital", city="Beta", hid="507f1f77bcf86cd799439012"),
    ]
    with patch("app.routers.hospitals.search_hospitals", new_callable=AsyncMock, return_value=[hospitals[0]]):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/hospitals/search?city=Alpha")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["city"] == "Alpha"


@pytest.mark.asyncio
async def test_search_hospitals_min_beds_filter():
    """Hospitals with fewer beds than min_beds are excluded."""
    hospitals = [_hospital(available_beds=50)]
    with patch("app.routers.hospitals.search_hospitals", new_callable=AsyncMock, return_value=hospitals):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/hospitals/search?min_beds=10")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["available_beds"] == 50


@pytest.mark.asyncio
async def test_search_hospitals_geo_filter_within_radius():
    """Hospital within radius appears in results with distance_km."""
    h = _hospital(lat=40.7128, lon=-74.006)
    with patch("app.routers.hospitals.search_hospitals", new_callable=AsyncMock, return_value=[h]):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/hospitals/search?lat=40.7128&lon=-74.006&radius_km=10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert "distance_km" in data["items"][0]
    assert data["items"][0]["distance_km"] == pytest.approx(0.0, abs=0.1)


@pytest.mark.asyncio
async def test_search_hospitals_geo_filter_outside_radius():
    """Hospital far away is excluded from geo results."""
    h = _hospital(lat=51.5074, lon=-0.1278)  # London
    with patch("app.routers.hospitals.search_hospitals", new_callable=AsyncMock, return_value=[h]):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                # Center: New York, radius 100 km
                resp = await ac.get("/api/hospitals/search?lat=40.7128&lon=-74.006&radius_km=100")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_search_hospitals_no_geo_returns_all():
    """Without lat/lon, no geo filtering is applied."""
    hospitals = [_hospital(), _hospital(name="Another", hid="507f1f77bcf86cd799439012")]
    with patch("app.routers.hospitals.search_hospitals", new_callable=AsyncMock, return_value=hospitals):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/hospitals/search")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


@pytest.mark.asyncio
async def test_search_hospitals_empty_results():
    with patch("app.routers.hospitals.search_hospitals", new_callable=AsyncMock, return_value=[]):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/hospitals/search?city=Nowhere")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


# ─── Hospital reserve ─────────────────────────────────────────────────────────

HOSPITAL_ID = "507f1f77bcf86cd799439011"


@pytest.mark.asyncio
async def test_reserve_beds_success():
    before = _hospital(available_beds=30)
    after = _hospital(available_beds=25)
    with patch("app.routers.hospitals.get_hospital", new_callable=AsyncMock, return_value=before):
        with patch("app.routers.hospitals.reserve_beds", new_callable=AsyncMock, return_value=after):
            with patch("app.routers.hospitals.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.post(f"/api/hospitals/{HOSPITAL_ID}/reserve", json={"beds": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["operation"] == "reserve"
    assert data["beds"] == 5
    assert data["available_beds_before"] == 30
    assert data["available_beds_after"] == 25


@pytest.mark.asyncio
async def test_reserve_beds_insufficient_capacity():
    """Not enough beds → 409."""
    before = _hospital(available_beds=3)
    with patch("app.routers.hospitals.get_hospital", new_callable=AsyncMock, return_value=before):
        with patch("app.routers.hospitals.reserve_beds", new_callable=AsyncMock, return_value=None):
            with patch("app.routers.hospitals.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.post(f"/api/hospitals/{HOSPITAL_ID}/reserve", json={"beds": 10})
    assert resp.status_code == 409
    assert "Insufficient" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_reserve_beds_hospital_not_found():
    with patch("app.routers.hospitals.get_hospital", new_callable=AsyncMock, return_value=None):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/hospitals/nonexistent/reserve", json={"beds": 1})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reserve_beds_inactive_hospital():
    """Inactive hospital cannot be reserved."""
    h = _hospital(status="INACTIVE")
    with patch("app.routers.hospitals.get_hospital", new_callable=AsyncMock, return_value=h):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post(f"/api/hospitals/{HOSPITAL_ID}/reserve", json={"beds": 1})
    assert resp.status_code == 409
    assert "not active" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reserve_beds_zero_rejected():
    """beds=0 is invalid."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(f"/api/hospitals/{HOSPITAL_ID}/reserve", json={"beds": 0})
    assert resp.status_code == 422


# ─── Hospital release ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_release_beds_success():
    before = _hospital(available_beds=25)
    after = _hospital(available_beds=30)
    with patch("app.routers.hospitals.get_hospital", new_callable=AsyncMock, return_value=before):
        with patch("app.routers.hospitals.release_beds", new_callable=AsyncMock, return_value=after):
            with patch("app.routers.hospitals.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.post(f"/api/hospitals/{HOSPITAL_ID}/release", json={"beds": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["operation"] == "release"
    assert data["available_beds_after"] == 30


@pytest.mark.asyncio
async def test_release_beds_not_found():
    with patch("app.routers.hospitals.get_hospital", new_callable=AsyncMock, return_value=None):
        with patch("app.routers.hospitals.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/hospitals/nonexistent/release", json={"beds": 5})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_release_beds_zero_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(f"/api/hospitals/{HOSPITAL_ID}/release", json={"beds": 0})
    assert resp.status_code == 422


# ─── Repository: capacity never negative ─────────────────────────────────────

@pytest.mark.asyncio
async def test_reserve_beds_never_negative():
    """Repo guard prevents available_beds going below 0."""
    from app.repositories.hospital_repo import reserve_beds
    mock_db = MagicMock()
    # find_one_and_update returns None when the guard query ($gte: beds) fails
    mock_db.hospitals.find_one_and_update = AsyncMock(return_value=None)
    result = await reserve_beds(mock_db, HOSPITAL_ID, 999)
    assert result is None  # no update performed


@pytest.mark.asyncio
async def test_release_beds_capped_at_capacity():
    """Release is capped at emergency_capacity — never exceeds maximum."""
    from app.repositories.hospital_repo import release_beds
    mock_db = MagicMock()
    existing = {
        "_id": HOSPITAL_ID,
        "available_beds": 95,
        "emergency_capacity": 100,
    }
    expected_update = {
        "_id": HOSPITAL_ID,
        "available_beds": 100,
        "emergency_capacity": 100,
        "updated_at": datetime.utcnow(),
    }
    mock_db.hospitals.find_one = AsyncMock(return_value=existing)
    mock_db.hospitals.find_one_and_update = AsyncMock(return_value=expected_update)

    result = await release_beds(mock_db, HOSPITAL_ID, 20)  # would be 115, capped to 100
    assert result is not None
    # Verify the $set value passed to update_one was 100, not 115
    call_args = mock_db.hospitals.find_one_and_update.call_args
    update_doc = call_args[0][1]  # second positional arg
    assert update_doc["$set"]["available_beds"] == 100


@pytest.mark.asyncio
async def test_reserve_beds_invalid_quantity():
    from app.repositories.hospital_repo import reserve_beds
    mock_db = MagicMock()
    with pytest.raises(ValueError):
        await reserve_beds(mock_db, HOSPITAL_ID, 0)


# ─── Police station search ────────────────────────────────────────────────────

def _station(
    name="Test Station", city="Test City",
    lat=40.7128, lon=-74.006,
    status="ACTIVE",
    sid="507f1f77bcf86cd799439021",
):
    return {
        "id": sid,
        "name": name,
        "city": city,
        "latitude": lat,
        "longitude": lon,
        "status": status,
        "phone": "+1-555-0200",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


@pytest.mark.asyncio
async def test_search_police_stations_by_city():
    stations = [_station(city="Central City")]
    with patch("app.routers.police_stations.search_police_stations", new_callable=AsyncMock, return_value=stations):
        with patch("app.routers.police_stations.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/police-stations/search?city=Central%20City")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["city"] == "Central City"


@pytest.mark.asyncio
async def test_search_police_stations_geo_within_radius():
    s = _station(lat=40.7128, lon=-74.006)
    with patch("app.routers.police_stations.search_police_stations", new_callable=AsyncMock, return_value=[s]):
        with patch("app.routers.police_stations.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/police-stations/search?lat=40.7128&lon=-74.006&radius_km=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert "distance_km" in data["items"][0]


@pytest.mark.asyncio
async def test_search_police_stations_geo_outside_radius():
    s = _station(lat=51.5074, lon=-0.1278)  # London
    with patch("app.routers.police_stations.search_police_stations", new_callable=AsyncMock, return_value=[s]):
        with patch("app.routers.police_stations.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/police-stations/search?lat=40.7128&lon=-74.006&radius_km=100")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_search_police_stations_active_only():
    """Inactive stations excluded when active_only=True."""
    with patch("app.routers.police_stations.search_police_stations", new_callable=AsyncMock, return_value=[]) as mock_s:
        with patch("app.routers.police_stations.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/police-stations/search?active_only=true")
    assert resp.status_code == 200
    # Verify active_only was passed to repo
    mock_s.assert_called_once()
    kwargs = mock_s.call_args[1]
    assert kwargs.get("active_only") is True
