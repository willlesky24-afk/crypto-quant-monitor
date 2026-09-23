from __future__ import annotations

import html
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

TELEGRAM_MAX_MESSAGE_LENGTH = 4096


class TelegramChannel(BaseNotificationChannel):
    """Notification delivery adapter for Telegram Bot API using HTML formatting."""

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
        name: str = "Telegram",
        is_enabled: bool = True,
        dry_run: bool = False,
        timeout: float = 5.0,
        max_retries: int = 3,
        base_backoff_sec: float = 1.0,
    ) -> None:
        super().__init__(
            name=name,
            channel_type=NotificationChannelType.TELEGRAM,
            is_enabled=is_enabled,
            dry_run=dry_run,
        )
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_backoff_sec = base_backoff_sec

    def format_message(self, payload: NotificationPayload) -> str:
        """Format a NotificationPayload into a structured HTML message for Telegram."""
        if payload.direction == "LONG" or payload.action == "BUY":
            icon = "🟢"
        elif payload.direction == "SHORT" or payload.action == "SELL":
            icon = "🔴"
        else:
            icon = "⏳"

        safe_symbol = html.escape(payload.symbol)
        safe_tf = html.escape(payload.timeframe.upper())
        safe_action = html.escape(payload.action)
        safe_dir = html.escape(payload.direction)
        safe_regime = html.escape(payload.regime)
        safe_reasoning = html.escape(payload.reasoning or "N/A")

        is_fx = "=X" in payload.symbol or payload.price < 10
        p_str = f"${payload.price:,.4f}" if is_fx else f"${payload.price:,.2f}"

        lines = [
            f"<b>{icon} SIGNAL ALERT: {safe_symbol} [{safe_tf}]</b>",
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"<b>Action:</b> {safe_action} ({safe_dir})",
            f"<b>Price:</b> {p_str}",
            f"<b>Market Regime:</b> <code>{safe_regime}</code>",
            f"<b>Confidence:</b> {payload.confidence * 100:.1f}%",
            f"<b>Predictive Score:</b> {payload.predictive_score:.2f}",
            f"<b>Quant Score:</b> {payload.quant_score:.1f}",
        ]

        if payload.stop_loss is not None:
            sl_str = f"${payload.stop_loss:,.4f}" if is_fx else f"${payload.stop_loss:,.2f}"
            lines.append(f"<b>🛑 Stop Loss:</b> {sl_str}")
        if payload.take_profit is not None:
            tp_str = f"${payload.take_profit:,.4f}" if is_fx else f"${payload.take_profit:,.2f}"
            lines.append(f"<b>🎯 Take Profit:</b> {tp_str}")
        if payload.risk_reward_ratio is not None:
            lines.append(f"<b>⚖️ R:R Ratio:</b> {payload.risk_reward_ratio:.2f}")

        lines.append(f"<b>🧠 Reasoning:</b> {safe_reasoning}")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"<i>Event ID: {payload.event_id} | Priority: {payload.priority.value}</i>")

        full_message = "\n".join(lines)

        # Message length protection (Telegram limit: 4096 characters)
        if len(full_message) > TELEGRAM_MAX_MESSAGE_LENGTH:
            excess = len(full_message) - TELEGRAM_MAX_MESSAGE_LENGTH + 20
            truncated_reasoning = safe_reasoning[:-excess] + " ...[truncated]"
            lines[-3] = f"<b>🧠 Reasoning:</b> {truncated_reasoning}"
            full_message = "\n".join(lines)

        return full_message

    def send(self, payload: NotificationPayload) -> NotificationResult:
        """Deliver the notification to Telegram via the Bot API."""
        if not self.validate_payload(payload):
            return NotificationResult(
                success=False,
                channel=self.channel_type,
                error_message="Payload validation failed",
                event_id=payload.event_id,
            )

        if (not self.bot_token or not self.chat_id) and not self.dry_run:
            logger.error(f"[{self.name}] Cannot send: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing.")
            return NotificationResult(
                success=False,
                channel=self.channel_type,
                error_message="TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not configured",
                event_id=payload.event_id,
            )

        api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        text_body = self.format_message(payload)
        json_data: dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": text_body,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        success, status_code, error_msg, retries, latency_ms = self.http_post_with_retry(
            url=api_url,
            json_data=json_data,
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

    def format_copilot_response(
        self,
        symbol: str,
        timeframe: str,
        answer: str,
        regime: str,
        quant_score: float,
        predictive_score: float,
    ) -> str:
        """Format an AI Copilot response for Telegram delivery."""
        safe_symbol = html.escape(symbol.upper())
        safe_tf = html.escape(timeframe.upper())
        safe_regime = html.escape(regime)
        safe_answer = html.escape(answer)

        lines = [
            f"<b>🤖 AI QUANT COPILOT: {safe_symbol} [{safe_tf}]</b>",
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"<b>Regime:</b> <code>{safe_regime}</code>",
            f"<b>Quant Score:</b> {quant_score:.1f}/100 | <b>Predictive:</b> {predictive_score:.2f}",
            "━━━━━━━━━━━━━━━━━━━━━━",
            safe_answer,
            "━━━━━━━━━━━━━━━━━━━━━━",
            "<i>Decision-support only. No automated execution.</i>",
        ]
        full_msg = "\n".join(lines)
        if len(full_msg) > TELEGRAM_MAX_MESSAGE_LENGTH:
            excess = len(full_msg) - TELEGRAM_MAX_MESSAGE_LENGTH + 20
            safe_answer = safe_answer[:-excess] + " ...[truncated]"
            lines[5] = safe_answer
            full_msg = "\n".join(lines)
        return full_msg

    def send_copilot_response(
        self,
        symbol: str,
        timeframe: str,
        answer: str,
        regime: str,
        quant_score: float,
        predictive_score: float,
    ) -> bool:
        """Deliver an AI Copilot interpretation message to Telegram."""
        if (not self.bot_token or not self.chat_id) and not self.dry_run:
            logger.error(f"[{self.name}] Cannot send: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing.")
            return False

        msg_body = self.format_copilot_response(
            symbol=symbol,
            timeframe=timeframe,
            answer=answer,
            regime=regime,
            quant_score=quant_score,
            predictive_score=predictive_score,
        )

        if self.dry_run:
            logger.info(f"[{self.name}] [DRY-RUN] Sent copilot message: {msg_body[:100]}...")
            return True

        api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        json_data: dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": msg_body,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        success, _, _, _, _ = self.http_post_with_retry(
            url=api_url,
            json_data=json_data,
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
            max_retries=self.max_retries,
            base_backoff_sec=self.base_backoff_sec,
        )
        return success

