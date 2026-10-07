"""
Phase 12 — Service Registry monitoring tests.

Covers the enhanced /api/registry/summary endpoint which now returns
per-service breakdown with PRIMARY/BACKUP role data and health details.
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from main import app


# ─── helpers ──────────────────────────────────────────────────────────────────

def _reg(
    service_name="hospital-service",
    instance_id="hospital-primary",
    base_url="http://hospital-primary:8004",
    status="UP",
    instance_role="PRIMARY",
    version="0.6.0",
):
    return {
        "id": "60d5f484f8d2e30d8c8b4567",
        "service_name": service_name,
        "instance_id": instance_id,
        "base_url": base_url,
        "status": status,
        "version": version,
        "instance_role": instance_role,
        "last_heartbeat": datetime.utcnow(),
        "registered_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "metadata": None,
    }


def _health(service_name="hospital-service", instance_id="hospital-primary", status="UP", rt=45):
    return {
        "id": "60d5f484f8d2e30d8c8b4568",
        "service_name": service_name,
        "instance_id": instance_id,
        "status": status,
        "response_time_ms": rt,
        "last_checked": datetime.utcnow(),
        "error": None,
        "details": None,
    }


# ─── Enhanced summary: structure ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_summary_includes_services_list():
    """Phase 12 summary returns a 'services' list of per-service breakdowns."""
    records = [
        _reg(service_name="hospital-service", instance_id="hospital-primary",  status="UP",   instance_role="PRIMARY"),
        _reg(service_name="hospital-service", instance_id="hospital-backup",   status="DOWN", instance_role="BACKUP"),
    ]
    healths = [
        _health("hospital-service", "hospital-primary", status="UP",   rt=45),
        _health("hospital-service", "hospital-backup",  status="DOWN", rt=None),
    ]
    with patch("app.routers.registry.list_registry",  new_callable=AsyncMock, return_value=records):
        with patch("app.routers.registry.list_health", new_callable=AsyncMock, return_value=healths):
            with patch("app.routers.registry.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/registry/summary")

    assert resp.status_code == 200
    data = resp.json()
    assert "services" in data
    assert isinstance(data["services"], list)
    assert len(data["services"]) == 1  # one logical service

    svc = data["services"][0]
    assert svc["service_name"] == "hospital-service"
    assert svc["total_instances"] == 2
    assert svc["healthy_instances"] == 1
    assert "status_breakdown" in svc
    assert svc["status_breakdown"].get("UP") == 1
    assert svc["status_breakdown"].get("DOWN") == 1


@pytest.mark.asyncio
async def test_summary_instances_have_role_and_health():
    """Each instance in the services breakdown has role, status, last_health_check."""
    records = [
        _reg(service_name="hospital-service", instance_id="hospital-primary", status="UP", instance_role="PRIMARY"),
    ]
    healths = [
        _health("hospital-service", "hospital-primary", status="UP", rt=30),
    ]
    with patch("app.routers.registry.list_registry",  new_callable=AsyncMock, return_value=records):
        with patch("app.routers.registry.list_health", new_callable=AsyncMock, return_value=healths):
            with patch("app.routers.registry.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/registry/summary")

    data = resp.json()
    svc = data["services"][0]
    inst = svc["instances"][0]
    assert inst["instance_id"] == "hospital-primary"
    assert inst["role"] == "PRIMARY"
    assert inst["status"] == "UP"
    assert inst["response_time_ms"] == 30
    assert "last_health_check" in inst
    assert "base_url" in inst


@pytest.mark.asyncio
async def test_summary_primary_sorted_before_backup():
    """Within each service, PRIMARY instance appears before BACKUP."""
    records = [
        # BACKUP registered first in DB order
        _reg(service_name="hospital-service", instance_id="hospital-backup",  status="UP", instance_role="BACKUP"),
        _reg(service_name="hospital-service", instance_id="hospital-primary", status="UP", instance_role="PRIMARY"),
    ]
    healths = [
        _health("hospital-service", "hospital-backup"),
        _health("hospital-service", "hospital-primary"),
    ]
    with patch("app.routers.registry.list_registry",  new_callable=AsyncMock, return_value=records):
        with patch("app.routers.registry.list_health", new_callable=AsyncMock, return_value=healths):
            with patch("app.routers.registry.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/registry/summary")

    data = resp.json()
    svc = data["services"][0]
    assert svc["instances"][0]["role"] == "PRIMARY"
    assert svc["instances"][1]["role"] == "BACKUP"


@pytest.mark.asyncio
async def test_summary_multiple_services_grouped_correctly():
    """Instances from different services are placed in separate groups."""
    records = [
        _reg(service_name="hospital-service",  instance_id="hospital-primary",  status="UP",   instance_role="PRIMARY"),
        _reg(service_name="resource-service",  instance_id="resource-primary",  status="UP",   instance_role="PRIMARY"),
        _reg(service_name="resource-service",  instance_id="resource-backup",   status="DOWN", instance_role="BACKUP"),
    ]
    healths = [
        _health("hospital-service", "hospital-primary",  status="UP"),
        _health("resource-service", "resource-primary",  status="UP"),
        _health("resource-service", "resource-backup",   status="DOWN", rt=None),
    ]
    with patch("app.routers.registry.list_registry",  new_callable=AsyncMock, return_value=records):
        with patch("app.routers.registry.list_health", new_callable=AsyncMock, return_value=healths):
            with patch("app.routers.registry.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/registry/summary")

    data = resp.json()
    assert data["total_instances"] == 3
    assert data["healthy_instances"] == 2

    svc_map = {s["service_name"]: s for s in data["services"]}
    assert "hospital-service" in svc_map
    assert "resource-service" in svc_map

    assert svc_map["hospital-service"]["total_instances"] == 1
    assert svc_map["resource-service"]["total_instances"] == 2
    assert svc_map["resource-service"]["healthy_instances"] == 1


@pytest.mark.asyncio
async def test_summary_empty_registry_returns_empty_services():
    """When no services are registered, services list is empty."""
    with patch("app.routers.registry.list_registry",  new_callable=AsyncMock, return_value=[]):
        with patch("app.routers.registry.list_health", new_callable=AsyncMock, return_value=[]):
            with patch("app.routers.registry.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/registry/summary")

    data = resp.json()
    assert data["total_instances"] == 0
    assert data["healthy_instances"] == 0
    assert data["services"] == []


@pytest.mark.asyncio
async def test_summary_all_statuses_counted():
    """All health statuses (UP, DOWN, DEGRADED, RECOVERING, UNKNOWN) counted."""
    statuses = ["UP", "DOWN", "DEGRADED", "RECOVERING", "UNKNOWN"]
    records = [
        _reg(service_name="orchestrator", instance_id=f"inst-{s}", status=s, instance_role="PRIMARY")
        for s in statuses
    ]
    healths = [
        _health("orchestrator", f"inst-{s}", status=s)
        for s in statuses
    ]
    with patch("app.routers.registry.list_registry",  new_callable=AsyncMock, return_value=records):
        with patch("app.routers.registry.list_health", new_callable=AsyncMock, return_value=healths):
            with patch("app.routers.registry.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/registry/summary")

    data = resp.json()
    assert data["total_instances"] == 5
    # UP, DEGRADED, RECOVERING are healthy
    assert data["healthy_instances"] == 3
    counts = data["status_counts"]
    for s in statuses:
        assert counts.get(s) == 1


@pytest.mark.asyncio
async def test_summary_instance_error_included():
    """When an instance has a health error, it is included in the breakdown."""
    records = [
        _reg(service_name="route-service", instance_id="route-primary", status="DOWN", instance_role="PRIMARY"),
    ]
    healths = [
        {
            "id": "abc",
            "service_name": "route-service",
            "instance_id": "route-primary",
            "status": "DOWN",
            "response_time_ms": None,
            "last_checked": datetime.utcnow(),
            "error": "Connection refused",
            "details": None,
        }
    ]
    with patch("app.routers.registry.list_registry",  new_callable=AsyncMock, return_value=records):
        with patch("app.routers.registry.list_health", new_callable=AsyncMock, return_value=healths):
            with patch("app.routers.registry.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/registry/summary")

    data = resp.json()
    inst = data["services"][0]["instances"][0]
    assert inst["error"] == "Connection refused"
    assert inst["response_time_ms"] is None
