"""
Phase 3 — Service Registry tests.

Covers:
  - Registration (new, idempotent, update)
  - Discovery (healthy preferred, DOWN excluded, PRIMARY preferred, BACKUP fallback)
  - Health state transitions
  - Registry isolation (DOWN service does not crash registry)

Run: pytest tests/ -v
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from main import app

# ─── helpers ──────────────────────────────────────────────────────────────────

def _make_db():
    """Return a MagicMock that mimics Motor collection operations."""
    db = MagicMock()
    return db


def _reg(
    service_name="hospital-service",
    instance_id="hospital-primary",
    base_url="http://hospital-primary:8004",
    status="UP",
    instance_role="PRIMARY",
    version="0.3.0",
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


# ─── /health ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_endpoint():
    mock_db = MagicMock()
    mock_db.command = AsyncMock(return_value={"ok": 1})
    with patch("main.get_db", return_value=mock_db):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "service-registry"


# ─── Registration ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_new_service():
    """Registering a new service returns success."""
    mock_record = _reg()
    with patch("app.routers.registry.upsert_registration", new_callable=AsyncMock, return_value=mock_record):
        with patch("app.routers.registry.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/registry/register", json={
                    "service_name": "hospital-service",
                    "instance_id": "hospital-primary",
                    "base_url": "http://hospital-primary:8004",
                    "version": "0.3.0",
                    "instance_role": "PRIMARY",
                })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["instance_id"] == "hospital-primary"
    assert data["service_name"] == "hospital-service"


@pytest.mark.asyncio
async def test_register_same_instance_twice_is_idempotent():
    """Calling register twice with the same instance_id does not error."""
    mock_record = _reg()
    with patch("app.routers.registry.upsert_registration", new_callable=AsyncMock, return_value=mock_record) as mock_upsert:
        with patch("app.routers.registry.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                payload = {
                    "service_name": "hospital-service",
                    "instance_id": "hospital-primary",
                    "base_url": "http://hospital-primary:8004",
                    "version": "0.3.0",
                    "instance_role": "PRIMARY",
                }
                r1 = await ac.post("/api/registry/register", json=payload)
                r2 = await ac.post("/api/registry/register", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    # upsert_registration called twice (repo handles idempotency internally)
    assert mock_upsert.call_count == 2


@pytest.mark.asyncio
async def test_register_backup_instance():
    """Registering a BACKUP instance succeeds with correct role."""
    mock_record = _reg(instance_id="hospital-backup", instance_role="BACKUP")
    with patch("app.routers.registry.upsert_registration", new_callable=AsyncMock, return_value=mock_record):
        with patch("app.routers.registry.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/registry/register", json={
                    "service_name": "hospital-service",
                    "instance_id": "hospital-backup",
                    "base_url": "http://hospital-backup:8004",
                    "version": "0.3.0",
                    "instance_role": "BACKUP",
                })
    assert resp.status_code == 200
    assert resp.json()["instance_id"] == "hospital-backup"


@pytest.mark.asyncio
async def test_register_invalid_role_rejected():
    """Invalid instance_role should return 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/registry/register", json={
            "service_name": "hospital-service",
            "instance_id": "hospital-primary",
            "base_url": "http://hospital-primary:8004",
            "version": "0.3.0",
            "instance_role": "INVALID_ROLE",
        })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_missing_fields_rejected():
    """Missing required fields return 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/registry/register", json={"service_name": "hospital-service"})
    assert resp.status_code == 422


# ─── Listing ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_services():
    """GET /api/registry/services returns all instances."""
    records = [_reg(), _reg(instance_id="hospital-backup", instance_role="BACKUP")]
    healths = [_health(), _health(instance_id="hospital-backup")]
    with patch("app.routers.registry.list_registry", new_callable=AsyncMock, return_value=records):
        with patch("app.routers.registry.list_health", new_callable=AsyncMock, return_value=healths):
            with patch("app.routers.registry.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/registry/services")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_list_services_by_name():
    """GET /api/registry/services/{service_name} filters correctly."""
    records = [_reg()]
    healths = [_health()]
    with patch("app.routers.registry.list_registry_by_service", new_callable=AsyncMock, return_value=records):
        with patch("app.routers.registry.list_health", new_callable=AsyncMock, return_value=healths):
            with patch("app.routers.registry.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/registry/services/hospital-service")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service_name"] == "hospital-service"
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_unknown_service_returns_404():
    with patch("app.routers.registry.list_registry_by_service", new_callable=AsyncMock, return_value=[]):
        with patch("app.routers.registry.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/registry/services/does-not-exist")
    assert resp.status_code == 404


# ─── Discovery ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_discover_healthy_primary():
    """Discovery returns UP PRIMARY as selected."""
    records = [
        _reg(instance_id="hospital-primary", status="UP", instance_role="PRIMARY"),
        _reg(instance_id="hospital-backup", status="UP", instance_role="BACKUP"),
    ]
    healths = [_health("hospital-service", "hospital-primary"), _health("hospital-service", "hospital-backup")]
    with patch("app.routers.registry.list_registry_by_service", new_callable=AsyncMock, return_value=records):
        with patch("app.routers.registry.list_health", new_callable=AsyncMock, return_value=healths):
            with patch("app.routers.registry.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/registry/discover/hospital-service")
    assert resp.status_code == 200
    data = resp.json()
    assert data["selected"]["instance_id"] == "hospital-primary"
    assert data["selected"]["instance_role"] == "PRIMARY"
    assert len(data["instances"]) == 2


@pytest.mark.asyncio
async def test_discover_returns_backup_when_primary_down():
    """When PRIMARY is DOWN, discovery returns the healthy BACKUP."""
    records = [
        _reg(instance_id="hospital-primary", status="DOWN", instance_role="PRIMARY"),
        _reg(instance_id="hospital-backup", status="UP", instance_role="BACKUP"),
    ]
    healths = [
        _health("hospital-service", "hospital-primary", status="DOWN", rt=None),
        _health("hospital-service", "hospital-backup", status="UP", rt=30),
    ]
    with patch("app.routers.registry.list_registry_by_service", new_callable=AsyncMock, return_value=records):
        with patch("app.routers.registry.list_health", new_callable=AsyncMock, return_value=healths):
            with patch("app.routers.registry.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/registry/discover/hospital-service")
    assert resp.status_code == 200
    data = resp.json()
    # DOWN primary must NOT appear in instances
    instance_ids = [i["instance_id"] for i in data["instances"]]
    assert "hospital-primary" not in instance_ids
    assert "hospital-backup" in instance_ids
    assert data["selected"]["instance_id"] == "hospital-backup"


@pytest.mark.asyncio
async def test_discover_no_healthy_instances_returns_503():
    """When all instances are DOWN, discovery returns 503."""
    records = [
        _reg(instance_id="hospital-primary", status="DOWN", instance_role="PRIMARY"),
        _reg(instance_id="hospital-backup", status="DOWN", instance_role="BACKUP"),
    ]
    healths = [
        _health("hospital-service", "hospital-primary", status="DOWN", rt=None),
        _health("hospital-service", "hospital-backup", status="DOWN", rt=None),
    ]
    with patch("app.routers.registry.list_registry_by_service", new_callable=AsyncMock, return_value=records):
        with patch("app.routers.registry.list_health", new_callable=AsyncMock, return_value=healths):
            with patch("app.routers.registry.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/registry/discover/hospital-service")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_discover_unregistered_service_returns_404():
    """Discovering a service that was never registered returns 404."""
    with patch("app.routers.registry.list_registry_by_service", new_callable=AsyncMock, return_value=[]):
        with patch("app.routers.registry.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/registry/discover/nonexistent-service")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_discover_multiple_healthy_instances():
    """Multiple healthy instances are all returned; PRIMARY is selected."""
    records = [
        _reg(instance_id="hospital-primary", status="UP", instance_role="PRIMARY"),
        _reg(instance_id="hospital-backup", status="RECOVERING", instance_role="BACKUP"),
    ]
    healths = [
        _health("hospital-service", "hospital-primary", status="UP"),
        _health("hospital-service", "hospital-backup", status="RECOVERING"),
    ]
    with patch("app.routers.registry.list_registry_by_service", new_callable=AsyncMock, return_value=records):
        with patch("app.routers.registry.list_health", new_callable=AsyncMock, return_value=healths):
            with patch("app.routers.registry.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/registry/discover/hospital-service")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["instances"]) == 2
    assert data["selected"]["instance_role"] == "PRIMARY"


@pytest.mark.asyncio
async def test_registry_summary_returns_health_breakdown():
    """Summary endpoint provides counts for service health monitoring."""
    records = [
        _reg(instance_id="hospital-primary", status="UP", instance_role="PRIMARY"),
        _reg(instance_id="hospital-backup", status="DOWN", instance_role="BACKUP"),
        _reg(service_name="resource-service", instance_id="resource-primary", status="RECOVERING", instance_role="PRIMARY"),
    ]
    healths = [
        _health("hospital-service", "hospital-primary", status="UP"),
        _health("hospital-service", "hospital-backup", status="DOWN"),
        _health("resource-service", "resource-primary", status="RECOVERING"),
    ]
    with patch("app.routers.registry.list_registry", new_callable=AsyncMock, return_value=records):
        with patch("app.routers.registry.list_health", new_callable=AsyncMock, return_value=healths):
            with patch("app.routers.registry.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/registry/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_instances"] == 3
    assert data["status_counts"]["UP"] == 1
    assert data["status_counts"]["DOWN"] == 1
    assert data["status_counts"]["RECOVERING"] == 1
    assert data["healthy_instances"] == 2


# ─── Health monitor unit tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_monitor_marks_service_up_on_success():
    """Healthy response → UP status stored."""
    import httpx as _httpx
    from app.monitor import _check_instance, _counters

    _counters.clear()
    instance = _reg(status="UNKNOWN")

    async def _fake_get(url, **kwargs):
        return _httpx.Response(200, json={"status": "ok"})

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=_fake_get)

    status, rt, error, _ = await _check_instance(mock_client, instance)

    assert status == "UP"
    assert error is None


@pytest.mark.asyncio
async def test_monitor_marks_service_down_after_failures():
    """Two consecutive failures (FAILURE_THRESHOLD=2) → DOWN."""
    import httpx as _httpx
    from app.monitor import _check_instance, _counters
    from app.config import FAILURE_THRESHOLD

    _counters.clear()
    instance = _reg(status="UP")

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=_httpx.ConnectError("refused"))

    for _ in range(FAILURE_THRESHOLD):
        status, rt, error, _ = await _check_instance(mock_client, instance)
        instance["status"] = status

    assert status == "DOWN"


@pytest.mark.asyncio
async def test_monitor_transitions_to_recovering_after_down():
    """First success after DOWN → RECOVERING."""
    import httpx as _httpx
    from app.monitor import _check_instance, _counters, _set_counters

    _counters.clear()
    instance = _reg(status="DOWN")
    key = (instance["service_name"], instance["instance_id"])
    _set_counters(key, failures=2, successes=0)

    async def _fake_get(url, **kwargs):
        return _httpx.Response(200, json={"status": "ok"})

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=_fake_get)

    status, rt, error, _ = await _check_instance(mock_client, instance)

    assert status == "RECOVERING"


@pytest.mark.asyncio
async def test_monitor_transitions_recovering_to_up():
    """RECOVERY_THRESHOLD consecutive successes after DOWN → UP."""
    import httpx as _httpx
    from app.monitor import _check_instance, _counters, _set_counters
    from app.config import RECOVERY_THRESHOLD

    _counters.clear()
    instance = _reg(status="DOWN")
    key = (instance["service_name"], instance["instance_id"])
    _set_counters(key, failures=2, successes=0)

    async def _fake_get(url, **kwargs):
        return _httpx.Response(200, json={"status": "ok"})

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=_fake_get)

    for _ in range(RECOVERY_THRESHOLD):
        status, rt, error, _ = await _check_instance(mock_client, instance)
        instance["status"] = status

    assert status == "UP"


# ─── Isolation test ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_registry_does_not_crash_when_monitored_service_down():
    """
    A DOWN monitored service must not crash the registry.
    The /health endpoint must still return 200.
    """
    import httpx as _httpx
    from app.monitor import run_health_check_cycle

    mock_db = MagicMock()
    mock_db.command = AsyncMock(return_value={"ok": 1})

    # Registry record for a service that will fail
    down_instance = _reg(status="UP")

    # Patch the HTTP client used inside run_health_check_cycle to simulate failure
    async def _failing_get(url, **kwargs):
        raise _httpx.ConnectError("refused")

    with patch("app.monitor.list_registry", new_callable=AsyncMock, return_value=[down_instance]):
        with patch("app.monitor.upsert_health", new_callable=AsyncMock):
            with patch("app.monitor.update_instance_status", new_callable=AsyncMock):
                with patch("app.monitor.get_db", return_value=mock_db):
                    with patch("httpx.AsyncClient") as mock_client_cls:
                        mock_client = MagicMock()
                        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                        mock_client.__aexit__ = AsyncMock(return_value=False)
                        mock_client.get = AsyncMock(side_effect=_httpx.ConnectError("refused"))
                        mock_client_cls.return_value = mock_client
                        # Should not raise — registry is resilient to downstream failures
                        await run_health_check_cycle()

    # Registry /health endpoint still responds
    with patch("main.get_db", return_value=mock_db):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/health")
    assert resp.status_code == 200
