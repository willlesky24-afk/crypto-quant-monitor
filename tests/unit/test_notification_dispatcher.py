from __future__ import annotations

import sqlite3
from dataclasses import replace
from unittest.mock import MagicMock

import pandas as pd
import pytest

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
from src.notifications.tracker import AlertOutcomeTracker


class FaultyChannel(BaseNotificationChannel):
    """Channel that deliberately raises an unexpected exception to test resilience."""

    def format_message(self, payload: NotificationPayload) -> dict:
        return {}

    def send(self, payload: NotificationPayload) -> NotificationResult:
        raise RuntimeError("Fatal hardware / unexpected library crash!")


class InspectingChannel(BaseNotificationChannel):
    """Local-only channel that verifies persistence before observing a send."""

    def __init__(self, tracker: AlertOutcomeTracker):
        super().__init__(name="Inspecting", channel_type=NotificationChannelType.LOG)
        self.tracker = tracker
        self.payloads: list[NotificationPayload] = []

    def format_message(self, payload: NotificationPayload) -> dict:
        return payload.to_dict()

    def send(self, payload: NotificationPayload) -> NotificationResult:
        record = self.tracker.get_all_alerts()[0]
        assert record["id"] == payload.event_id
        assert record["risk_integrity_status"] == "VALIDATED"
        assert record["status"] == "OPEN"
        self.payloads.append(payload)
        return NotificationResult(
            success=True, channel=self.channel_type, event_id=payload.event_id
        )


def _operational_signal() -> SignalEvent:
    return SignalEvent(
        timestamp=pd.Timestamp("2026-09-23 10:00:00", tz="UTC"),
        symbol="BTCUSDT",
        timeframe="1h",
        action="BUY",
        direction="LONG",
        confidence=0.9,
        predictive_score=0.8,
        regime="TRENDING_BULL",
        reasoning="Verified fixture",
        price=60000.0,
        stop_loss=59000.0,
        take_profit=62000.0,
        signal_id="tracked-001",
        metadata={
            "signal_status": "ACTIVADA",
            "entry_confirmed": True,
            "risk_reward_ratio": 2.0,
        },
    )


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
    payload = _create_sample_payload(action="TEST")
    results = dispatcher.dispatch(payload)
    assert results == []


def test_dispatcher_multi_channel_success_and_cooldown():
    discord = DiscordWebhookChannel(name="Discord", dry_run=True)
    telegram = TelegramChannel(name="Telegram", dry_run=True)
    dispatcher = NotificationDispatcher(
        channels=[discord, telegram], cooldown_seconds=60.0
    )

    payload = _create_sample_payload(
        action="TEST", predictive_score=0.85, confidence=0.90
    )

    # 1. First dispatch succeeds on both channels
    results = dispatcher.dispatch(payload)
    assert len(results) == 2
    assert all(r.success for r in results)
    channel_types = {r.channel for r in results}
    assert channel_types == {
        NotificationChannelType.DISCORD,
        NotificationChannelType.TELEGRAM,
    }

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

    # An informational event establishes cooldown.
    payload_info = _create_sample_payload(action="TEST")
    res1 = dispatcher.dispatch(payload_info)
    assert res1[0].success is True

    # Immediate CRITICAL alert for same action bypasses cooldown
    payload_crit = _create_sample_payload(
        action="TEST",
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
    payload_wait = _create_sample_payload(
        action="WAIT", predictive_score=0.80, confidence=0.80
    )
    res_wait = dispatcher.dispatch(payload_wait)
    assert res_wait[0].success is False
    assert "configured to be ignored" in str(res_wait[0].error_message)

    # 2. Low predictive score
    payload_low_score = _create_sample_payload(
        action="TEST", predictive_score=0.55, confidence=0.80
    )
    res_low_score = dispatcher.dispatch(payload_low_score)
    assert res_low_score[0].success is False
    assert "predictive score" in str(res_low_score[0].error_message).lower()

    # 3. Low confidence
    payload_low_conf = _create_sample_payload(
        action="TEST", predictive_score=0.80, confidence=0.50
    )
    res_low_conf = dispatcher.dispatch(payload_low_conf)
    assert res_low_conf[0].success is False
    assert "confidence" in str(res_low_conf[0].error_message).lower()


def test_direct_operational_dispatch_is_blocked_without_tracking():
    discord = DiscordWebhookChannel(name="Discord", dry_run=True)
    discord.send = MagicMock()
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
        stop_loss=3350.0,
        take_profit=3800.0,
        metadata={"signal_status": "ACTIVADA", "entry_confirmed": True},
    )

    results = dispatcher.dispatch_signal(signal, custom_summary="Custom ETH Alert")
    assert len(results) == 1
    assert results[0].success is False
    assert "dispatch_tracked_signal" in results[0].error_message
    discord.send.assert_not_called()


