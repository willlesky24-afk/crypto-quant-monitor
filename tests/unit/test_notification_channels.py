from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import requests

from src.notifications.channels.discord import (
    COLOR_LONG,
    COLOR_NEUTRAL,
    COLOR_SHORT,
    DiscordWebhookChannel,
)
from src.notifications.channels.telegram import (
    TELEGRAM_MAX_MESSAGE_LENGTH,
    TelegramChannel,
)
from src.notifications.channels.webhook import WebhookChannel
from src.notifications.models import (
    NotificationChannelType,
    NotificationPayload,
    NotificationPriority,
)


def _build_test_payload(
    action: str = "BUY",
    direction: str = "LONG",
    price: float = 65000.0,
    stop_loss: float | None = 63500.0,
    take_profit: float | None = 68000.0,
    risk_reward_ratio: float | None = 2.0,
    reasoning: str = "Momentum breakout confirmed",
) -> NotificationPayload:
    return NotificationPayload(
        event_id="sig-test-01",
        timestamp=pd.Timestamp.now("UTC"),
        symbol="BTCUSDT",
        timeframe="1h",
        action=action,
        direction=direction,
        price=price,
        confidence=0.85,
        predictive_score=0.78,
        regime="TRENDING_BULL",
        priority=NotificationPriority.HIGH,
        summary=f"[BTCUSDT 1h] {action} ({direction}) @ {price:.2f}",
        reasoning=reasoning,
        quant_score=82.0,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward_ratio=risk_reward_ratio,
        metadata={"volume_spike": True},
    )


# =====================================================================
# 1. DISCORD ADAPTER TESTS
# =====================================================================

def test_discord_formatting_colors_and_fields():
    channel = DiscordWebhookChannel(webhook_url="https://discord.com/api/webhooks/test", dry_run=True)

    # LONG format (Green)
    long_payload = _build_test_payload(action="BUY", direction="LONG")
    long_embed = channel.format_message(long_payload)["embeds"][0]
    assert long_embed["color"] == COLOR_LONG
    assert "🟢" in long_embed["title"]
    field_names = [f["name"] for f in long_embed["fields"]]
    assert "Action / Direction" in field_names
    assert "Stop Loss" in field_names
    assert "Take Profit" in field_names
    assert "R:R Ratio" in field_names

    # SHORT format (Red)
    short_payload = _build_test_payload(action="SELL", direction="SHORT", stop_loss=66500.0, take_profit=62000.0)
    short_embed = channel.format_message(short_payload)["embeds"][0]
    assert short_embed["color"] == COLOR_SHORT
    assert "🔴" in short_embed["title"]

    # WAIT format (Blue/Neutral) without SL/TP
    wait_payload = _build_test_payload(
        action="WAIT",
        direction="NEUTRAL",
        stop_loss=None,
        take_profit=None,
        risk_reward_ratio=None,
        reasoning="",
    )
    wait_embed = channel.format_message(wait_payload)["embeds"][0]
    assert wait_embed["color"] == COLOR_NEUTRAL
    assert "⏳" in wait_embed["title"]
    wait_field_names = [f["name"] for f in wait_embed["fields"]]
    assert "Stop Loss" not in wait_field_names


@patch("requests.post")
def test_discord_send_success_and_failure(mock_post):
    channel = DiscordWebhookChannel(webhook_url="https://discord.com/api/webhooks/test", base_backoff_sec=0.001)
    payload = _build_test_payload()

    # Success 204
    mock_resp_success = MagicMock()
    mock_resp_success.status_code = 204
    mock_post.return_value = mock_resp_success

    res = channel.send(payload)
    assert res.success is True
    assert res.status_code == 204
    assert res.channel == NotificationChannelType.DISCORD
    assert res.latency_ms > 0
    assert res.delivered_at is not None

    # Failure 400 (Bad Request - non retryable)
    mock_resp_err = MagicMock()
    mock_resp_err.status_code = 400
    mock_resp_err.text = "Bad Request"
    mock_post.return_value = mock_resp_err

    res_err = channel.send(payload)
    assert res_err.success is False
    assert res_err.status_code == 400
    assert "HTTP 400" in str(res_err.error_message)


