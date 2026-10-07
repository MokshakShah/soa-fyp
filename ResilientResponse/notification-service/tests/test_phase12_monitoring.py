"""
Phase 12 — Notification Service monitoring tests.

Covers:
  - GET /api/notifications/summary counts (total, by_status, sent, failed, pending)
  - Structured logging: SENT log after successful delivery
  - Structured logging: FAILED log after failed delivery
"""
import logging
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from main import app
from app.providers.demo import DemoProvider
from app.providers.base import DeliveryResult


# ─── helpers ──────────────────────────────────────────────────────────────────

def _pending(nid="507f1f77bcf86cd799439011"):
    return {
        "id": nid,
        "recipient_type": "HOSPITAL",
        "recipient_id": None,
        "recipient_name": "City Hospital",
        "phone_number": "+1-555-0100",
        "message": "EMERGENCY",
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


# ─── /api/notifications/summary ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notification_summary_returns_correct_fields():
    """GET /api/notifications/summary returns total, by_status, sent, failed, pending."""
    summary_data = {
        "total": 30,
        "by_status": {"SENT": 25, "FAILED": 3, "PENDING": 2},
        "sent": 25,
        "failed": 3,
        "pending": 2,
    }
    with patch("app.routers.notifications.notification_status_summary", new_callable=AsyncMock, return_value=summary_data):
        with patch("app.routers.notifications.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/notifications/summary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 30
    assert data["sent"] == 25
    assert data["failed"] == 3
    assert data["pending"] == 2
    assert "by_status" in data


@pytest.mark.asyncio
async def test_notification_summary_empty():
    """Empty database returns zeros for all counts."""
    summary_data = {
        "total": 0,
        "by_status": {},
        "sent": 0,
        "failed": 0,
        "pending": 0,
    }
    with patch("app.routers.notifications.notification_status_summary", new_callable=AsyncMock, return_value=summary_data):
        with patch("app.routers.notifications.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/notifications/summary")

    data = resp.json()
    assert data["total"] == 0
    assert data["sent"] == 0
    assert data["failed"] == 0


@pytest.mark.asyncio
async def test_notification_summary_all_sent():
    """When all notifications are SENT, failed and pending are zero."""
    summary_data = {
        "total": 5,
        "by_status": {"SENT": 5},
        "sent": 5,
        "failed": 0,
        "pending": 0,
    }
    with patch("app.routers.notifications.notification_status_summary", new_callable=AsyncMock, return_value=summary_data):
        with patch("app.routers.notifications.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/notifications/summary")

    data = resp.json()
    assert data["total"] == 5
    assert data["sent"] == 5
    assert data["failed"] == 0


@pytest.mark.asyncio
async def test_notification_summary_by_status_matches_individual_counts():
    """by_status entries sum to total; individual fields match by_status values."""
    summary_data = {
        "total": 10,
        "by_status": {"SENT": 7, "FAILED": 2, "PENDING": 1},
        "sent": 7,
        "failed": 2,
        "pending": 1,
    }
    with patch("app.routers.notifications.notification_status_summary", new_callable=AsyncMock, return_value=summary_data):
        with patch("app.routers.notifications.get_db"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/notifications/summary")

    data = resp.json()
    assert sum(data["by_status"].values()) == data["total"]
    assert data["by_status"]["SENT"] == data["sent"]
    assert data["by_status"]["FAILED"] == data["failed"]


# ─── Structured logging ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_service_logs_sent(caplog):
    """Successful delivery logs SENT with notification_id and provider."""
    from app.services.send_service import send_notification
    from app.models.notification import SendNotificationRequest, RecipientType, NotificationPriority

    pending = _pending()
    sent = {**pending, "status": "SENT", "sent_at": datetime.utcnow()}

    req = SendNotificationRequest(
        recipient_type=RecipientType.HOSPITAL,
        recipient_name="City Hospital",
        phone_number="+1-555-0100",
        message="Alert",
    )

    with caplog.at_level(logging.INFO, logger="notification.send_service"):
        with patch("app.services.send_service.create_notification", new_callable=AsyncMock, return_value=pending):
            with patch("app.services.send_service.mark_sent", new_callable=AsyncMock, return_value=sent):
                await send_notification(MagicMock(), req, DemoProvider())

    sent_logs = [r for r in caplog.records if "SENT" in r.message]
    assert len(sent_logs) >= 1
    assert "507f1f77bcf86cd799439011" in sent_logs[0].message or "DEMO" in sent_logs[0].message


@pytest.mark.asyncio
async def test_send_service_logs_failed(caplog):
    """Failed delivery logs FAILED with notification_id and reason."""
    from app.services.send_service import send_notification
    from app.models.notification import SendNotificationRequest, RecipientType, NotificationPriority

    pending = _pending()
    failed = {**pending, "status": "FAILED", "failure_reason": "SMS gateway down"}

    class FailingProvider(DemoProvider):
        async def deliver(self, **kwargs) -> DeliveryResult:
            return DeliveryResult(success=False, provider="DEMO", failure_reason="SMS gateway down")

    req = SendNotificationRequest(
        recipient_type=RecipientType.POLICE,
        recipient_name="Central Police",
        phone_number="+1-555-0400",
        message="Police needed",
    )

    with caplog.at_level(logging.WARNING, logger="notification.send_service"):
        with patch("app.services.send_service.create_notification", new_callable=AsyncMock, return_value=pending):
            with patch("app.services.send_service.mark_failed", new_callable=AsyncMock, return_value=failed):
                await send_notification(MagicMock(), req, FailingProvider())

    failed_logs = [r for r in caplog.records if "FAILED" in r.message]
    assert len(failed_logs) >= 1
