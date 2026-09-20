import json
from dataclasses import FrozenInstanceError
from typing import Any

import pandas as pd
import pytest

from src.decision_engine import DecisionResult
from src.notifications.channels.base import BaseNotificationChannel
from src.notifications.models import (
    NotificationChannelType,
    NotificationPayload,
    NotificationPriority,
    NotificationResult,
    SignalEvent,
)


class DummyChannel(BaseNotificationChannel):
    """Concrete implementation of BaseNotificationChannel for testing."""

    def format_message(self, payload: NotificationPayload) -> dict[str, Any]:
        return {"text": payload.summary}

    def send(self, payload: NotificationPayload) -> NotificationResult:
        if not self.validate_payload(payload):
            return NotificationResult(
                success=False,
                channel=self.channel_type,
                error_message="Validation failed",
                event_id=payload.event_id,
            )
        return NotificationResult(
            success=True,
            channel=self.channel_type,
            status_code=200,
            delivered_at=pd.Timestamp.now("UTC"),
            event_id=payload.event_id,
        )


def test_signal_event_creation_and_immutability():
    ts = pd.Timestamp("2026-03-15 12:00:00")
    event = SignalEvent(
        timestamp=ts,
        symbol="BTCUSDT",
        timeframe="1h",
        action="BUY",
        direction="LONG",
        confidence=0.85,
        predictive_score=0.78,
        regime="TRENDING_BULL",
        reasoning="Strong momentum above EMA 200 with VP support",
        price=65000.0,
        quant_score=82.0,
        stop_loss=63500.0,
        take_profit=68000.0,
        signal_id="sig-test-01",
        metadata={"source": "test"},
    )

    assert event.symbol == "BTCUSDT"
    assert event.timeframe == "1h"
    assert event.action == "BUY"
    assert event.direction == "LONG"
    assert event.confidence == 0.85
    assert event.predictive_score == 0.78
    assert event.regime == "TRENDING_BULL"
    assert event.price == 65000.0
    assert event.stop_loss == 63500.0
    assert event.take_profit == 68000.0
    assert event.signal_id == "sig-test-01"
    assert event.metadata["source"] == "test"

    # Verify frozen immutability
    with pytest.raises(FrozenInstanceError):
        event.price = 70000.0  # type: ignore

    # Verify dictionary and JSON serialization
    d = event.to_dict()
    assert d["symbol"] == "BTCUSDT"
    assert d["timestamp"] == "2026-03-15 12:00:00"
    json_str = json.dumps(d)
    assert "BTCUSDT" in json_str


def test_signal_event_from_decision():
    ts = pd.Timestamp("2026-03-15 12:00:00")
    candle = {"timestamp": ts, "close": 65000.0}

    decision = DecisionResult(
        decision="BUY",
        confidence=0.82,
        positives=["Trend aligned", "High volume"],
        warnings=[],
        market_state="Bullish",
        signal="ENTRY",
        technical_score=80.0,
        predictive_score=0.75,
        regime="TRENDING_BULL",
        reasoning="Multi-layer confirmation",
        direction="LONG",
    )

    event = SignalEvent.from_decision(
        decision_result=decision,
        candle=candle,
        symbol="btcusdt",
        timeframe="1H",
        stop_loss=63500.0,
        take_profit=68000.0,
    )

    assert event.symbol == "BTCUSDT"
    assert event.timeframe == "1h"
    assert event.action == "BUY"
    assert event.direction == "LONG"
    assert event.confidence == 0.82
    assert event.predictive_score == 0.75
    assert event.quant_score == 80.0
    assert event.price == 65000.0
    assert event.stop_loss == 63500.0
    assert event.take_profit == 68000.0
    assert "positives" in event.metadata


def test_notification_payload_from_signal_event():
    ts = pd.Timestamp("2026-03-15 12:00:00")
    event = SignalEvent(
        timestamp=ts,
        symbol="ETHUSDT",
        timeframe="4h",
        action="BUY",
        direction="LONG",
        confidence=0.88,
        predictive_score=0.80,
        regime="TRENDING_BULL",
        reasoning="Breakout confirmed",
        price=3500.0,
        quant_score=85.0,
        stop_loss=3350.0,  # Risk = 150
        take_profit=3800.0,  # Reward = 300 -> R:R = 2.0
        signal_id="sig-eth-01",
    )

    payload = NotificationPayload.from_signal_event(event)

    assert payload.event_id == "sig-eth-01"
    assert payload.symbol == "ETHUSDT"
    assert payload.timeframe == "4h"
    assert payload.action == "BUY"
    assert payload.priority == NotificationPriority.HIGH  # confidence >= 0.75
    assert payload.risk_reward_ratio == 2.0
    assert "[ETHUSDT 4h] BUY (LONG) @ 3500.00" in payload.summary

    # Verify frozen immutability
    with pytest.raises(FrozenInstanceError):
        payload.price = 3600.0  # type: ignore

    # Verify to_dict and JSON serialization
    p_dict = payload.to_dict()
    assert p_dict["priority"] == "HIGH"
    assert p_dict["risk_reward_ratio"] == 2.0
    json_str = json.dumps(p_dict)
    assert "ETHUSDT" in json_str


