from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd

from src.decision_engine import DecisionResult
from src.notifications.channels.discord import DiscordWebhookChannel
from src.notifications.dispatcher import NotificationDispatcher
from src.notifications.models import (
    NotificationChannelType,
    SignalEvent,
)
from src.streaming.candle_aggregator import CandleAggregator, KlineEvent
from src.streaming.live_engine import LiveExecutionEngine


def _generate_synthetic_ohlcv(bars: int = 250) -> pd.DataFrame:
    """Generate a realistic synthetic trending OHLCV DataFrame for testing."""
    dates = pd.date_range("2026-01-01", periods=bars, freq="1h", tz="UTC")
    base_price = 50000.0
    t = np.linspace(0, 10, bars)
    # Upward trending price with some sine wave variation
    close_prices = base_price + (t * 500.0) + (np.sin(t * 3) * 200.0)
    high_prices = close_prices + 150.0
    low_prices = close_prices - 150.0
    open_prices = close_prices - 20.0
    volume = np.random.uniform(100.0, 500.0, size=bars)

    return pd.DataFrame({
        "timestamp": dates,
        "open": open_prices,
        "high": high_prices,
        "low": low_prices,
        "close": close_prices,
        "volume": volume,
    })


def test_live_engine_warm_up_insufficient_bars():
    engine = LiveExecutionEngine(symbol="BTCUSDT", interval="1h", warm_up_bars=200)

    # DataFrame with only 50 bars
    short_df = _generate_synthetic_ohlcv(bars=50)
    kline = KlineEvent.from_binance_payload({
        "e": "kline",
        "s": "BTCUSDT",
        "k": {
            "t": 1672531200000,
            "T": 1672534799999,
            "s": "BTCUSDT",
            "i": "1h",
            "o": "50000.0",
            "c": "50100.0",
            "h": "50200.0",
            "l": "49900.0",
            "v": "100.0",
            "x": True,
        },
    })

    sig, dec, notifs = engine.on_candle_closed(short_df, kline)
    assert sig is None
    assert dec is None
    assert notifs == []
    assert len(engine.signal_history) == 0


def test_live_engine_full_predictive_pipeline_execution():
    dispatcher = NotificationDispatcher(
        channels=[DiscordWebhookChannel(webhook_url="https://discord.com/api/webhooks/test", dry_run=True)],
        min_predictive_score=0.10,  # Low threshold to ensure delivery
        min_confidence=0.10,
        ignore_actions=set(),  # Accept any action
    )

    engine = LiveExecutionEngine(
        symbol="BTCUSDT",
        interval="1h",
        dispatcher=dispatcher,
        predictive_mode=True,
        warm_up_bars=200,
    )

    received_signals: list[SignalEvent] = []
    engine.on_signal(lambda s: received_signals.append(s))

    full_df = _generate_synthetic_ohlcv(bars=220)
    last_row = full_df.iloc[-1]
    kline = KlineEvent(
        symbol="BTCUSDT",
        interval="1h",
        start_time=pd.Timestamp(last_row["timestamp"]),
        close_time=pd.Timestamp(last_row["timestamp"]) + pd.Timedelta(hours=1),
        open=float(last_row["open"]),
        high=float(last_row["high"]),
        low=float(last_row["low"]),
        close=float(last_row["close"]),
        volume=float(last_row["volume"]),
        is_closed=True,
    )

    signal_event, decision, notifs = engine.on_candle_closed(full_df, kline)

    assert signal_event is not None
    assert decision is not None
    assert signal_event.symbol == "BTCUSDT"
    assert signal_event.timeframe == "1h"
    assert signal_event.price == float(last_row["close"])
    assert signal_event.predictive_score > 0.0
    assert signal_event.confidence > 0.0
    assert len(signal_event.regime) > 0
    assert "poc" in signal_event.metadata
    assert "vah" in signal_event.metadata
    assert "val" in signal_event.metadata

    # State update verification
    assert engine.last_signal == signal_event
    assert engine.last_decision == decision
    assert len(engine.signal_history) == 1
    assert len(received_signals) == 1

    # Notification dispatch verification
    assert len(notifs) >= 1
    assert notifs[0].success is True
    assert notifs[0].channel == NotificationChannelType.DISCORD


def test_live_engine_legacy_mode_execution():
    engine = LiveExecutionEngine(symbol="ETHUSDT", interval="4h", predictive_mode=False, warm_up_bars=200)

    full_df = _generate_synthetic_ohlcv(bars=210)
    last_row = full_df.iloc[-1]
    kline = KlineEvent(
        symbol="ETHUSDT",
        interval="4h",
        start_time=pd.Timestamp(last_row["timestamp"]),
        close_time=pd.Timestamp(last_row["timestamp"]) + pd.Timedelta(hours=4),
        open=float(last_row["open"]),
        high=float(last_row["high"]),
        low=float(last_row["low"]),
        close=float(last_row["close"]),
        volume=float(last_row["volume"]),
        is_closed=True,
    )

    sig, dec, notifs = engine.on_candle_closed(full_df, kline)
    assert sig is not None
    assert dec is not None
    assert sig.regime == "UNKNOWN"
    assert sig.predictive_score == 0.0


