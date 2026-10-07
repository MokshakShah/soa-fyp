"""
AlertSourceAdapter — base class for all alert source adapters.

Every adapter converts source-specific data into NormalizedAlert objects.
The rest of alert-service only works with NormalizedAlert and never imports
source-specific formats.
"""
from abc import ABC, abstractmethod
from typing import List
from app.models.alert import NormalizedAlert


class AlertSourceAdapter(ABC):
    """Abstract base for all alert source adapters."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Logical name used as the `source` field in NormalizedAlert."""

    @abstractmethod
    async def fetch(self) -> List[NormalizedAlert]:
        """
        Fetch alerts from the source and return normalized alerts.
        Must handle network errors gracefully — raise AdapterError on failure.
        """

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(source={self.source_name})"


class AdapterError(Exception):
    """Raised when an adapter cannot fetch or parse alerts."""
    def __init__(self, source: str, message: str, cause: Exception | None = None):
        self.source = source
        self.cause = cause
        super().__init__(f"[{source}] {message}")
