"""
Demo / Log provider — Phase 9 default transport.

Logs the notification and returns success.
This is the ONLY transport in Phase 9. A real SMS provider can be added
by implementing NotificationProvider and setting NOTIFICATION_PROVIDER=SMS.
"""
import logging
from app.providers.base import NotificationProvider, DeliveryResult

logger = logging.getLogger("notification.provider.demo")


class DemoProvider(NotificationProvider):
    """
    Simulates delivery by logging the notification.
    Always returns success — represents the delivery workflow executing
    without a real external transport.
    """

    @property
    def provider_name(self) -> str:
        return "DEMO"

    async def deliver(
        self,
        recipient_name: str,
        phone_number: str,
        message: str,
        priority: str,
        notification_id: str,
    ) -> DeliveryResult:
        logger.info(
            "[DEMO] Notification %s → %s (%s) [%s]: %s",
            notification_id, recipient_name, phone_number, priority, message,
        )
        return DeliveryResult(
            success=True,
            provider="DEMO",
            provider_message_id=f"demo-{notification_id}",
        )