@pytest.mark.parametrize("action,direction", [("BUY", "LONG"), ("SELL", "SHORT")])
def test_generic_dispatch_rejects_operational_payload_even_with_forged_tracking(
    action, direction
):
    channel = DiscordWebhookChannel(name="Discord", dry_run=True)
    channel.send = MagicMock()
    dispatcher = NotificationDispatcher(channels=[channel])
    payload = replace(
        _create_sample_payload(action=action, direction=direction),
        metadata={
            "tracking_id": "forged-id",
            "tracking_recorded_at": "2026-09-23T10:00:00+00:00",
            "tracking_status": "OPEN",
            "signal_status": "ACTIVADA",
            "entry_confirmed": True,
        },
    )

    results = dispatcher.dispatch(payload)

    assert len(results) == 1 and not results[0].success
    assert "dispatch_tracked_signal" in results[0].error_message
    channel.send.assert_not_called()


def test_async_generic_dispatch_cannot_bypass_registration():
    channel = DiscordWebhookChannel(name="Discord", dry_run=True)
    channel.send = MagicMock()
    dispatcher = NotificationDispatcher(channels=[channel])
    try:
        result = dispatcher.dispatch_async(_create_sample_payload()).result(timeout=2.0)
    finally:
        dispatcher.close()

    assert len(result) == 1 and not result[0].success
    assert "dispatch_tracked_signal" in result[0].error_message
    channel.send.assert_not_called()


def test_non_operational_test_ping_remains_available():
    discord = DiscordWebhookChannel(name="Discord", dry_run=True)
    dispatcher = NotificationDispatcher(channels=[discord])
    signal = replace(
        _operational_signal(),
        action="TEST",
        direction="SIN OPERACIÓN",
        stop_loss=None,
        take_profit=None,
        metadata={},
    )
    results = dispatcher.dispatch_signal(signal, priority=NotificationPriority.HIGH)
    assert len(results) == 1
    assert results[0].success is True


def test_operational_alert_is_registered_before_channel_send(tmp_path):
    tracker = AlertOutcomeTracker(db_path=tmp_path / "alerts.db")
    channel = InspectingChannel(tracker)
    dispatcher = NotificationDispatcher(channels=[channel])
    signal = _operational_signal()

    record, results = dispatcher.dispatch_tracked_signal(
        signal, tracker, risk_reward=2.0, priority=NotificationPriority.HIGH
    )

    assert record is not None
    assert record["id"] == signal.signal_id
    assert record["risk_integrity_status"] == "VALIDATED"
    assert len(results) == 1 and results[0].success
    payload = channel.payloads[0]
    assert payload.event_id == record["id"]
    assert payload.timestamp == signal.timestamp
    assert payload.symbol == record["symbol"]
    assert payload.direction == record["direction"]
    assert payload.price == record["entry_price"]
    assert payload.stop_loss == record["stop_loss"]
    assert payload.take_profit == record["take_profit"]
    assert payload.risk_reward_ratio == record["risk_reward"]
    assert payload.metadata["signal_status"] == "ACTIVADA"
    assert payload.metadata["tracking_id"] == record["id"]
    assert payload.metadata["tracking_recorded_at"] == record["risk_recorded_at"]
    assert payload.metadata["tracking_status"] == record["status"]


def test_duplicate_id_with_different_plan_cannot_dispatch(tmp_path):
    tracker = AlertOutcomeTracker(db_path=tmp_path / "alerts.db")
    original = _operational_signal()
    tracker.record_alert(original, risk_reward=2.0)
    channel = InspectingChannel(tracker)
    dispatcher = NotificationDispatcher(channels=[channel])
    changed = replace(original, stop_loss=59500.0, take_profit=61000.0)

    with pytest.raises(ValueError, match="registro operativo validado"):
        dispatcher.dispatch_tracked_signal(changed, tracker, risk_reward=2.0)

    assert channel.payloads == []
    assert tracker.get_all_alerts()[0]["stop_loss"] == original.stop_loss


