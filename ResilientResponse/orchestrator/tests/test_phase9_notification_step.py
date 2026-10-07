"""
Phase 9 — Orchestrator notification step tests.

Covers:
  - dispatch_notification calls notification-service via discovery
  - notification failure → PARTIAL workflow (non-critical step)
  - notification uses correct recipient types
  - hospital + police both notified when data available
  - hospital-only notification when no police in context
  - all notifications failing → ServiceCallError raised
  - workflow event persisted for dispatch_notification
  - PRIMARY/BACKUP failover reaches notification-service backup
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.workflows.engine import run_workflow
from app.workflows.step_handlers import execute_step_action, _dispatch_notification
from app.workflows.definitions import get_workflow_definition
from app.clients.service_client import ServiceCallError
from app.models.workflow import WorkflowStatus, WorkflowEventStatus


# ─── helpers ──────────────────────────────────────────────────────────────────

def _notification_step():
    return get_workflow_definition("FLOOD").steps[-1]  # dispatch_notification is last


def _context(**kwargs):
    base = {
        "incident_id": "inc-test",
        "workflow_id": "wf-test",
        "classification": {"disaster_type": "FLOOD", "severity": "HIGH"},
        "latitude": 40.71,
        "longitude": -74.0,
        "reserve_beds": 5,
        "hospitals": [{"id": "h1", "name": "City Hospital", "phone": "+1-555-0100", "emergency_phone": "+1-555-0911", "city": "Test City", "latitude": 40.72, "longitude": -74.01}],
        "reserved_hospital_id": "h1",
        "reserved_hospital": {"id": "h1", "name": "City Hospital", "phone": "+1-555-0100", "emergency_phone": "+1-555-0911"},
        "police_stations": [{"id": "p1", "name": "Central Police", "phone": "+1-555-0400", "emergency_phone": "+1-555-0100"}],
        "resources": [{"id": "r1", "name": "Ambulance", "latitude": 40.73, "longitude": -74.02}],
        "allocated_resource_id": "r1",
    }
    base.update(kwargs)
    return base


# ─── dispatch_notification step action ────────────────────────────────────────

def test_dispatch_notification_is_last_step():
    step = _notification_step()
    assert step.action == "dispatch_notification"
    assert step.service == "notification-service"
    assert step.critical is False


def test_dispatch_notification_not_deferred():
    """Phase 9: deferred param should be removed from definitions."""
    step = _notification_step()
    assert "deferred" not in step.params


@pytest.mark.asyncio
async def test_dispatch_notification_calls_notification_service():
    """dispatch_notification must call notification-service via call_service."""
    step = _notification_step()
    ctx = _context()
    sent_record = {"id": "n1", "status": "SENT", "recipient_name": "City Hospital"}

    with patch("app.workflows.step_handlers.call_service", new_callable=AsyncMock,
               return_value=sent_record) as mock_call:
        result = await execute_step_action(step, ctx)

    assert result["notifications_sent"] > 0
    # Verify notification-service was called
    calls = mock_call.call_args_list
    services_called = [c.args[0] for c in calls]
    assert "notification-service" in services_called


@pytest.mark.asyncio
async def test_dispatch_notification_sends_to_hospital():
    """Hospital notification must use HOSPITAL recipient_type."""
    ctx = _context(police_stations=[])  # no police — only hospital
    sent_record = {"id": "n1", "status": "SENT", "recipient_name": "City Hospital"}

    captured_payloads = []

    async def fake_call(service, method, path, **kwargs):
        if service == "notification-service":
            captured_payloads.append(kwargs.get("json_body", {}))
            return sent_record
        return {}

    with patch("app.workflows.step_handlers.call_service", side_effect=fake_call):
        result = await _dispatch_notification(ctx, {})

    assert result["notifications_sent"] == 1
    assert captured_payloads[0]["recipient_type"] == "HOSPITAL"
    assert captured_payloads[0]["phone_number"] == "+1-555-0911"


@pytest.mark.asyncio
async def test_dispatch_notification_sends_to_police():
    """Police notification must use POLICE recipient_type."""
    sent_record = {"id": "n2", "status": "SENT"}
    captured_payloads = []

    async def fake_call(service, method, path, **kwargs):
        if service == "notification-service":
            captured_payloads.append(kwargs.get("json_body", {}))
            return sent_record
        return {}

    ctx = _context()
    with patch("app.workflows.step_handlers.call_service", side_effect=fake_call):
        result = await _dispatch_notification(ctx, {})

    recipient_types = [p["recipient_type"] for p in captured_payloads]
    assert "POLICE" in recipient_types


@pytest.mark.asyncio
async def test_dispatch_notification_both_hospital_and_police():
    """Both hospital and police receive notifications."""
    sent_record = {"id": "n1", "status": "SENT"}
    call_count = {"n": 0}

    async def fake_call(service, method, path, **kwargs):
        if service == "notification-service":
            call_count["n"] += 1
            return sent_record
        return {}

    ctx = _context()
    with patch("app.workflows.step_handlers.call_service", side_effect=fake_call):
        result = await _dispatch_notification(ctx, {})

    assert call_count["n"] == 2
    assert result["notifications_sent"] == 2


@pytest.mark.asyncio
async def test_dispatch_notification_all_failures_raises():
    """If all notifications fail, ServiceCallError is raised."""
    async def fake_call(service, method, path, **kwargs):
        if service == "notification-service":
            raise ServiceCallError("notification-service unavailable")
        return {}

    ctx = _context()
    with pytest.raises(ServiceCallError):
        with patch("app.workflows.step_handlers.call_service", side_effect=fake_call):
            await _dispatch_notification(ctx, {})


@pytest.mark.asyncio
async def test_dispatch_notification_partial_success_no_raise():
    """Hospital notification succeeds but police fails — no raise, partial result."""
    sent_record = {"id": "n1", "status": "SENT"}
    call_count = {"n": 0}

    async def fake_call(service, method, path, **kwargs):
        if service == "notification-service":
            call_count["n"] += 1
            body = kwargs.get("json_body", {})
            if body.get("recipient_type") == "HOSPITAL":
                return sent_record
            raise ServiceCallError("police notification failed")
        return {}

    ctx = _context()
    with patch("app.workflows.step_handlers.call_service", side_effect=fake_call):
        result = await _dispatch_notification(ctx, {})

    # Hospital succeeded → result returned, police failure in errors
    assert result["notifications_sent"] == 1
    assert len(result["errors"]) == 1


@pytest.mark.asyncio
async def test_dispatch_notification_message_contains_incident_info():
    """Notification message must include disaster type and severity."""
    sent_record = {"id": "n1", "status": "SENT"}
    captured = []

    async def fake_call(service, method, path, **kwargs):
        if service == "notification-service":
            captured.append(kwargs.get("json_body", {}).get("message", ""))
            return sent_record
        return {}

    ctx = _context()
    with patch("app.workflows.step_handlers.call_service", side_effect=fake_call):
        await _dispatch_notification(ctx, {})

    assert len(captured) > 0
    msg = captured[0]
    assert "FLOOD" in msg
    assert "HIGH" in msg
    assert "inc-test" in msg


@pytest.mark.asyncio
async def test_dispatch_notification_no_hospital_no_police_no_raise():
    """No hospital or police in context → no notifications, no raise."""
    ctx = _context(hospitals=[], police_stations=[], reserved_hospital=None, reserved_hospital_id=None)
    with patch("app.workflows.step_handlers.call_service", new_callable=AsyncMock):
        result = await _dispatch_notification(ctx, {})
    assert result["notifications_sent"] == 0


# ─── Workflow engine integration ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notification_failure_produces_partial_workflow():
    """Non-critical notification failure → workflow status PARTIAL."""
    async def fake_execute(step, context):
        if step.action == "dispatch_notification":
            raise ServiceCallError("notification-service unreachable")
        if step.action == "search_hospitals":
            context["hospitals"] = [{"id": "h1"}]
            return {"count": 1}
        if step.action == "reserve_hospital_beds":
            context["reserved_hospital_id"] = "h1"
            return {"hospital_id": "h1"}
        if step.action == "search_resources":
            context["resources"] = [{"id": "r1"}]
            return {"count": 1}
        if step.action == "allocate_resource":
            return {"resource_id": "r1"}
        return {}

    with patch("app.workflows.engine.create_workflow", new_callable=AsyncMock) as mock_create:
        with patch("app.workflows.engine.update_workflow", new_callable=AsyncMock):
            with patch("app.workflows.engine.create_workflow_event", new_callable=AsyncMock):
                with patch("app.workflows.engine.get_workflow", new_callable=AsyncMock) as mock_get:
                    with patch("app.workflows.engine.list_workflow_events", new_callable=AsyncMock, return_value=[]):
                        with patch("app.workflows.engine.execute_step_action", side_effect=fake_execute):
                            mock_create.return_value = {"id": "wf9", "created_at": datetime.utcnow()}
                            mock_get.return_value = {"id": "wf9", "status": WorkflowStatus.PARTIAL.value}
                            result = await run_workflow(
                                MagicMock(),
                                incident_id="inc-9",
                                disaster_type="FLOOD",
                                classification={"disaster_type": "FLOOD", "severity": "HIGH"},
                            )
    assert result["status"] == WorkflowStatus.PARTIAL.value


@pytest.mark.asyncio
async def test_notification_success_does_not_affect_completed_workflow():
    """Successful notification → workflow remains COMPLETED."""
    async def fake_execute(step, context):
        if step.action == "dispatch_notification":
            return {"notifications_sent": 2, "results": [], "errors": []}
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
        return {}

    with patch("app.workflows.engine.create_workflow", new_callable=AsyncMock) as mock_create:
        with patch("app.workflows.engine.update_workflow", new_callable=AsyncMock):
            with patch("app.workflows.engine.create_workflow_event", new_callable=AsyncMock):
                with patch("app.workflows.engine.get_workflow", new_callable=AsyncMock) as mock_get:
                    with patch("app.workflows.engine.list_workflow_events", new_callable=AsyncMock, return_value=[]):
                        with patch("app.workflows.engine.execute_step_action", side_effect=fake_execute):
                            mock_create.return_value = {"id": "wf10", "created_at": datetime.utcnow()}
                            mock_get.return_value = {"id": "wf10", "status": WorkflowStatus.COMPLETED.value}
                            result = await run_workflow(
                                MagicMock(),
                                incident_id="inc-10",
                                disaster_type="FLOOD",
                                classification={"disaster_type": "FLOOD", "severity": "LOW"},
                            )
    assert result["status"] == WorkflowStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_notification_event_persisted():
    """dispatch_notification step result is recorded as a workflow event."""
    events_recorded = []

    async def fake_execute(step, context):
        if step.action == "dispatch_notification":
            return {"notifications_sent": 1, "results": [{"recipient": "Hospital", "status": "SENT"}], "errors": []}
        if step.action in ("search_hospitals", "reserve_hospital_beds"):
            if step.action == "search_hospitals":
                context["hospitals"] = [{"id": "h1"}]
            return {}
        if step.action in ("search_resources", "allocate_resource"):
            if step.action == "search_resources":
                context["resources"] = [{"id": "r1"}]
            return {}
        return {}

    async def capture_event(db, data):
        events_recorded.append(data)
        return {"id": f"e{len(events_recorded)}", **data}

    with patch("app.workflows.engine.create_workflow", new_callable=AsyncMock) as mock_create:
        with patch("app.workflows.engine.update_workflow", new_callable=AsyncMock):
            with patch("app.workflows.engine.create_workflow_event", side_effect=capture_event):
                with patch("app.workflows.engine.get_workflow", new_callable=AsyncMock) as mock_get:
                    with patch("app.workflows.engine.list_workflow_events", new_callable=AsyncMock, return_value=events_recorded):
                        with patch("app.workflows.engine.execute_step_action", side_effect=fake_execute):
                            mock_create.return_value = {"id": "wf11", "created_at": datetime.utcnow()}
                            mock_get.return_value = {"id": "wf11", "status": WorkflowStatus.COMPLETED.value}
                            await run_workflow(
                                MagicMock(),
                                incident_id="inc-11",
                                disaster_type="FLOOD",
                                classification={"disaster_type": "FLOOD"},
                            )

    notification_events = [e for e in events_recorded if e.get("action") == "dispatch_notification"]
    assert len(notification_events) == 1
    assert notification_events[0]["status"] == WorkflowEventStatus.SUCCESS.value


# ─── Service Registry discovery ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notification_step_uses_registry_discovery():
    """Notification calls go through call_service which uses registry discovery."""
    from app.clients import service_client

    instances = [
        {"base_url": "http://notification-primary:8007", "instance_role": "PRIMARY", "instance_id": "n-primary"},
    ]

    class FakeResp:
        status_code = 201

        def json(self):
            return {"id": "n1", "status": "SENT", "recipient_name": "Hospital"}

        content = b'{"id":"n1","status":"SENT"}'

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def request(self, method, url, **kwargs):
            assert "notification-primary" in url
            assert "/api/notifications/send" in url
            return FakeResp()

    with patch("app.clients.service_client.discover_ordered_instances",
               new_callable=AsyncMock, return_value=instances):
        with patch("app.clients.service_client.httpx.AsyncClient", return_value=FakeClient()):
            data = await service_client.call_service(
                "notification-service", "POST", "/api/notifications/send",
                json_body={
                    "recipient_type": "HOSPITAL",
                    "recipient_name": "Hospital",
                    "phone_number": "+1-555",
                    "message": "Alert",
                },
            )
    assert data["status"] == "SENT"


@pytest.mark.asyncio
async def test_notification_primary_backup_failover():
    """If PRIMARY notification instance fails, BACKUP is tried."""
    from app.clients import service_client

    instances = [
        {"base_url": "http://notif-primary:8007", "instance_role": "PRIMARY", "instance_id": "notif-primary"},
        {"base_url": "http://notif-backup:8007", "instance_role": "BACKUP", "instance_id": "notif-backup"},
    ]
    call_urls = []

    class FakeRespOk:
        status_code = 201

        def json(self):
            return {"id": "n2", "status": "SENT"}

        content = b'{"id":"n2","status":"SENT"}'

    class FakeRespFail:
        status_code = 503
        content = b"unavailable"

        def json(self):
            return {}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def request(self, method, url, **kwargs):
            call_urls.append(url)
            if "primary" in url:
                return FakeRespFail()
            return FakeRespOk()

    with patch("app.clients.service_client.discover_ordered_instances",
               new_callable=AsyncMock, return_value=instances):
        with patch("app.clients.service_client.httpx.AsyncClient", return_value=FakeClient()):
            data = await service_client.call_service(
                "notification-service", "POST", "/api/notifications/send",
                json_body={"recipient_type": "HOSPITAL", "recipient_name": "H", "phone_number": "+1", "message": "A"},
            )

    assert data["status"] == "SENT"
    assert len(call_urls) == 2  # tried primary, fell over to backup
    assert any("primary" in u for u in call_urls)
    assert any("backup" in u for u in call_urls)
