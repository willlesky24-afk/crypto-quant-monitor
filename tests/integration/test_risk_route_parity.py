from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.constants import DECISION_FAVORABLE, DECISION_WAIT_CONFIRMATION
from src.decision_engine import DecisionEngine, DecisionResult
from src.market_scanner import MarketScanner
from src.operator_assistant import on_demand_context
from src.operator_assistant.assistant import OperatorAssistant
from src.streaming.candle_aggregator import KlineEvent
from src.streaming.live_engine import LiveExecutionEngine


@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
@pytest.mark.parametrize(
    ("decision_name", "expected_status"),
    [
        (DECISION_FAVORABLE, "CANDIDATA"),
        (DECISION_WAIT_CONFIRMATION, "ESPERANDO CONFIRMACIÓN"),
    ],
)
def test_scanner_live_and_on_demand_share_effective_risk_levels(
    monkeypatch, synthetic_ohlcv, direction, decision_name, expected_status
):
    """The three routes receive the same closed candles and decision parameters."""
    decision = DecisionResult(
        decision=decision_name,
        confidence=85.0,
        positives=[],
        warnings=[],
        market_state="fixture",
        direction=direction,
        sl_multiplier=1.5,
        tp_multiplier=3.0,
        reasoning="Deterministic test decision",
    )
    monkeypatch.setattr(DecisionEngine, "evaluate", lambda self, **kwargs: decision)

    loader = MagicMock()
    loader.get_klines.return_value = synthetic_ohlcv.copy()
    scanner_result = MarketScanner(data_loader=loader).scan_market(
        symbols=["BTCUSDT"], timeframe="1h"
    )[0]
    monkeypatch.setattr(on_demand_context, "BinanceDataLoader", lambda: loader)
    context = on_demand_context.build_on_demand_context("BTCUSDT", "1h")
    assert context is not None

    last = synthetic_ohlcv.iloc[-1]
    event = KlineEvent(
        symbol="BTCUSDT",
        interval="1h",
        start_time=pd.Timestamp(last["timestamp"]),
        close_time=pd.Timestamp(last["timestamp"]) + pd.Timedelta(hours=1),
        open=float(last["open"]),
        high=float(last["high"]),
        low=float(last["low"]),
        close=float(last["close"]),
        volume=float(last["volume"]),
        is_closed=True,
    )
    dispatcher = MagicMock()
    live = LiveExecutionEngine("BTCUSDT", "1h", dispatcher=dispatcher)
    live_event, _, notifications = live.on_candle_closed(synthetic_ohlcv.copy(), event)

    assert live_event is not None
    assistant_plan = OperatorAssistant._validated_risk_plan(context)
    assert assistant_plan["status"] == expected_status
    assert (
        scanner_result.status
        == live_event.metadata["signal_status"]
        == context.metadata["signal_status"]
        == expected_status
    )
    assert scanner_result.direction == live_event.direction == context.signal.direction
    assert live_event.action == context.signal.action == "WAIT"
    assert (
        live_event.metadata["decision_label"]
        == context.metadata["decision_label"]
        == decision_name
    )
    assert context.signal.action == "WAIT"
    assert expected_status in context.signal.reasoning
    assert (
        scanner_result.entry_confirmed
        is live_event.metadata["entry_confirmed"]
        is context.metadata["entry_confirmed"]
        is False
    )
    if expected_status == "CANDIDATA":
        assert scanner_result.direction == direction
        assert scanner_result.entry_price == pytest.approx(
            live_event.metadata["entry_price"]
        )
        assert scanner_result.entry_price == pytest.approx(
            context.metadata["entry_price"]
        )
        assert scanner_result.stop_loss == pytest.approx(live_event.stop_loss)
        assert scanner_result.stop_loss == pytest.approx(context.risk.stop_loss)
        assert scanner_result.take_profit == pytest.approx(live_event.take_profit)
        assert scanner_result.take_profit == pytest.approx(context.risk.take_profit)
        assert scanner_result.risk_reward == pytest.approx(
            live_event.metadata["risk_reward_ratio"]
        )
        assert scanner_result.risk_reward == pytest.approx(
            context.metadata["risk_reward_ratio"]
        )
        assert scanner_result.risk_reward == pytest.approx(context.risk.risk_ratio)
        assert assistant_plan["entry_price"] == scanner_result.entry_price
        assert assistant_plan["stop_loss"] == scanner_result.stop_loss
        assert assistant_plan["take_profit"] == scanner_result.take_profit
        assert assistant_plan["gross_risk_reward"] == scanner_result.risk_reward
        assert scanner_result.risk_reward == pytest.approx(
            scanner_result.reward_distance / scanner_result.risk_distance
        )
    else:
        assert scanner_result.direction == "SIN OPERACIÓN"
        assert (
            scanner_result.entry_price
            is live_event.metadata["entry_price"]
            is context.metadata["entry_price"]
            is None
        )
        assert (
            scanner_result.stop_loss
            is live_event.stop_loss
            is context.risk.stop_loss
            is None
        )
        assert (
            scanner_result.take_profit
            is live_event.take_profit
            is context.risk.take_profit
            is None
        )
        assert (
            scanner_result.risk_reward
            is live_event.metadata["risk_reward_ratio"]
            is context.risk.risk_ratio
            is None
        )
        assert assistant_plan["entry_price"] is None
        assert assistant_plan["stop_loss"] is None
        assert assistant_plan["take_profit"] is None
        assert assistant_plan["gross_risk_reward"] is None
    assert notifications == []
    dispatcher.dispatch_signal.assert_not_called()
