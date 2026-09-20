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

# Discord Embed Colors
COLOR_LONG = 0x2ECC71  # Vibrant Green
COLOR_SHORT = 0xE74C3C  # Vibrant Red
COLOR_NEUTRAL = 0x3498DB  # Info Blue


class DiscordWebhookChannel(BaseNotificationChannel):
    """Notification delivery adapter for Discord Webhooks using Rich Embeds."""

    def __init__(
        self,
        webhook_url: str | None = None,
        name: str = "Discord",
        is_enabled: bool = True,
        dry_run: bool = False,
        timeout: float = 5.0,
        max_retries: int = 3,
        base_backoff_sec: float = 1.0,
    ) -> None:
        super().__init__(
            name=name,
            channel_type=NotificationChannelType.DISCORD,
            is_enabled=is_enabled,
            dry_run=dry_run,
        )
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL", "")
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_backoff_sec = base_backoff_sec

    def format_message(self, payload: NotificationPayload) -> dict[str, Any]:
        """Convert a NotificationPayload into a structured Discord Rich Embed."""
        # Determine semantic color based on action & direction
        if payload.direction == "LONG" or payload.action == "BUY":
            color = COLOR_LONG
            title_emoji = "🟢"
        elif payload.direction == "SHORT" or payload.action == "SELL":
            color = COLOR_SHORT
            title_emoji = "🔴"
        else:
            color = COLOR_NEUTRAL
            title_emoji = "⏳"

        embed_fields: list[dict[str, Any]] = [
            {"name": "Action / Direction", "value": f"{payload.action} ({payload.direction})", "inline": True},
            {"name": "Price", "value": f"${payload.price:,.2f}", "inline": True},
            {"name": "Market Regime", "value": f"`{payload.regime}`", "inline": True},
            {"name": "Confidence", "value": f"{payload.confidence * 100:.1f}%", "inline": True},
            {"name": "Predictive Score", "value": f"{payload.predictive_score:.2f}", "inline": True},
            {"name": "Quant Score", "value": f"{payload.quant_score:.1f}", "inline": True},
        ]

        if payload.stop_loss is not None:
            embed_fields.append({"name": "Stop Loss", "value": f"${payload.stop_loss:,.2f}", "inline": True})
        if payload.take_profit is not None:
            embed_fields.append({"name": "Take Profit", "value": f"${payload.take_profit:,.2f}", "inline": True})
        if payload.risk_reward_ratio is not None:
            embed_fields.append({"name": "R:R Ratio", "value": f"{payload.risk_reward_ratio:.2f}", "inline": True})

        embed_fields.append({
            "name": "Reasoning & Context",
            "value": payload.reasoning or "No additional reasoning provided.",
            "inline": False,
        })

        embed = {
            "title": f"{title_emoji} SIGNAL ALERT: {payload.symbol} [{payload.timeframe.upper()}]",
            "description": payload.summary,
            "color": color,
            "fields": embed_fields,
            "footer": {
                "text": f"Event ID: {payload.event_id} • Priority: {payload.priority.value} • Crypto Quant Monitor"
            },
            "timestamp": payload.timestamp.isoformat(),
        }

        return {"embeds": [embed]}

    def send(self, payload: NotificationPayload) -> NotificationResult:
        """Deliver the notification to Discord via Webhook."""
        if not self.validate_payload(payload):
            return NotificationResult(
                success=False,
                channel=self.channel_type,
                error_message="Payload validation failed",
                event_id=payload.event_id,
            )

        if not self.webhook_url and not self.dry_run:
            logger.error(f"[{self.name}] Cannot send: DISCORD_WEBHOOK_URL is not set.")
            return NotificationResult(
                success=False,
                channel=self.channel_type,
                error_message="DISCORD_WEBHOOK_URL is not configured",
                event_id=payload.event_id,
            )

        message_body = self.format_message(payload)
        success, status_code, error_msg, retries, latency_ms = self.http_post_with_retry(
            url=self.webhook_url,
            json_data=message_body,
            headers={"Content-Type": "application/json"},
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
