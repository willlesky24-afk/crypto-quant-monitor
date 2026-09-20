from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from src.notifications.models import (
    NotificationChannelType,
    NotificationPayload,
    NotificationResult,
)

logger = logging.getLogger(__name__)


class BaseNotificationChannel(ABC):
    """Abstract base class for all notification delivery channels."""

    def __init__(
        self,
        name: str,
        channel_type: NotificationChannelType,
        is_enabled: bool = True,
        dry_run: bool = False,
    ) -> None:
        self.name = name
        self.channel_type = channel_type
        self.is_enabled = is_enabled
        self.dry_run = dry_run

    def validate_payload(self, payload: NotificationPayload) -> bool:
        """Validate that the payload has the mandatory fields for transmission."""
        if not payload.symbol or not payload.timeframe or not payload.event_id:
            logger.warning(f"[{self.name}] Invalid payload: missing mandatory identifiers.")
            return False
        if payload.price <= 0:
            logger.warning(f"[{self.name}] Invalid payload: price must be positive.")
            return False
        return True

    @abstractmethod
    def format_message(self, payload: NotificationPayload) -> Any:
        """Format the generic payload into the channel's native representation (e.g. dict, embed, string)."""
        pass

    @abstractmethod
    def send(self, payload: NotificationPayload) -> NotificationResult:
        """Send the notification payload through the channel."""
        pass