def test_discord_missing_url_and_dry_run():
    # Missing URL when dry_run=False
    channel_no_url = DiscordWebhookChannel(webhook_url="", dry_run=False)
    res_no_url = channel_no_url.send(_build_test_payload())
    assert res_no_url.success is False
    assert "DISCORD_WEBHOOK_URL is not configured" in str(res_no_url.error_message)

    # Dry run mode
    channel_dry = DiscordWebhookChannel(webhook_url="", dry_run=True)
    res_dry = channel_dry.send(_build_test_payload())
    assert res_dry.success is True
    assert res_dry.status_code == 200

    # Invalid payload
    invalid_payload = _build_test_payload(price=-10.0)
    res_inv = channel_dry.send(invalid_payload)
    assert res_inv.success is False
    assert "validation failed" in str(res_inv.error_message).lower()


# =====================================================================
# 2. TELEGRAM ADAPTER TESTS
# =====================================================================

def test_telegram_formatting_and_length_protection():
    channel = TelegramChannel(bot_token="dummy_token", chat_id="12345", dry_run=True)

    payload_long = _build_test_payload(action="BUY", direction="LONG")
    msg_long = channel.format_message(payload_long)
    assert "🟢 SIGNAL ALERT: BTCUSDT [1H]" in msg_long
    assert "<b>Action:</b> BUY (LONG)" in msg_long
    assert "<b>🛑 Stop Loss:</b>" in msg_long
    assert "<b>🎯 Take Profit:</b>" in msg_long
    assert "<b>⚖️ R:R Ratio:</b> 2.00" in msg_long

    payload_short = _build_test_payload(action="SELL", direction="SHORT")
    msg_short = channel.format_message(payload_short)
    assert "🔴 SIGNAL ALERT: BTCUSDT [1H]" in msg_short

    payload_wait = _build_test_payload(action="WAIT", direction="NEUTRAL", stop_loss=None, take_profit=None, risk_reward_ratio=None)
    msg_wait = channel.format_message(payload_wait)
    assert "⏳ SIGNAL ALERT: BTCUSDT [1H]" in msg_wait

    # Test extreme length protection (> 4096 chars)
    giant_reasoning = "A" * 5000
    payload_giant = _build_test_payload(reasoning=giant_reasoning)
    msg_giant = channel.format_message(payload_giant)
    assert len(msg_giant) <= TELEGRAM_MAX_MESSAGE_LENGTH
    assert "[truncated]" in msg_giant


@patch("requests.post")
def test_telegram_send_success_and_failure(mock_post):
    channel = TelegramChannel(bot_token="dummy_token", chat_id="12345", base_backoff_sec=0.001)
    payload = _build_test_payload()

    # Success 200
    mock_resp_success = MagicMock()
    mock_resp_success.status_code = 200
    mock_resp_success.json.return_value = {"ok": True}
    mock_post.return_value = mock_resp_success

    res = channel.send(payload)
    assert res.success is True
    assert res.status_code == 200
    assert res.channel == NotificationChannelType.TELEGRAM

    # Failure 401 Unauthorized
    mock_resp_err = MagicMock()
    mock_resp_err.status_code = 401
    mock_resp_err.text = "Unauthorized"
    mock_post.return_value = mock_resp_err

    res_err = channel.send(payload)
    assert res_err.success is False
    assert res_err.status_code == 401


def test_telegram_missing_credentials_and_dry_run():
    # Missing credentials
    channel_no_creds = TelegramChannel(bot_token="", chat_id="", dry_run=False)
    res = channel_no_creds.send(_build_test_payload())
    assert res.success is False
    assert "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not configured" in str(res.error_message)

    # Dry run
    channel_dry = TelegramChannel(bot_token="", chat_id="", dry_run=True)
    res_dry = channel_dry.send(_build_test_payload())
    assert res_dry.success is True

    # Invalid payload
    res_inv = channel_dry.send(_build_test_payload(price=0.0))
    assert res_inv.success is False


# =====================================================================
# 3. GENERIC WEBHOOK ADAPTER TESTS
# =====================================================================

@patch("requests.post")
def test_webhook_send_and_custom_headers(mock_post):
    headers = {"Authorization": "Bearer secret_api_key", "X-Custom": "test"}
    channel = WebhookChannel(url="https://api.example.com/alerts", headers=headers, base_backoff_sec=0.001)
    payload = _build_test_payload()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp

    res = channel.send(payload)
    assert res.success is True
    assert res.channel == NotificationChannelType.WEBHOOK

    # Check mock called with custom headers and dictionary payload
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args[1]
    assert call_kwargs["headers"] == headers
    assert call_kwargs["json"]["symbol"] == "BTCUSDT"


