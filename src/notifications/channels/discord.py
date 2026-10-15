from __future__ import annotations

import logging
import os
import re
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


def _discord_text(value: Any) -> str:
    """Keep untrusted content from changing Markdown or mentioning users."""
    escaped = str(value).replace("@", "@\u200b")
    return re.sub(r"([\\*_`~|>])", r"\\\1", escaped)


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
        tracked = (
            payload.action in {"BUY", "SELL"}
            and payload.metadata.get("tracking_id")
            and payload.metadata.get("tracking_recorded_at")
            and payload.metadata.get("signal_status") == "ACTIVADA"
        )
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
            {"name": "Action / Direction", "value": f"{_discord_text(payload.action)} ({_discord_text(payload.direction)})", "inline": True},
            {"name": "Entrada validada" if tracked else "Price", "value": f"${payload.price}" if tracked else f"${payload.price:,.2f}", "inline": True},
            {"name": "Market Regime", "value": _discord_text(payload.regime), "inline": True},
            {"name": "Confidence", "value": f"{payload.confidence * 100:.1f}%", "inline": True},
            {"name": "Predictive Score", "value": f"{payload.predictive_score:.2f}", "inline": True},
            {"name": "Quant Score", "value": f"{payload.quant_score:.1f}", "inline": True},
        ]

        if tracked:
            embed_fields.extend([
                {"name": "ID de seguimiento", "value": _discord_text(payload.metadata["tracking_id"]), "inline": True},
                {"name": "Registro (UTC)", "value": _discord_text(payload.metadata["tracking_recorded_at"]), "inline": True},
                {"name": "Estado de señal", "value": _discord_text(payload.metadata["signal_status"]), "inline": True},
            ])

        if payload.stop_loss is not None:
            embed_fields.append({"name": "Stop Loss", "value": f"${payload.stop_loss}" if tracked else f"${payload.stop_loss:,.2f}", "inline": True})
        if payload.take_profit is not None:
            embed_fields.append({"name": "Take Profit", "value": f"${payload.take_profit}" if tracked else f"${payload.take_profit:,.2f}", "inline": True})
        if payload.risk_reward_ratio is not None:
            embed_fields.append({
                "name": "R:R bruto (sin costes)" if tracked else "R:R Ratio",
                "value": str(payload.risk_reward_ratio) if tracked else f"{payload.risk_reward_ratio:.2f}",
                "inline": True,
            })

        embed_fields.append({
            "name": "Reasoning & Context",
            "value": _discord_text(payload.reasoning or "No additional reasoning provided."),
            "inline": False,
        })

        embed = {
            "title": f"{title_emoji} SIGNAL ALERT: {_discord_text(payload.symbol)} [{_discord_text(payload.timeframe.upper())}]",
            "description": _discord_text(payload.summary),
            "color": color,
            "fields": embed_fields,
            "footer": {
                "text": f"Event ID: {_discord_text(payload.event_id)} • Priority: {payload.priority.value} • Crypto Quant Monitor"
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