def test_all_channels_fail_but_tracking_status_remains_open(tmp_path):
    tracker = AlertOutcomeTracker(db_path=tmp_path / "alerts.db")
    discord = DiscordWebhookChannel(name="Discord", dry_run=True)
    discord.send = MagicMock(
        return_value=NotificationResult(
            success=False,
            channel=NotificationChannelType.DISCORD,
            error_message="mocked Discord failure",
            event_id="tracked-001",
        )
    )
    telegram = TelegramChannel(name="Telegram", dry_run=True)
    telegram.send = MagicMock(
        return_value=NotificationResult(
            success=False,
            channel=NotificationChannelType.TELEGRAM,
            error_message="mocked Telegram failure",
            event_id="tracked-001",
        )
    )
    dispatcher = NotificationDispatcher(channels=[discord, telegram])

    record, results = dispatcher.dispatch_tracked_signal(
        _operational_signal(), tracker, risk_reward=2.0
    )

    assert record is not None and record["status"] == "OPEN"
    assert tracker.get_all_alerts()[0]["status"] == "OPEN"
    assert len(results) == 2 and all(result.success is False for result in results)
    assert {result.channel for result in results} == {
        NotificationChannelType.DISCORD,
        NotificationChannelType.TELEGRAM,
    }
    discord.send.assert_called_once()
    telegram.send.assert_called_once()


def test_tracker_rejection_prevents_operational_send(tmp_path):
    tracker = AlertOutcomeTracker(db_path=tmp_path / "alerts.db")
    channel = InspectingChannel(tracker)
    dispatcher = NotificationDispatcher(channels=[channel])

    with pytest.raises(ValueError, match="R reportado no coincide"):
        dispatcher.dispatch_tracked_signal(
            _operational_signal(), tracker, risk_reward=3.0
        )

    assert channel.payloads == []
    assert tracker.get_all_alerts() == []


@pytest.mark.parametrize(
    "action,status,confirmed",
    [("WAIT", "CANDIDATA", False), ("BUY", "CANDIDATA", False)],
)
def test_informational_event_does_not_dispatch_or_register(
    tmp_path, action, status, confirmed
):
    tracker = AlertOutcomeTracker(db_path=tmp_path / "alerts.db")
    channel = InspectingChannel(tracker)
    dispatcher = NotificationDispatcher(channels=[channel])
    signal = replace(
        _operational_signal(),
        action=action,
        metadata={"signal_status": status, "entry_confirmed": confirmed},
    )

    record, results = dispatcher.dispatch_tracked_signal(
        signal, tracker, risk_reward=2.0
    )

    assert record is None and results == []
    assert channel.payloads == []
    assert tracker.get_all_alerts() == []


def test_persistence_error_prevents_operational_send(tmp_path):
    tracker = AlertOutcomeTracker(db_path=tmp_path / "alerts.db")
    channel = InspectingChannel(tracker)
    dispatcher = NotificationDispatcher(channels=[channel])
    failing_tracker = MagicMock()
    failing_tracker.record_alert.side_effect = sqlite3.OperationalError(
        "database is locked"
    )

    with pytest.raises(sqlite3.OperationalError, match="database is locked"):
        dispatcher.dispatch_tracked_signal(
            _operational_signal(), failing_tracker, risk_reward=2.0
        )

    assert channel.payloads == []
    assert tracker.get_all_alerts() == []


def test_dispatcher_fault_isolation_unexpected_exception():
    faulty = FaultyChannel(
        name="CrashingChannel", channel_type=NotificationChannelType.LOG
    )
    healthy = DiscordWebhookChannel(name="DiscordHealthy", dry_run=True)
    dispatcher = NotificationDispatcher(channels=[faulty, healthy])

    payload = _create_sample_payload(action="TEST", symbol="SOLUSDT")
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

    payload = _create_sample_payload(action="TEST", symbol="ADAUSDT")
    future = dispatcher.dispatch_async(payload)

    # Wait for future completion
    results = future.result(timeout=2.0)
    assert len(results) == 1
    assert results[0].success is True

    dispatcher.close()
    assert dispatcher._executor is None
