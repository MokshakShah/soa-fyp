"""
Phase 9 — Notification Service tests.

Covers:
  - Model validation (required fields, invalid enum values)
  - Provider abstraction (Demo provider success/failure)
  - Provider factory fallback
  - Send service workflow (persist → deliver → update)
  - Repository (create, mark_sent, mark_failed, list filters, get)
  - API: POST /api/notifications/send (success, provider failure, invalid payload)
  - API: GET /api/notifications (filters)
  - API: GET /api/notifications/{id} (found, not found)
  - API: GET /health
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from main import app
from app.models.notification import (
    SendNotificationRequest, RecipientType, NotificationPriority,
)
from app.providers.base import DeliveryResult
from app.providers.demo import DemoProvider
from app.providers.factory import get_provider


# ─── helpers ──────────────────────────────────────────────────────────────────

def _req(**kwargs) -> SendNotificationRequest:
    defaults = dict(
        recipient_type=RecipientType.HOSPITAL,
        recipient_name="City General Hospital",
        phone_number="+1-555-0100",
        message="EMERGENCY ALERT — Flood warning. Prepare 5 emergency beds.",
        incident_id="inc-001",
        workflow_id="wf-001",
        priority=NotificationPriority.HIGH,
    )
    defaults.update(kwargs)
    return SendNotificationRequest(**defaults)


def _pending_record(nid="507f1f77bcf86cd799439011"):
    return {
        "id": nid,
        "recipient_type": "HOSPITAL",
        "recipient_id": None,
        "recipient_name": "City General Hospital",
        "phone_number": "+1-555-0100",
        "message": "EMERGENCY ALERT",
        "incident_id": "inc-001",
        "workflow_id": "wf-001",
        "priority": "HIGH",
        "provider": "DEMO",
        "status": "PENDING",
        "sent_at": None,
        "failure_reason": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


def _sent_record(nid="507f1f77bcf86cd799439011"):
    return {**_pending_record(nid), "status": "SENT", "sent_at": datetime.utcnow()}


def _failed_record(nid="507f1f77bcf86cd799439011", reason="Connection refused"):
    return {**_pending_record(nid), "status": "FAILED", "failure_reason": reason}


# ─── Model validation ──────────────────────────────────────────────────────────

def test_send_request_all_required_fields():
    r = _req()
    assert r.recipient_type == RecipientType.HOSPITAL
    assert r.recipient_name == "City General Hospital"
    assert r.phone_number == "+1-555-0100"
    assert r.priority == NotificationPriority.HIGH


def test_send_request_missing_recipient_name_raises():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        SendNotificationRequest(
            recipient_type="HOSPITAL",
            phone_number="+1-555-0100",
            message="Alert",
        )


def test_send_request_missing_message_raises():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        SendNotificationRequest(
            recipient_type="HOSPITAL",
            recipient_name="Hospital",
            phone_number="+1-555-0100",
        )


def test_send_request_invalid_recipient_type_raises():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        SendNotificationRequest(
            recipient_type="UNKNOWN_TYPE",
            recipient_name="X",
            phone_number="+1-555-0100",
            message="Alert",
        )


def test_send_request_default_priority():
    r = SendNotificationRequest(
        recipient_type="HOSPITAL",
        recipient_name="Test",
        phone_number="+1-555",
        message="test",
    )
    assert r.priority == NotificationPriority.NORMAL


def test_all_recipient_types_valid():
    for rtype in ("HOSPITAL", "POLICE", "RESPONSE_TEAM"):
        r = SendNotificationRequest(
            recipient_type=rtype,
            recipient_name="Test",
            phone_number="+1-555",
            message="Alert",
        )
        assert r.recipient_type.value == rtype


# ─── Provider: Demo ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_demo_provider_returns_success():
    provider = DemoProvider()
    result = await provider.deliver(
        recipient_name="City Hospital",
        phone_number="+1-555-0100",
        message="Flood alert",
        priority="HIGH",
        notification_id="n-001",
    )
    assert result.success is True
    assert result.provider == "DEMO"
    assert result.provider_message_id == "demo-n-001"
    assert result.failure_reason is None


@pytest.mark.asyncio
async def test_demo_provider_name():
    assert DemoProvider().provider_name == "DEMO"


def test_provider_factory_demo():
    p = get_provider("DEMO")
    assert p.provider_name == "DEMO"


def test_provider_factory_unknown_falls_back_to_demo():
    p = get_provider("UNKNOWN_PROVIDER")
    assert p.provider_name == "DEMO"


def test_provider_factory_case_insensitive():
    p = get_provider("demo")
    assert p.provider_name == "DEMO"


# ─── Send service ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_service_success_marks_sent():
    from app.services.send_service import send_notification
    pending = _pending_record()
    sent = _sent_record()

    mock_db = MagicMock()
    with patch("app.services.send_service.create_notification", new_callable=AsyncMock, return_value=pending):
        with patch("app.services.send_service.mark_sent", new_callable=AsyncMock, return_value=sent):
            with patch("app.services.send_service.mark_failed", new_callable=AsyncMock) as mock_fail:
                result = await send_notification(mock_db, _req(), DemoProvider())

    assert result["status"] == "SENT"
    mock_fail.assert_not_called()


@pytest.mark.asyncio
async def test_send_service_provider_failure_marks_failed():
    from app.services.send_service import send_notification

    class FailingProvider(DemoProvider):
        async def deliver(self, **kwargs) -> DeliveryResult:
            return DeliveryResult(success=False, provider="DEMO", failure_reason="SMS gateway unreachable")

    pending = _pending_record()
    failed = _failed_record(reason="SMS gateway unreachable")

    mock_db = MagicMock()
    with patch("app.services.send_service.create_notification", new_callable=AsyncMock, return_value=pending):
        with patch("app.services.send_service.mark_sent", new_callable=AsyncMock) as mock_sent:
            with patch("app.services.send_service.mark_failed", new_callable=AsyncMock, return_value=failed):
                result = await send_notification(mock_db, _req(), FailingProvider())

    assert result["status"] == "FAILED"
    assert result["failure_reason"] == "SMS gateway unreachable"
    mock_sent.assert_not_called()


@pytest.mark.asyncio
async def test_send_service_provider_raises_marks_failed():
    from app.services.send_service import send_notification

    class CrashingProvider(DemoProvider):
        async def deliver(self, **kwargs) -> DeliveryResult:
            raise RuntimeError("Unexpected crash")

    pending = _pending_record()
    failed = _failed_record(reason="Provider raised unexpectedly: Unexpected crash")
    mock_db = MagicMock()

    with patch("app.services.send_service.create_notification", new_callable=AsyncMock, return_value=pending):
        with patch("app.services.send_service.mark_failed", new_callable=AsyncMock, return_value=failed):
            result = await send_notification(mock_db, _req(), CrashingProvider())

    assert result["status"] == "FAILED"


@pytest.mark.asyncio
async def test_send_service_persists_before_delivery():
    """create_notification must be called before provider.deliver."""
    from app.services.send_service import send_notification
    call_order = []

    pending = _pending_record()
    sent = _sent_record()

    async def fake_create(db, data):
        call_order.append("create")
        return pending

    async def fake_mark_sent(db, nid, pmid=None):
        call_order.append("mark_sent")
        return sent

    class TrackingProvider(DemoProvider):
        async def deliver(self, **kwargs) -> DeliveryResult:
            call_order.append("deliver")
            return DeliveryResult(success=True, provider="DEMO")

    mock_db = MagicMock()
    with patch("app.services.send_service.create_notification", side_effect=fake_create):
        with patch("app.services.send_service.mark_sent", side_effect=fake_mark_sent):
            await send_notification(mock_db, _req(), TrackingProvider())

    assert call_order == ["create", "deliver", "mark_sent"]


# ─── Repository ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_repo_create_notification():
    from app.repositories.notification_repo import create_notification
    inserted = {**_pending_record(), "_id": "507f1f77bcf86cd799439011"}
    del inserted["id"]

    mock_db = MagicMock()
    mock_db.notifications.insert_one = AsyncMock(
        return_value=MagicMock(inserted_id="507f1f77bcf86cd799439011")
    )
    mock_db.notifications.find_one = AsyncMock(return_value=inserted)

    result = await create_notification(mock_db, {
        "recipient_name": "Hospital",
        "phone_number": "+1-555",
        "message": "Alert",
        "recipient_type": "HOSPITAL",
        "provider": "DEMO",
    })
    assert result["status"] == "PENDING"
    assert result["id"] == "507f1f77bcf86cd799439011"


@pytest.mark.asyncio
async def test_repo_mark_sent():
    from app.repositories.notification_repo import mark_sent
    updated = {**_sent_record(), "_id": "507f1f77bcf86cd799439011"}
    del updated["id"]

    mock_db = MagicMock()
    mock_db.notifications.find_one_and_update = AsyncMock(return_value=updated)

    result = await mark_sent(mock_db, "507f1f77bcf86cd799439011", "demo-msg-1")
    assert result["status"] == "SENT"


@pytest.mark.asyncio
async def test_repo_mark_failed():
    from app.repositories.notification_repo import mark_failed
    updated = {**_failed_record(), "_id": "507f1f77bcf86cd799439011"}
    del updated["id"]

    mock_db = MagicMock()
    mock_db.notifications.find_one_and_update = AsyncMock(return_value=updated)

    result = await mark_failed(mock_db, "507f1f77bcf86cd799439011", "Connection refused")
    assert result["status"] == "FAILED"
    assert result["failure_reason"] == "Connection refused"


@pytest.mark.asyncio
async def test_repo_get_notification_not_found():
    from app.repositories.notification_repo import get_notification
    mock_db = MagicMock()
    mock_db.notifications.find_one = AsyncMock(return_value=None)
    result = await get_notification(mock_db, "507f1f77bcf86cd799439099")
    assert result is None


@pytest.mark.asyncio
async def test_repo_list_with_incident_filter():
    from app.repositories.notification_repo import list_notifications
    mock_db = MagicMock()

    async def fake_cursor():
        yield {**_pending_record(), "_id": "507f1f77bcf86cd799439011"}

    mock_cursor = MagicMock()
    mock_cursor.__aiter__ = lambda s: fake_cursor()
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.sort.return_value = mock_cursor
    mock_db.notifications.find.return_value = mock_cursor

    results = await list_notifications(mock_db, incident_id="inc-001", limit=10)
    query = mock_db.notifications.find.call_args[0][0]
    assert query.get("incident_id") == "inc-001"
    assert len(results) == 1


@pytest.mark.asyncio
async def test_repo_list_with_status_filter():
    from app.repositories.notification_repo import list_notifications
    mock_db = MagicMock()

    async def fake_cursor():
        return
        yield  # empty async generator

    mock_cursor = MagicMock()
    mock_cursor.__aiter__ = lambda s: fake_cursor()
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.sort.return_value = mock_cursor
    mock_db.notifications.find.return_value = mock_cursor

    await list_notifications(mock_db, status="SENT", limit=10)
    query = mock_db.notifications.find.call_args[0][0]
    assert query.get("status") == "SENT"


# ─── API: health ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_health():
    mock_db = MagicMock()
    mock_db.command = AsyncMock(return_value={"ok": 1})
    with patch("main.get_db", return_value=mock_db):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "notification-service"
    assert data["version"] == "0.9.0"
    assert "provider" in data


# ─── API: POST /send — success ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_send_success():
    sent = _sent_record()
    with patch("app.routers.notifications.send_notification", new_callable=AsyncMock, return_value=sent):
        with patch("app.routers.notifications.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/notifications/send", json={
                    "recipient_type": "HOSPITAL",
                    "recipient_name": "City General Hospital",
                    "phone_number": "+1-555-0100",
                    "message": "EMERGENCY ALERT — Flood warning.",
                    "incident_id": "inc-001",
                    "workflow_id": "wf-001",
                    "priority": "HIGH",
                })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "SENT"


@pytest.mark.asyncio
async def test_api_send_provider_failure_returns_201_with_failed_status():
    """Provider failure persists FAILED — still returns 201 with the record."""
    failed = _failed_record(reason="SMS gateway unreachable")
    with patch("app.routers.notifications.send_notification", new_callable=AsyncMock, return_value=failed):
        with patch("app.routers.notifications.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/notifications/send", json={
                    "recipient_type": "HOSPITAL",
                    "recipient_name": "City Hospital",
                    "phone_number": "+1-555-0100",
                    "message": "Alert",
                })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "FAILED"
    assert data["failure_reason"] == "SMS gateway unreachable"


@pytest.mark.asyncio
async def test_api_send_missing_required_fields_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/notifications/send", json={
            "recipient_type": "HOSPITAL",
            # missing recipient_name, phone_number, message
        })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_send_invalid_recipient_type_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/notifications/send", json={
            "recipient_type": "INVALID",
            "recipient_name": "X",
            "phone_number": "+1-555",
            "message": "Alert",
        })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_send_police_recipient_type():
    sent = {**_sent_record(), "recipient_type": "POLICE"}
    with patch("app.routers.notifications.send_notification", new_callable=AsyncMock, return_value=sent):
        with patch("app.routers.notifications.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/notifications/send", json={
                    "recipient_type": "POLICE",
                    "recipient_name": "Central Police Station",
                    "phone_number": "+1-555-0400",
                    "message": "Police assistance required.",
                })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_api_send_response_team_recipient_type():
    sent = {**_sent_record(), "recipient_type": "RESPONSE_TEAM"}
    with patch("app.routers.notifications.send_notification", new_callable=AsyncMock, return_value=sent):
        with patch("app.routers.notifications.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/notifications/send", json={
                    "recipient_type": "RESPONSE_TEAM",
                    "recipient_name": "Alpha Response Team",
                    "phone_number": "+1-555-0500",
                    "message": "Respond immediately.",
                })
    assert resp.status_code == 201


# ─── API: GET /api/notifications ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_list_notifications_empty():
    with patch("app.routers.notifications.list_notifications", new_callable=AsyncMock, return_value=[]):
        with patch("app.routers.notifications.count_notifications", new_callable=AsyncMock, return_value=0):
            with patch("app.routers.notifications.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/notifications")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_api_list_notifications_with_results():
    notifications = [_sent_record(), _sent_record("507f1f77bcf86cd799439022")]
    with patch("app.routers.notifications.list_notifications", new_callable=AsyncMock, return_value=notifications):
        with patch("app.routers.notifications.count_notifications", new_callable=AsyncMock, return_value=2):
            with patch("app.routers.notifications.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/notifications")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2
    assert len(resp.json()["items"]) == 2


@pytest.mark.asyncio
async def test_api_list_notifications_incident_filter_passed():
    with patch("app.routers.notifications.list_notifications", new_callable=AsyncMock, return_value=[]) as mock_list:
        with patch("app.routers.notifications.count_notifications", new_callable=AsyncMock, return_value=0):
            with patch("app.routers.notifications.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    await ac.get("/api/notifications?incident_id=inc-001")
    call_kwargs = mock_list.call_args.kwargs
    assert call_kwargs.get("incident_id") == "inc-001"


@pytest.mark.asyncio
async def test_api_list_notifications_status_filter_passed():
    with patch("app.routers.notifications.list_notifications", new_callable=AsyncMock, return_value=[]) as mock_list:
        with patch("app.routers.notifications.count_notifications", new_callable=AsyncMock, return_value=0):
            with patch("app.routers.notifications.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    await ac.get("/api/notifications?status=FAILED")
    call_kwargs = mock_list.call_args.kwargs
    assert call_kwargs.get("status") == "FAILED"


# ─── API: GET /api/notifications/{id} ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_get_notification_found():
    record = _sent_record()
    with patch("app.routers.notifications.get_notification", new_callable=AsyncMock, return_value=record):
        with patch("app.routers.notifications.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get(f"/api/notifications/{record['id']}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "SENT"


@pytest.mark.asyncio
async def test_api_get_notification_not_found():
    with patch("app.routers.notifications.get_notification", new_callable=AsyncMock, return_value=None):
        with patch("app.routers.notifications.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/notifications/nonexistent")
    assert resp.status_code == 404
