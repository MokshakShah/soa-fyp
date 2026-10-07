"""
Provider factory — returns the configured NotificationProvider.

To add a new provider:
  1. Implement NotificationProvider in a new module
  2. Add its name to the factory below
  3. Set NOTIFICATION_PROVIDER=<name> in the environment
"""
import logging
from app.providers.base import NotificationProvider
from app.providers.demo import DemoProvider

logger = logging.getLogger("notification.provider.factory")


def get_provider(provider_name: str) -> NotificationProvider:
    name = provider_name.upper().strip()
    if name == "DEMO":
        return DemoProvider()
    # Future: SMS, EMAIL, etc.
    logger.warning(
        "[factory] Unknown provider '%s', falling back to DEMO", provider_name
    )
    return DemoProvider()
