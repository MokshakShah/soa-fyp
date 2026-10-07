"""
Notification send service.

Coordinates the full delivery workflow:
  1. Persist notification (status=PENDING)
  2. Call provider.deliver()
  3. Update status to SENT or FAILED
  4. Return the final persisted record

Provider failures are caught here — the function always returns a record,
never raises. Callers can inspect `status` to detect failure.
"""
import logging
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.notification import SendNotificationRequest
from app.providers.base import NotificationProvider
from app.repositories.notification_repo import (
    create_notification, mark_sent, mark_failed,
)

logger = logging.getLogger("notification.send_service")


async def send_notification(
    db: AsyncIOMotorDatabase,
    request: SendNotificationRequest,
    provider: NotificationProvider,
) -> dict:
    """
    Full send workflow: persist → deliver → update status → return.

    Never raises. On provider error, persists FAILED with the failure reason.
    """
    # 1. Persist as PENDING
    record = await create_notification(db, {
        "recipient_type": request.recipient_type.value,
        "recipient_id": request.recipient_id,
        "recipient_name": request.recipient_name,
        "phone_number": request.phone_number,
        "message": request.message,
        "incident_id": request.incident_id,
        "workflow_id": request.workflow_id,
        "priority": request.priority.value,
        "provider": provider.provider_name,
    })
    notification_id = record["id"]

    # 2. Deliver
    try:
        result = await provider.deliver(
            recipient_name=request.recipient_name,
            phone_number=request.phone_number,
            message=request.message,
            priority=request.priority.value,
            notification_id=notification_id,
        )
    except Exception as exc:
        # Provider must not raise, but guard anyway
        err = f"Provider raised unexpectedly: {exc}"
        logger.error("[send_service] %s notification_id=%s", err, notification_id)
        final = await mark_failed(db, notification_id, err)
        return final or record

    # 3. Update status
    if result.success:
        final = await mark_sent(db, notification_id, result.provider_message_id)
        logger.info(
            "[send_service] SENT notification_id=%s provider=%s",
            notification_id, provider.provider_name,
        )
    else:
        reason = result.failure_reason or "Provider returned failure"
        final = await mark_failed(db, notification_id, reason)
        logger.warning(
            "[send_service] FAILED notification_id=%s reason=%s",
            notification_id, reason,
        )

    response_dict = final or record
    # Broadcast to SSE clients
    from app.services.sse import broadcast
    import asyncio
    asyncio.create_task(broadcast(response_dict))
    
    return response_dict
