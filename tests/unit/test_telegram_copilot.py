from __future__ import annotations

from unittest.mock import patch

from src.notifications.channels.telegram import TelegramChannel


def test_telegram_channel_format_copilot_response():
    channel = TelegramChannel(bot_token="test_token", chat_id="12345", dry_run=True)
    formatted = channel.format_copilot_response(
        symbol="BTCUSDT",
        timeframe="1h",
        answer="Price is consolidating above POC with low volatility.",
        regime="CONSOLIDATION",
        quant_score=60.0,
        predictive_score=0.55,
    )

    assert "AI QUANT COPILOT: BTCUSDT [1H]" in formatted
    assert "CONSOLIDATION" in formatted
    assert "60.0/100" in formatted
    assert "Decision-support only" in formatted


def test_telegram_channel_send_copilot_response_dry_run():
    channel = TelegramChannel(bot_token="test_token", chat_id="12345", dry_run=True)
    res = channel.send_copilot_response(
        symbol="BTCUSDT",
        timeframe="1h",
        answer="Sample analysis",
        regime="TRENDING_BULL",
        quant_score=85.0,
        predictive_score=0.80,
    )
    assert res is True


def test_telegram_channel_send_copilot_response_missing_credentials():
    channel = TelegramChannel(bot_token="", chat_id="", dry_run=False)
    res = channel.send_copilot_response(
        symbol="BTCUSDT",
        timeframe="1h",
        answer="Sample analysis",
        regime="TRENDING_BULL",
        quant_score=85.0,
        predictive_score=0.80,
    )
    assert res is False


def test_telegram_channel_send_copilot_response_live_post():
    channel = TelegramChannel(bot_token="valid_token", chat_id="valid_chat", dry_run=False)
    with patch.object(channel, "http_post_with_retry", return_value=(True, 200, None, 0, 15.0)) as mock_post:
        res = channel.send_copilot_response(
            symbol="BTCUSDT",
            timeframe="1h",
            answer="Sample live message",
            regime="TRENDING_BULL",
            quant_score=85.0,
            predictive_score=0.80,
        )
        assert res is True
        mock_post.assert_called_once()