def test_notification_payload_priority_and_neutral():
    ts = pd.Timestamp("2026-03-15 12:00:00")
    event_wait = SignalEvent(
        timestamp=ts,
        symbol="SOLUSDT",
        timeframe="1h",
        action="WAIT",
        direction="NEUTRAL",
        confidence=0.45,
        predictive_score=0.50,
        regime="RANGING_CONSOLIDATION",
        reasoning="Market ranging inside value area",
        price=145.0,
    )

    payload_wait = NotificationPayload.from_signal_event(event_wait)
    assert payload_wait.priority == NotificationPriority.LOW
    assert payload_wait.risk_reward_ratio is None


def test_notification_result():
    ts = pd.Timestamp("2026-03-15 12:00:00")
    result = NotificationResult(
        success=True,
        channel=NotificationChannelType.DISCORD,
        status_code=204,
        delivered_at=ts,
        event_id="sig-test-01",
    )

    assert result.success is True
    assert result.channel == NotificationChannelType.DISCORD
    assert result.status_code == 204
    d = result.to_dict()
    assert d["channel"] == "DISCORD"
    assert d["delivered_at"] == "2026-03-15 12:00:00"


def test_base_notification_channel():
    channel = DummyChannel(
        name="TestDummy",
        channel_type=NotificationChannelType.LOG,
        is_enabled=True,
        dry_run=False,
    )

    assert channel.name == "TestDummy"
    assert channel.channel_type == NotificationChannelType.LOG
    assert channel.is_enabled is True
    assert channel.dry_run is False

    valid_payload = NotificationPayload(
        event_id="e1",
        timestamp=pd.Timestamp.now("UTC"),
        symbol="BTCUSDT",
        timeframe="1h",
        action="BUY",
        direction="LONG",
        price=60000.0,
        confidence=0.8,
        predictive_score=0.75,
        regime="TRENDING_BULL",
        priority=NotificationPriority.NORMAL,
        summary="Test Buy",
        reasoning="Test reason",
    )

    assert channel.validate_payload(valid_payload) is True
    res = channel.send(valid_payload)
    assert res.success is True
    assert res.status_code == 200

    # Test invalid payload (zero price)
    invalid_payload = NotificationPayload(
        event_id="e2",
        timestamp=pd.Timestamp.now("UTC"),
        symbol="BTCUSDT",
        timeframe="1h",
        action="BUY",
        direction="LONG",
        price=0.0,  # Invalid!
        confidence=0.8,
        predictive_score=0.75,
        regime="TRENDING_BULL",
        priority=NotificationPriority.NORMAL,
        summary="Invalid",
        reasoning="Invalid",
    )
    assert channel.validate_payload(invalid_payload) is False
    res_err = channel.send(invalid_payload)
    assert res_err.success is False
    assert "Validation failed" in str(res_err.error_message)

    # Test invalid payload (missing identifiers)
    for bad_kwarg in [{"symbol": ""}, {"timeframe": ""}, {"event_id": ""}]:
        bad_payload = NotificationPayload(
            event_id=bad_kwarg.get("event_id", "e3"),
            timestamp=pd.Timestamp.now("UTC"),
            symbol=bad_kwarg.get("symbol", "BTCUSDT"),
            timeframe=bad_kwarg.get("timeframe", "1h"),
            action="BUY",
            direction="LONG",
            price=60000.0,
            confidence=0.8,
            predictive_score=0.75,
            regime="TRENDING_BULL",
            priority=NotificationPriority.NORMAL,
            summary="Invalid ID",
            reasoning="Invalid ID",
        )
        assert channel.validate_payload(bad_payload) is False


def test_signal_event_from_decision_with_string_ts_and_series():
    series_candle = pd.Series({"timestamp": "2026-03-15 14:00:00", "close": 67000.0})

    class SimpleDecision:
        decision = "SELL"
        direction = "SHORT"
        confidence = 0.70
        predictive_score = 0.65
        regime = "TRENDING_BEAR"
        reasoning = "Bearish confirmation"
        technical_score = 72.0

    event = SignalEvent.from_decision(
        decision_result=SimpleDecision(),
        candle=series_candle,
        symbol="BTCUSDT",
        timeframe="1h",
    )
    assert event.action == "SELL"
    assert event.direction == "SHORT"
    assert event.confidence == 0.70
    assert isinstance(event.timestamp, pd.Timestamp)

    # Test payload with custom summary and moderate priority
    payload = NotificationPayload.from_signal_event(
        event,
        custom_summary="Custom Sell Alert",
    )
    assert payload.priority == NotificationPriority.NORMAL
    assert payload.summary == "Custom Sell Alert"

    # Test explicit priority override
    payload_crit = NotificationPayload.from_signal_event(
        event,
        priority=NotificationPriority.CRITICAL,
    )
    assert payload_crit.priority == NotificationPriority.CRITICAL


def test_base_notification_channel_abstract_method_bodies():
    class RawChannel(BaseNotificationChannel):
        def format_message(self, payload: NotificationPayload) -> Any:
            return super().format_message(payload)

        def send(self, payload: NotificationPayload) -> Any:
            return super().send(payload)

    raw = RawChannel("raw", NotificationChannelType.LOG)
    dummy_payload = NotificationPayload.from_signal_event(
        SignalEvent(
            timestamp=pd.Timestamp.now("UTC"),
            symbol="BTCUSDT",
            timeframe="1h",
            action="WAIT",
            direction="NEUTRAL",
            confidence=0.5,
            predictive_score=0.5,
            regime="RANGE",
            reasoning="test",
            price=50000.0,
        )
    )
    assert raw.format_message(dummy_payload) is None
    assert raw.send(dummy_payload) is None