def test_webhook_missing_url_and_dry_run():
    channel = WebhookChannel(url="", dry_run=False)
    res = channel.send(_build_test_payload())
    assert res.success is False
    assert "Webhook target URL is not configured" in str(res.error_message)

    channel_dry = WebhookChannel(url="", dry_run=True)
    assert channel_dry.send(_build_test_payload()).success is True

    invalid_payload = _build_test_payload(price=-5.0)
    assert channel_dry.send(invalid_payload).success is False


# =====================================================================
# 4. RETRY SYSTEM TESTS (HTTP 429, 5xx, Network Timeout)
# =====================================================================

@patch("requests.post")
def test_retry_on_429_then_success(mock_post):
    channel = DiscordWebhookChannel(webhook_url="https://discord.com/api/webhooks/test", max_retries=3, base_backoff_sec=0.001)
    payload = _build_test_payload()

    resp_429 = MagicMock(status_code=429, text="Rate Limited")
    resp_200 = MagicMock(status_code=200, text="OK")
    mock_post.side_effect = [resp_429, resp_429, resp_200]

    res = channel.send(payload)
    assert res.success is True
    assert res.status_code == 200
    assert res.retry_count == 2
    assert mock_post.call_count == 3


@patch("requests.post")
def test_retry_on_503_exceeds_max_retries(mock_post):
    channel = WebhookChannel(url="https://api.example.com/alerts", max_retries=2, base_backoff_sec=0.001)
    payload = _build_test_payload()

    resp_503 = MagicMock(status_code=503, text="Service Unavailable")
    mock_post.return_value = resp_503

    res = channel.send(payload)
    assert res.success is False
    assert res.status_code == 503
    assert res.retry_count == 2
    assert mock_post.call_count == 3  # Initial + 2 retries


@patch("requests.post")
def test_retry_on_network_timeout_then_success(mock_post):
    channel = TelegramChannel(bot_token="tok", chat_id="123", max_retries=2, base_backoff_sec=0.001)
    payload = _build_test_payload()

    resp_200 = MagicMock(status_code=200, text="OK")
    mock_post.side_effect = [requests.exceptions.Timeout("Connection timed out"), resp_200]

    res = channel.send(payload)
    assert res.success is True
    assert res.retry_count == 1
    assert mock_post.call_count == 2


@patch("requests.post")
def test_network_exception_exceeds_retries(mock_post):
    channel = WebhookChannel(url="https://api.example.com/alerts", max_retries=1, base_backoff_sec=0.001)
    payload = _build_test_payload()

    mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

    res = channel.send(payload)
    assert res.success is False
    assert res.retry_count == 1
    assert "ConnectionError" in str(res.error_message)


def test_channel_disabled_returns_error_immediately():
    channel = DiscordWebhookChannel(webhook_url="https://discord.com/api/test", is_enabled=False)
    payload = _build_test_payload()

    res = channel.send(payload)
    assert res.success is False
    assert "disabled" in str(res.error_message).lower()


# =====================================================================
# 5. CHANNEL ISOLATION TESTS
# =====================================================================

@patch("requests.post")
def test_channel_isolation_one_fails_others_succeed(mock_post):
    """Demonstrates that a failure in Telegram does not stop Discord or Webhook."""
    discord = DiscordWebhookChannel(webhook_url="https://discord.com/api/webhooks/test", base_backoff_sec=0.001)
    telegram = TelegramChannel(bot_token="bad_token", chat_id="123", base_backoff_sec=0.001)
    webhook = WebhookChannel(url="https://api.example.com/alerts", base_backoff_sec=0.001)

    payload = _build_test_payload()

    def mock_post_by_url(url, *args, **kwargs):
        resp = MagicMock()
        if "telegram" in url:
            resp.status_code = 500
            resp.text = "Internal Server Error"
        else:
            resp.status_code = 200
            resp.text = "Success"
        return resp

    mock_post.side_effect = mock_post_by_url

    res_discord = discord.send(payload)
    res_telegram = telegram.send(payload)
    res_webhook = webhook.send(payload)

    # Discord succeeds
    assert res_discord.success is True
    assert res_discord.channel == NotificationChannelType.DISCORD

    # Telegram fails
    assert res_telegram.success is False
    assert res_telegram.status_code == 500
    assert res_telegram.channel == NotificationChannelType.TELEGRAM

    # Webhook still succeeds
    assert res_webhook.success is True
    assert res_webhook.channel == NotificationChannelType.WEBHOOK


def test_channel_negative_max_retries():
    channel = DiscordWebhookChannel(webhook_url="https://discord.com/api/webhooks/test", max_retries=-1)
    payload = _build_test_payload()
    res = channel.send(payload)
    assert res.success is False
    assert "Max retries exceeded" in str(res.error_message)

