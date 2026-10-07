"""Phase 11 — resilience and failover validation."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.clients.service_client import ServiceCallError
from app.workflows.engine import run_workflow
from app.workflows.step_handlers import _dispatch_notification
from app.models.workflow import WorkflowStatus


@pytest.mark.asyncio
async def test_service_client_skips_duplicate_instance_urls():
    """Duplicate registry entries for the same base URL should not be retried twice."""
    from app.clients import service_client

    instances = [
        {"base_url": "http://primary:8004", "instance_id": "p1", "instance_role": "PRIMARY"},
        {"base_url": "http://primary:8004", "instance_id": "p2", "instance_role": "BACKUP"},
    ]
    call_urls = []

    class FakeResp:
        status_code = 200
        content = b'{"ok": true}'

        def json(self):
            return {"ok": True}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def request(self, method, url, **kwargs):
            call_urls.append(url)
            return FakeResp()

    with patch("app.clients.service_client.discover_ordered_instances", new_callable=AsyncMock, return_value=instances):
        with patch("app.clients.service_client.httpx.AsyncClient", return_value=FakeClient()):
            data = await service_client.call_service("hospital-service", "GET", "/api/hospitals/search")

    assert data == {"ok": True}
    assert len(call_urls) == 1
    assert "primary:8004" in call_urls[0]


@pytest.mark.asyncio
async def test_service_client_raises_after_all_instances_fail():
    """When every discovered instance fails, the client surfaces a single ServiceCallError."""
    from app.clients import service_client

    instances = [
        {"base_url": "http://primary:8004", "instance_id": "p1", "instance_role": "PRIMARY"},
        {"base_url": "http://backup:8014", "instance_id": "b1", "instance_role": "BACKUP"},
    ]

    class FakeResp:
        status_code = 503
        content = b"unavailable"
        text = "unavailable"

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def request(self, method, url, **kwargs):
            return FakeResp()

    with patch("app.clients.service_client.discover_ordered_instances", new_callable=AsyncMock, return_value=instances):
        with patch("app.clients.service_client.httpx.AsyncClient", return_value=FakeClient()):
            with pytest.raises(ServiceCallError, match="unavailable after failover"):
                await service_client.call_service("hospital-service", "GET", "/api/hospitals/search")


@pytest.mark.asyncio
async def test_route_failure_keeps_workflow_partial():
    """A route-provider failure should be non-critical and leave the workflow in PARTIAL."""

    async def fake_execute(step, context):
        if step.action == "search_hospitals":
            context["hospitals"] = [{"id": "h1"}]
            return {"count": 1}
        if step.action == "reserve_hospital_beds":
            return {"hospital_id": "h1"}
        if step.action == "search_resources":
            context["resources"] = [{"id": "r1"}]
            return {"count": 1}
        if step.action == "allocate_resource":
            return {"resource_id": "r1"}
        if step.action == "plan_route":
            raise ServiceCallError("route-provider unavailable")
        return {}

    with patch("app.workflows.engine.create_workflow", new_callable=AsyncMock) as mock_create:
        with patch("app.workflows.engine.update_workflow", new_callable=AsyncMock):
            with patch("app.workflows.engine.create_workflow_event", new_callable=AsyncMock):
                with patch("app.workflows.engine.get_workflow", new_callable=AsyncMock) as mock_get:
                    with patch("app.workflows.engine.list_workflow_events", new_callable=AsyncMock, return_value=[]):
                        with patch("app.workflows.engine.execute_step_action", side_effect=fake_execute):
                            mock_create.return_value = {"id": "wf-phase11", "created_at": __import__("datetime").datetime.utcnow()}
                            mock_get.return_value = {"id": "wf-phase11", "status": WorkflowStatus.PARTIAL.value}
                            result = await run_workflow(
                                MagicMock(),
                                incident_id="inc-phase11",
                                disaster_type="FLOOD",
                                classification={"disaster_type": "FLOOD", "severity": "HIGH"},
                            )

    assert result["status"] == WorkflowStatus.PARTIAL.value


@pytest.mark.asyncio
async def test_notification_partial_failure_returns_errors():
    """Notification delivery failure should report partial results without crashing the workflow."""
    ctx = {
        "incident_id": "inc-alert",
        "workflow_id": "wf-alert",
        "classification": {"disaster_type": "FLOOD", "severity": "HIGH"},
        "hospitals": [{"id": "h1", "name": "City Hospital", "phone": "+1-555-0100", "emergency_phone": "+1-555-0911"}],
        "reserved_hospital": {"id": "h1", "name": "City Hospital", "phone": "+1-555-0100", "emergency_phone": "+1-555-0911"},
        "police_stations": [{"id": "p1", "name": "Central Police"}],
    }

    async def fake_call(service, method, path, **kwargs):
        if service != "notification-service":
            return {}
        body = kwargs.get("json_body", {})
        if body.get("recipient_type") == "HOSPITAL":
            return {"id": "n1", "status": "SENT"}
        raise ServiceCallError("police provider unavailable")

    with patch("app.workflows.step_handlers.call_service", side_effect=fake_call):
        result = await _dispatch_notification(ctx, {})

    assert result["notifications_sent"] == 1
    assert len(result["errors"]) == 1
    assert "Police" in result["errors"][0] or "police" in result["errors"][0]
