"""
Phase 12 — API Gateway monitoring aggregation tests.

Covers GET /api/monitoring/summary which aggregates registry, workflow,
and notification summaries from three backend services in parallel.

Uses app.dependency_overrides to bypass JWT auth so tests are self-contained.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from main import app
from app.auth import get_current_admin


# ─── helpers ──────────────────────────────────────────────────────────────────

def _mock_admin():
    return {
        "id": "admin-1",
        "email": "admin@test.local",
        "name": "Admin",
        "role": "ADMIN",
    }


def _registry_summary():
    return {
        "total_instances": 4,
        "healthy_instances": 3,
        "status_counts": {"UP": 2, "DEGRADED": 1, "DOWN": 1},
        "services": [
            {
                "service_name": "hospital-service",
                "total_instances": 2,
                "healthy_instances": 2,
                "status_breakdown": {"UP": 2},
                "instances": [
                    {"instance_id": "hospital-primary", "role": "PRIMARY", "status": "UP", "response_time_ms": 40},
                    {"instance_id": "hospital-backup",  "role": "BACKUP",  "status": "UP", "response_time_ms": 45},
                ],
            }
        ],
    }


def _workflow_summary():
    return {
        "total": 10,
        "by_status": {"COMPLETED": 7, "PARTIAL": 1, "FAILED": 1, "RUNNING": 1},
        "running": 1,
        "completed": 7,
        "partial": 1,
        "failed": 1,
    }


def _notification_summary():
    return {
        "total": 20,
        "by_status": {"SENT": 17, "FAILED": 2, "PENDING": 1},
        "sent": 17,
        "failed": 2,
        "pending": 1,
    }


# ─── Auth bypass ──────────────────────────────────────────────────────────────

def _override_auth():
    """Override get_current_admin to bypass JWT validation in tests."""
    async def _fake_admin():
        return _mock_admin()
    return _fake_admin


# ─── Success cases ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_monitoring_summary_aggregates_all_three():
    """All three backend summaries are aggregated into a single response."""
    async def fake_fetch_json(client, url: str) -> dict:
        if "registry" in url:
            return _registry_summary()
        if "workflows" in url:
            return _workflow_summary()
        if "notifications" in url:
            return _notification_summary()
        return {}

    app.dependency_overrides[get_current_admin] = _override_auth()
    try:
        with patch("app.routers.proxy._fetch_json", side_effect=fake_fetch_json):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/monitoring/summary")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert "registry" in data
    assert "workflows" in data
    assert "notifications" in data


@pytest.mark.asyncio
async def test_monitoring_summary_registry_data_correct():
    """Registry section contains health totals and services breakdown."""
    async def fake_fetch_json(client, url: str) -> dict:
        if "registry" in url:
            return _registry_summary()
        return {}

    app.dependency_overrides[get_current_admin] = _override_auth()
    try:
        with patch("app.routers.proxy._fetch_json", side_effect=fake_fetch_json):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/monitoring/summary")
    finally:
        app.dependency_overrides.clear()

    data = resp.json()
    reg = data["registry"]
    assert reg["available"] is True
    assert reg["total_instances"] == 4
    assert reg["healthy_instances"] == 3


@pytest.mark.asyncio
async def test_monitoring_summary_workflow_data_correct():
    """Workflow section contains execution counts."""
    async def fake_fetch_json(client, url: str) -> dict:
        if "workflows" in url:
            return _workflow_summary()
        return {}

    app.dependency_overrides[get_current_admin] = _override_auth()
    try:
        with patch("app.routers.proxy._fetch_json", side_effect=fake_fetch_json):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/monitoring/summary")
    finally:
        app.dependency_overrides.clear()

    data = resp.json()
    wf = data["workflows"]
    assert wf["available"] is True
    assert wf["total"] == 10
    assert wf["running"] == 1
    assert wf["completed"] == 7
    assert wf["partial"] == 1
    assert wf["failed"] == 1


@pytest.mark.asyncio
async def test_monitoring_summary_notification_data_correct():
    """Notification section contains delivery counts."""
    async def fake_fetch_json(client, url: str) -> dict:
        if "notifications" in url:
            return _notification_summary()
        return {}

    app.dependency_overrides[get_current_admin] = _override_auth()
    try:
        with patch("app.routers.proxy._fetch_json", side_effect=fake_fetch_json):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/monitoring/summary")
    finally:
        app.dependency_overrides.clear()

    data = resp.json()
    notif = data["notifications"]
    assert notif["available"] is True
    assert notif["total"] == 20
    assert notif["sent"] == 17
    assert notif["failed"] == 2
    assert notif["pending"] == 1


# ─── Partial / degraded backends ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_monitoring_summary_registry_unavailable_returns_partial():
    """When registry backend is unreachable, its section has available=False; others still return data."""
    async def fake_fetch_json(client, url: str) -> dict:
        if "registry" in url:
            return {}    # simulates _fetch_json returning {} on error
        if "workflows" in url:
            return _workflow_summary()
        if "notifications" in url:
            return _notification_summary()
        return {}

    app.dependency_overrides[get_current_admin] = _override_auth()
    try:
        with patch("app.routers.proxy._fetch_json", side_effect=fake_fetch_json):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/monitoring/summary")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    # Registry returned empty dict → available=False
    assert data["registry"]["available"] is False
    # Others succeeded
    assert data["workflows"]["available"] is True
    assert data["notifications"]["available"] is True


@pytest.mark.asyncio
async def test_monitoring_summary_all_backends_unavailable():
    """All backends unreachable — all sections have available=False but response is 200."""
    async def fake_fetch_json(client, url: str) -> dict:
        return {}  # every backend returns empty

    app.dependency_overrides[get_current_admin] = _override_auth()
    try:
        with patch("app.routers.proxy._fetch_json", side_effect=fake_fetch_json):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/monitoring/summary")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["registry"]["available"] is False
    assert data["workflows"]["available"] is False
    assert data["notifications"]["available"] is False


@pytest.mark.asyncio
async def test_monitoring_summary_response_shape():
    """Response always has exactly three top-level keys: registry, workflows, notifications."""
    async def fake_fetch_json(client, url: str) -> dict:
        return {}

    app.dependency_overrides[get_current_admin] = _override_auth()
    try:
        with patch("app.routers.proxy._fetch_json", side_effect=fake_fetch_json):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/monitoring/summary")
    finally:
        app.dependency_overrides.clear()

    data = resp.json()
    assert set(data.keys()) == {"registry", "workflows", "notifications"}


# ─── Auth guard ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_monitoring_summary_requires_auth():
    """Unauthenticated requests return 401, 403, or 422 (missing credentials)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/monitoring/summary")
    assert resp.status_code in (401, 403, 422)