def test_live_engine_attach_aggregator_end_to_end():
    engine = LiveExecutionEngine(symbol="BTCUSDT", interval="1h", warm_up_bars=200)
    aggregator = CandleAggregator(symbol="BTCUSDT", interval="1h", max_bars=300)

    # Attach engine to aggregator
    engine.attach_aggregator(aggregator)

    # Seed aggregator with 210 historical bars
    seed_df = _generate_synthetic_ohlcv(bars=210)
    aggregator.seed(seed_df)

    # Feed an intra-bar kline (is_closed=False) -> should NOT trigger engine analysis
    t_open = int(pd.Timestamp("2026-03-01 00:00:00", tz="UTC").timestamp() * 1000)
    intra_kline = KlineEvent.from_binance_payload({
        "e": "kline",
        "s": "BTCUSDT",
        "k": {
            "t": t_open,
            "T": t_open + 3599999,
            "s": "BTCUSDT",
            "i": "1h",
            "o": "65000.0",
            "c": "65150.0",
            "h": "65200.0",
            "l": "64900.0",
            "v": "50.0",
            "x": False,
        },
    })
    aggregator.process_kline(intra_kline)
    assert len(engine.signal_history) == 0

    # Feed closed kline (is_closed=True) -> triggers engine analysis automatically
    closed_kline = KlineEvent.from_binance_payload({
        "e": "kline",
        "s": "BTCUSDT",
        "k": {
            "t": t_open,
            "T": t_open + 3599999,
            "s": "BTCUSDT",
            "i": "1h",
            "o": "65000.0",
            "c": "65200.0",
            "h": "65250.0",
            "l": "64900.0",
            "v": "120.0",
            "x": True,
        },
    })
    aggregator.process_kline(closed_kline)

    assert len(engine.signal_history) == 1
    assert engine.last_signal is not None
    assert engine.last_signal.price == 65200.0


def test_live_engine_listener_and_dispatcher_error_isolation():
    mock_dispatcher = MagicMock()
    mock_dispatcher.dispatch_signal.side_effect = RuntimeError("Dispatcher crashed!")

    engine = LiveExecutionEngine(symbol="BTCUSDT", interval="1h", dispatcher=mock_dispatcher, warm_up_bars=200)

    def failing_listener(sig):
        raise ValueError("Listener crashed!")

    engine.on_signal(failing_listener)

    full_df = _generate_synthetic_ohlcv(bars=205)
    last_row = full_df.iloc[-1]
    kline = KlineEvent(
        symbol="BTCUSDT",
        interval="1h",
        start_time=pd.Timestamp(last_row["timestamp"]),
        close_time=pd.Timestamp(last_row["timestamp"]) + pd.Timedelta(hours=1),
        open=float(last_row["open"]),
        high=float(last_row["high"]),
        low=float(last_row["low"]),
        close=float(last_row["close"]),
        volume=float(last_row["volume"]),
        is_closed=True,
    )

    # Should not crash despite listener and dispatcher errors
    sig, dec, notifs = engine.on_candle_closed(full_df, kline)
    assert sig is not None
    assert len(engine.signal_history) == 1


def test_live_engine_short_direction_sl_tp():
    engine = LiveExecutionEngine(symbol="BTCUSDT", interval="1h", warm_up_bars=200)

    # Mock decision engine to return SHORT
    mock_decision = DecisionResult(
        decision="SELL",
        confidence=0.85,
        positives=[],
        warnings=[],
        market_state="Bearish",
        direction="SHORT",
        tp_multiplier=2.5,
        sl_multiplier=1.2,
        reasoning="Bearish breakdown",
    )
    engine.decision_engine.evaluate = MagicMock(return_value=mock_decision)

    full_df = _generate_synthetic_ohlcv(bars=205)
    last_row = full_df.iloc[-1]
    kline = KlineEvent(
        symbol="BTCUSDT",
        interval="1h",
        start_time=pd.Timestamp(last_row["timestamp"]),
        close_time=pd.Timestamp(last_row["timestamp"]) + pd.Timedelta(hours=1),
        open=float(last_row["open"]),
        high=float(last_row["high"]),
        low=float(last_row["low"]),
        close=float(last_row["close"]),
        volume=float(last_row["volume"]),
        is_closed=True,
    )

    sig, dec, notifs = engine.on_candle_closed(full_df, kline)
    assert sig is not None
    assert sig.direction == "SHORT"
    assert sig.action == "SELL"
    # For SHORT, SL must be above close price, TP below close price
    assert sig.stop_loss > sig.price
    assert sig.take_profit < sig.price

