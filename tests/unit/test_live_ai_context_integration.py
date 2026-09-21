from __future__ import annotations

from dataclasses import FrozenInstanceError

import pandas as pd
import pytest

from src.notifications.models import SignalEvent
from src.operator_service.interfaces import InMemoryMarketContextProvider
from src.operator_service.live_bridge import LiveAIContextBridge
from src.operator_service.models import MarketSummaryRequest, SignalExplanationRequest
from src.operator_service.service import OperatorService


def _create_live_signal_event(
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    price: float = 65000.0,
    action: str = "BUY",
    direction: str = "LONG",
    regime: str = "TRENDING_BULL",
    score: float = 85.0,
    pred_score: float = 0.82,
    timestamp: str = "2026-04-20 12:00:00",
) -> SignalEvent:
    ts = pd.Timestamp(timestamp)
    return SignalEvent(
        timestamp=ts,
        symbol=symbol,
        timeframe=timeframe,
        action=action,
        direction=direction,
        confidence=0.9,
        predictive_score=pred_score,
        regime=regime,
        reasoning="Live closed candle breakout",
        price=price,
        quant_score=score,
        stop_loss=price - 2000.0,
        take_profit=price + 4000.0,
        signal_id=f"sig-{symbol}-{int(ts.timestamp())}",
        metadata={
            "poc": price - 500.0,
            "vah": price + 1000.0,
            "val": price - 1500.0,
            "atr": 1200.0,
            "positives": ["EMA 50 > EMA 200", "Volume Surge"],
            "warnings": [],
        },
    )


def test_signal_event_updates_context_provider_and_service():
    provider = InMemoryMarketContextProvider()
    bridge = LiveAIContextBridge(context_provider=provider)
    service = OperatorService(context_provider=provider)

    assert bridge.context_provider is provider
    assert bridge.processed_count == 0
    assert bridge.last_context is None

    # Emit signal 1
    sig1 = _create_live_signal_event(price=65000.0, action="BUY", direction="LONG")
    ctx1 = bridge.on_signal_event(sig1)

    assert bridge.processed_count == 1
    assert bridge.last_context is ctx1
    assert ctx1.current_price == 65000.0
    assert ctx1.signal.action == "BUY"

    # Verify retrieval through OperatorService
    req_expl = SignalExplanationRequest(symbol="BTCUSDT", timeframe="1h")
    resp_expl = pytest.importorskip("asyncio").run(service.get_signal_explanation(req_expl))

    assert resp_expl.success is True
    assert resp_expl.explanation is not None
    assert "BUY signal identified for BTCUSDT" in resp_expl.explanation.summary
    assert "65,000.00" in resp_expl.explanation.summary

    req_sum = MarketSummaryRequest(symbol="BTCUSDT", timeframe="1h")
    resp_sum = pytest.importorskip("asyncio").run(service.get_market_summary(req_sum))

    assert resp_sum.success is True
    assert resp_sum.summary is not None
    assert resp_sum.summary.key_levels["CurrentPrice"] == 65000.0


def test_no_mutation_of_historical_snapshots():
    provider = InMemoryMarketContextProvider()
    bridge = LiveAIContextBridge(context_provider=provider)

    # First candle T
    sig_t = _create_live_signal_event(
        price=65000.0,
        action="BUY",
        timestamp="2026-04-20 12:00:00",
    )
    ctx_t = bridge.on_signal_event(sig_t)

    # Second candle T+1
    sig_t1 = _create_live_signal_event(
        price=66500.0,
        action="SELL",
        direction="SHORT",
        regime="HIGH_VOLATILITY_EXPANSION",
        timestamp="2026-04-20 13:00:00",
    )
    ctx_t1 = bridge.on_signal_event(sig_t1)

    assert bridge.processed_count == 2
    assert ctx_t is not ctx_t1

    # Verify snapshot at T is strictly immutable
    assert ctx_t.current_price == 65000.0
    assert ctx_t.signal.action == "BUY"
    assert ctx_t.timestamp == pd.Timestamp("2026-04-20 12:00:00")

    with pytest.raises(FrozenInstanceError):
        ctx_t.current_price = 70000.0  # type: ignore[misc]

    # Verify snapshot at T+1 reflects new data
    assert ctx_t1.current_price == 66500.0
    assert ctx_t1.signal.action == "SELL"
    assert ctx_t1.timestamp == pd.Timestamp("2026-04-20 13:00:00")


@pytest.mark.anyio
async def test_async_update_and_subscriber_isolation():
    provider = InMemoryMarketContextProvider()
    bridge = LiveAIContextBridge(context_provider=provider)

    received_contexts = []

    async def async_subscriber(ctx):
        received_contexts.append(ctx)

    def failing_subscriber(ctx):
        raise RuntimeError("Simulated downstream subscriber failure")

    bridge.subscribe(async_subscriber)
    bridge.subscribe(failing_subscriber)

    sig = _create_live_signal_event(symbol="ETHUSDT", price=3400.0)
    ctx = await bridge.on_signal_event_async(sig)

    assert bridge.processed_count == 1
    assert len(received_contexts) == 1
    assert received_contexts[0] is ctx

    # Context in provider is updated despite failing subscriber
    stored = await provider.get_latest_context("ETHUSDT", "1h")
    assert stored is not None
    assert stored.current_price == 3400.0


def test_attach_to_live_engine_mock():
    class DummyLiveEngine:
        def __init__(self):
            self.listeners = []

        def on_signal(self, callback):
            self.listeners.append(callback)

        def emit(self, event):
            for listener in self.listeners:
                listener(event)

    engine = DummyLiveEngine()
    provider = InMemoryMarketContextProvider()
    bridge = LiveAIContextBridge(context_provider=provider)

    bridge.attach_to_live_engine(engine)
    assert len(engine.listeners) == 1

    sig = _create_live_signal_event(symbol="SOLUSDT", price=160.0)
    engine.emit(sig)

    assert bridge.processed_count == 1
    assert bridge.last_context is not None
    assert bridge.last_context.symbol == "SOLUSDT"
    assert bridge.last_context.current_price == 160.0

    # Invalid engine attachment raises TypeError
    with pytest.raises(TypeError):
        bridge.attach_to_live_engine("not_an_engine")


def test_downstream_sync_subscriber_exception_safety():
    provider = InMemoryMarketContextProvider()
    bridge = LiveAIContextBridge(context_provider=provider)

    def crashing_sub(ctx):
        raise ValueError("Crash in sync sub")

    async def unawaited_async_sub(ctx):
        pass  # In sync on_signal_event, returns awaitable without error

    bridge.subscribe(crashing_sub)
    bridge.subscribe(unawaited_async_sub)

    sig = _create_live_signal_event()
    # Does not raise ValueError
    ctx = bridge.on_signal_event(sig)
    assert ctx is not None
    assert bridge.processed_count == 1
