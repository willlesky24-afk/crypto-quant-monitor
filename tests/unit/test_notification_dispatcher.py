from __future__ import annotations

import pandas as pd

from src.notifications.channels.base import BaseNotificationChannel
from src.notifications.channels.discord import DiscordWebhookChannel
from src.notifications.channels.telegram import TelegramChannel
from src.notifications.dispatcher import CooldownManager, NotificationDispatcher
from src.notifications.models import (
    NotificationChannelType,
    NotificationPayload,
    NotificationPriority,
    NotificationResult,
    SignalEvent,
)


class FaultyChannel(BaseNotificationChannel):
    """Channel that deliberately raises an unexpected exception to test resilience."""

    def format_message(self, payload: NotificationPayload) -> dict:
        return {}

    def send(self, payload: NotificationPayload) -> NotificationResult:
        raise RuntimeError("Fatal hardware / unexpected library crash!")


def _create_sample_payload(
    action: str = "BUY",
    direction: str = "LONG",
    predictive_score: float = 0.75,
    confidence: float = 0.80,
    priority: NotificationPriority = NotificationPriority.NORMAL,
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
) -> NotificationPayload:
    return NotificationPayload(
        event_id="test-event-01",
        timestamp=pd.Timestamp.now("UTC"),
        symbol=symbol,
        timeframe=timeframe,
        action=action,
        direction=direction,
        price=65000.0,
        confidence=confidence,
        predictive_score=predictive_score,
        regime="TRENDING_BULL",
        priority=priority,
        summary=f"[{symbol} {timeframe}] {action} @ 65000",
        reasoning="Test reasoning",
        quant_score=80.0,
    )


# =====================================================================
# 1. COOLDOWN MANAGER TESTS
# =====================================================================

def test_cooldown_manager_flow():
    cm = CooldownManager(default_cooldown_seconds=10.0)

    # 1. Initially not on cooldown
    assert cm.is_in_cooldown("BTCUSDT", "1h", "BUY") is False

    # 2. Record dispatch at T0
    t0 = pd.Timestamp("2026-03-15 12:00:00", tz="UTC")
    cm.record_dispatch("BTCUSDT", "1h", "BUY", now=t0)

    # 3. Same time or within 10s -> in cooldown
    t1 = pd.Timestamp("2026-03-15 12:00:05", tz="UTC")
    assert cm.is_in_cooldown("BTCUSDT", "1h", "BUY", now=t1) is True
    # Different action -> not in cooldown
    assert cm.is_in_cooldown("BTCUSDT", "1h", "SELL", now=t1) is False
    # Different timeframe -> not in cooldown
    assert cm.is_in_cooldown("BTCUSDT", "4h", "BUY", now=t1) is False
    # Case insensitivity
    assert cm.is_in_cooldown("btcusdt", "1H", "buy", now=t1) is True

    # 4. After 15s -> cooldown expired
    t2 = pd.Timestamp("2026-03-15 12:00:15", tz="UTC")
    assert cm.is_in_cooldown("BTCUSDT", "1h", "BUY", now=t2) is False

    # 5. Reset clears history
    cm.record_dispatch("BTCUSDT", "1h", "BUY", now=t2)
    assert cm.is_in_cooldown("BTCUSDT", "1h", "BUY", now=t2) is True
    cm.reset()
    assert cm.is_in_cooldown("BTCUSDT", "1h", "BUY", now=t2) is False


# =====================================================================
# 2. NOTIFICATION DISPATCHER TESTS
# =====================================================================

def test_dispatcher_channel_registration():
    dispatcher = NotificationDispatcher()
    discord = DiscordWebhookChannel(name="Discord1", dry_run=True)
    telegram = TelegramChannel(name="Telegram1", dry_run=True)

    dispatcher.register_channel(discord)
    dispatcher.register_channel(telegram)
    assert len(dispatcher.channels) == 2

    # Re-registering with same name updates existing
    discord_updated = DiscordWebhookChannel(name="Discord1", dry_run=True)
    dispatcher.register_channel(discord_updated)
    assert len(dispatcher.channels) == 2

    # Unregister channel
    assert dispatcher.unregister_channel("Telegram1") is True
    assert len(dispatcher.channels) == 1
    assert dispatcher.unregister_channel("NonExistent") is False


def test_dispatcher_empty_channels():
    dispatcher = NotificationDispatcher(channels=[])
    payload = _create_sample_payload()
    results = dispatcher.dispatch(payload)
    assert results == []


