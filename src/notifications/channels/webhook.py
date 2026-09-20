from __future__ import annotations

import logging
import os
from typing import Any

import pandas as pd

from src.notifications.channels.base import BaseNotificationChannel
from src.notifications.models import (
    NotificationChannelType,
    NotificationPayload,
    NotificationResult,
)

logger = logging.getLogger(__name__)


class WebhookChannel(BaseNotificationChannel):
    """Generic webhook adapter for raw JSON delivery via HTTP POST."""

    def __init__(
        self,
        url: str | None = None,
        headers: dict[str, str] | None = None,
        name: str = "GenericWebhook",
        is_enabled: bool = True,
        dry_run: bool = False,
        timeout: float = 5.0,
        max_retries: int = 3,
        base_backoff_sec: float = 1.0,
    ) -> None:
        super().__init__(
            name=name,
            channel_type=NotificationChannelType.WEBHOOK,
            is_enabled=is_enabled,
            dry_run=dry_run,
        )
        self.url = url or os.getenv("GENERIC_WEBHOOK_URL", "")
        self.headers = headers or {"Content-Type": "application/json"}
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_backoff_sec = base_backoff_sec

    def format_message(self, payload: NotificationPayload) -> dict[str, Any]:
        """Convert a NotificationPayload into a standard JSON-serializable dictionary."""
        return payload.to_dict()

    def send(self, payload: NotificationPayload) -> NotificationResult:
        """Deliver the JSON payload via HTTP POST to the target URL."""
        if not self.validate_payload(payload):
            return NotificationResult(
                success=False,
                channel=self.channel_type,
                error_message="Payload validation failed",
                event_id=payload.event_id,
            )

        if not self.url and not self.dry_run:
            logger.error(f"[{self.name}] Cannot send: target URL is not configured.")
            return NotificationResult(
                success=False,
                channel=self.channel_type,
                error_message="Webhook target URL is not configured",
                event_id=payload.event_id,
            )

        body_dict = self.format_message(payload)
        success, status_code, error_msg, retries, latency_ms = self.http_post_with_retry(
            url=self.url,
            json_data=body_dict,
            headers=self.headers,
            timeout=self.timeout,
            max_retries=self.max_retries,
            base_backoff_sec=self.base_backoff_sec,
        )

        return NotificationResult(
            success=success,
            channel=self.channel_type,
            status_code=status_code,
            error_message=error_msg,
            delivered_at=pd.Timestamp.now("UTC") if success else None,
            retry_count=retries,
            event_id=payload.event_id,
            latency_ms=latency_ms,
        )
