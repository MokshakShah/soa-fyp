"""
NotificationProvider — abstract base for all delivery providers.

Every provider receives a notification payload and returns a DeliveryResult.
The Notification Service business logic never depends on provider internals.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class DeliveryResult:
    success: bool
    provider: str
    provider_message_id: Optional[str] = None
    failure_reason: Optional[str] = None


class NotificationProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identifier stored on the notification record."""

    @abstractmethod
    async def deliver(
        self,
        recipient_name: str,
        phone_number: str,
        message: str,
        priority: str,
        notification_id: str,
    ) -> DeliveryResult:
        """
        Deliver the notification.
        Must not raise — return DeliveryResult(success=False) on any error.
        """