def test_dispatcher_multi_channel_success_and_cooldown():
    discord = DiscordWebhookChannel(name="Discord", dry_run=True)
    telegram = TelegramChannel(name="Telegram", dry_run=True)
    dispatcher = NotificationDispatcher(channels=[discord, telegram], cooldown_seconds=60.0)

    payload = _create_sample_payload(action="BUY", predictive_score=0.85, confidence=0.90)

    # 1. First dispatch succeeds on both channels
    results = dispatcher.dispatch(payload)
    assert len(results) == 2
    assert all(r.success for r in results)
    channel_types = {r.channel for r in results}
    assert channel_types == {NotificationChannelType.DISCORD, NotificationChannelType.TELEGRAM}

    # 2. Immediate second dispatch is suppressed due to cooldown
    results_cooldown = dispatcher.dispatch(payload)
    assert len(results_cooldown) == 1
    assert results_cooldown[0].success is False
    assert "cooldown" in str(results_cooldown[0].error_message).lower()


def test_dispatcher_critical_priority_bypasses_cooldown_and_ignore():
    discord = DiscordWebhookChannel(name="Discord", dry_run=True)
    dispatcher = NotificationDispatcher(
        channels=[discord],
        cooldown_seconds=60.0,
        ignore_actions={"WAIT"},
        allow_critical_bypass=True,
    )

    # Normal BUY establishes cooldown
    payload_buy = _create_sample_payload(action="BUY")
    res1 = dispatcher.dispatch(payload_buy)
    assert res1[0].success is True

    # Immediate CRITICAL alert for same action bypasses cooldown
    payload_crit = _create_sample_payload(
        action="BUY",
        priority=NotificationPriority.CRITICAL,
    )
    res_crit = dispatcher.dispatch(payload_crit)
    assert res_crit[0].success is True

    # CRITICAL alert for WAIT action bypasses ignore_actions
    payload_crit_wait = _create_sample_payload(
        action="WAIT",
        priority=NotificationPriority.CRITICAL,
    )
    res_crit_wait = dispatcher.dispatch(payload_crit_wait)
    assert res_crit_wait[0].success is True


def test_dispatcher_filtering_by_thresholds_and_ignored_actions():
    discord = DiscordWebhookChannel(name="Discord", dry_run=True)
    dispatcher = NotificationDispatcher(
        channels=[discord],
        min_predictive_score=0.70,
        min_confidence=0.75,
        ignore_actions={"WAIT"},
    )

    # 1. Ignored action (WAIT)
    payload_wait = _create_sample_payload(action="WAIT", predictive_score=0.80, confidence=0.80)
    res_wait = dispatcher.dispatch(payload_wait)
    assert res_wait[0].success is False
    assert "configured to be ignored" in str(res_wait[0].error_message)

    # 2. Low predictive score
    payload_low_score = _create_sample_payload(action="BUY", predictive_score=0.55, confidence=0.80)
    res_low_score = dispatcher.dispatch(payload_low_score)
    assert res_low_score[0].success is False
    assert "predictive score" in str(res_low_score[0].error_message).lower()

    # 3. Low confidence
    payload_low_conf = _create_sample_payload(action="BUY", predictive_score=0.80, confidence=0.50)
    res_low_conf = dispatcher.dispatch(payload_low_conf)
    assert res_low_conf[0].success is False
    assert "confidence" in str(res_low_conf[0].error_message).lower()


def test_dispatcher_dispatch_signal_convenience():
    discord = DiscordWebhookChannel(name="Discord", dry_run=True)
    dispatcher = NotificationDispatcher(channels=[discord])

    signal = SignalEvent(
        timestamp=pd.Timestamp.now("UTC"),
        symbol="ETHUSDT",
        timeframe="4h",
        action="BUY",
        direction="LONG",
        confidence=0.85,
        predictive_score=0.80,
        regime="TRENDING_BULL",
        reasoning="Multi-layer confirmation",
        price=3500.0,
    )

    results = dispatcher.dispatch_signal(signal, custom_summary="Custom ETH Alert")
    assert len(results) == 1
    assert results[0].success is True


def test_dispatcher_fault_isolation_unexpected_exception():
    faulty = FaultyChannel(name="CrashingChannel", channel_type=NotificationChannelType.LOG)
    healthy = DiscordWebhookChannel(name="DiscordHealthy", dry_run=True)
    dispatcher = NotificationDispatcher(channels=[faulty, healthy])

    payload = _create_sample_payload(symbol="SOLUSDT")
    results = dispatcher.dispatch(payload)

    assert len(results) == 2
    # Faulty channel result is caught and recorded as failure
    assert results[0].success is False
    assert "Unhandled exception" in str(results[0].error_message)

    # Healthy channel succeeded without being impacted
    assert results[1].success is True
    assert results[1].channel == NotificationChannelType.DISCORD


def test_dispatcher_async_dispatch_and_close():
    discord = DiscordWebhookChannel(name="Discord", dry_run=True)
    dispatcher = NotificationDispatcher(channels=[discord], max_workers=2)

    payload = _create_sample_payload(symbol="ADAUSDT")
    future = dispatcher.dispatch_async(payload)

    # Wait for future completion
    results = future.result(timeout=2.0)
    assert len(results) == 1
    assert results[0].success is True

    dispatcher.close()
    assert dispatcher._executor is None
