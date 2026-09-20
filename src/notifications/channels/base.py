from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import requests

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

    def http_post_with_retry(
        self,
        url: str,
        json_data: Any = None,
        headers: dict[str, str] | None = None,
        timeout: float = 5.0,
        max_retries: int = 3,
        base_backoff_sec: float = 1.0,
    ) -> tuple[bool, int | None, str | None, int, float]:
        """Execute an HTTP POST with exponential backoff for transient failures.

        Retries ONLY on:
        - HTTP 429 (Rate Limit / Too Many Requests)
        - HTTP 5xx (Internal Server Errors)
        - Network Timeout / Connection Error

        Does NOT retry on:
        - HTTP 4xx (except 429), e.g. 400 Bad Request, 401 Unauthorized, 403 Forbidden

        Returns: (success, status_code, error_message, retry_count, latency_ms)
        """
        if not self.is_enabled:
            return False, None, f"Channel '{self.name}' is disabled", 0, 0.0

        if self.dry_run:
            logger.info(f"[{self.name}] Dry-run mode enabled: skipping HTTP POST to {url}")
            return True, 200, None, 0, 0.0

        last_status: int | None = None
        last_error: str | None = None
        total_latency_ms: float = 0.0

        for attempt in range(max_retries + 1):
            start_time = time.perf_counter()
            try:
                response = requests.post(
                    url,
                    json=json_data,
                    headers=headers,
                    timeout=timeout,
                )
                elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                total_latency_ms += elapsed_ms
                last_status = response.status_code

                # Success: 2xx responses
                if 200 <= response.status_code < 300:
                    return True, response.status_code, None, attempt, total_latency_ms

                # Transient Rate Limit (429) or Server Error (5xx)
                if response.status_code == 429 or 500 <= response.status_code < 600:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    if attempt < max_retries:
                        backoff = base_backoff_sec * (2**attempt)
                        logger.warning(
                            f"[{self.name}] Transient error ({last_error}). Retrying in {backoff:.2f}s (attempt {attempt + 1}/{max_retries})..."
                        )
                        time.sleep(backoff)
                        continue
                    return False, last_status, last_error, attempt, total_latency_ms

                # Client Errors (4xx non-429) or other non-transient status -> DO NOT RETRY
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.error(f"[{self.name}] Non-retryable HTTP error: {last_error}")
                return False, last_status, last_error, attempt, total_latency_ms

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.RequestException) as exc:
                elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                total_latency_ms += elapsed_ms
                last_error = f"Network exception: {exc.__class__.__name__} - {str(exc)}"
                if attempt < max_retries:
                    backoff = base_backoff_sec * (2**attempt)
                    logger.warning(
                        f"[{self.name}] Network error ({last_error}). Retrying in {backoff:.2f}s (attempt {attempt + 1}/{max_retries})..."
                    )
                    time.sleep(backoff)
                    continue
                return False, None, last_error, attempt, total_latency_ms

        return False, last_status, last_error or "Max retries exceeded", max_retries, total_latency_ms

    @abstractmethod
    def format_message(self, payload: NotificationPayload) -> Any:
        """Format the generic payload into the channel's native representation."""
        pass

    @abstractmethod
    def send(self, payload: NotificationPayload) -> NotificationResult:
        """Send the notification payload through the channel."""
        pass
