from __future__ import annotations

import pandas as pd

from src.ai_agent.context_builder import ContextBuilder
from src.decision_engine import DecisionResult
from src.notifications.models import SignalEvent


def test_build_from_signal_event_complete():
    ts = pd.Timestamp("2026-04-01 10:00:00")
    sig = SignalEvent(
        timestamp=ts,
        symbol="BTCUSDT",
        timeframe="1h",
        action="BUY",
        direction="LONG",
        confidence=0.88,
        predictive_score=0.79,
        regime="TRENDING_BULL",
        reasoning="Strong trend continuation with volume surge",
        price=60000.0,
        quant_score=82.0,
        stop_loss=58000.0,
        take_profit=66000.0,
        signal_id="sig-btc-001",
        metadata={
            "positives": ["EMA 50 > EMA 200", "Volume > SMA 20"],
            "warnings": ["RSI near 70"],
            "atr": 1000.0,
            "risk_category": "Bajo",
            "tp_multiplier": 3.0,
            "sl_multiplier": 1.0,
            "poc": 59500.0,
            "vah": 61000.0,
            "val": 58500.0,
            "rsi": 68.5,
            "p_continuation": 0.81,
            "p_reversal": 0.19,
        },
    )

    ctx = ContextBuilder.build_from_signal_event(sig)

    assert ctx.symbol == "BTCUSDT"
    assert ctx.timeframe == "1h"
    assert ctx.current_price == 60000.0
    assert ctx.market_regime == "TRENDING_BULL"
    assert ctx.predictive_score == 0.79
    assert ctx.quant_score == 82.0

    # Signal Info
    assert ctx.signal.action == "BUY"
    assert ctx.signal.direction == "LONG"
    assert ctx.signal.confidence == 0.88
    assert ctx.signal.reasoning == "Strong trend continuation with volume surge"
    assert ctx.signal.positives == ("EMA 50 > EMA 200", "Volume > SMA 20")
    assert ctx.signal.warnings == ("RSI near 70",)

    # Risk Metrics
    assert ctx.risk.stop_loss == 58000.0
    assert ctx.risk.take_profit == 66000.0
    # Reward = 66000 - 60000 = 6000, Risk = 60000 - 58000 = 2000 -> ratio = 3.0
    assert ctx.risk.risk_ratio == 3.0
    assert ctx.risk.risk_category == "Bajo"
    assert ctx.risk.atr == 1000.0
    assert ctx.risk.tp_multiplier == 3.0
    assert ctx.risk.sl_multiplier == 1.0

    # Volume Profile
    assert ctx.volume_profile["poc"] == 59500.0
    assert ctx.volume_profile["vah"] == 61000.0
    assert ctx.volume_profile["val"] == 58500.0

    # Technical Indicators
    assert ctx.technical_indicators["rsi"] == 68.5
    assert ctx.technical_indicators["p_continuation"] == 0.81


def test_build_from_signal_event_missing_sl_tp_and_zero_division():
    ts = pd.Timestamp("2026-04-01 10:00:00")
    sig_no_bounds = SignalEvent(
        timestamp=ts,
        symbol="ETHUSDT",
        timeframe="15m",
        action="WAIT",
        direction="NEUTRAL",
        confidence=0.5,
        predictive_score=0.4,
        regime="RANGING_CONSOLIDATION",
        reasoning="Choppy market conditions",
        price=3000.0,
        stop_loss=None,
        take_profit=None,
    )

    ctx_no_bounds = ContextBuilder.build_from_signal_event(sig_no_bounds)
    assert ctx_no_bounds.risk.stop_loss is None
    assert ctx_no_bounds.risk.take_profit is None
    assert ctx_no_bounds.risk.risk_ratio is None

    # Zero division test: price == stop_loss
    sig_zero_div = SignalEvent(
        timestamp=ts,
        symbol="ETHUSDT",
        timeframe="15m",
        action="BUY",
        direction="LONG",
        confidence=0.7,
        predictive_score=0.6,
        regime="TRENDING_BULL",
        reasoning="Test zero div",
        price=3000.0,
        stop_loss=3000.0,  # price == sl -> distance = 0
        take_profit=3200.0,
    )
    ctx_zero_div = ContextBuilder.build_from_signal_event(sig_zero_div)
    assert ctx_zero_div.risk.risk_ratio is None


def test_build_from_signal_event_with_supplemental_market_report():
    ts = pd.Timestamp("2026-04-01 10:00:00")
    sig = SignalEvent(
        timestamp=ts,
        symbol="SOLUSDT",
        timeframe="1h",
        action="BUY",
        direction="LONG",
        confidence=0.8,
        predictive_score=0.75,
        regime="TRENDING_BULL",
        reasoning="Trend test",
        price=180.0,
        stop_loss=170.0,
        take_profit=200.0,
        # metadata without positives or warnings to test fallback to market_report
        metadata={},
    )

    market_report = {
        "symbol": "SOLUSDT",
        "price": 180.0,
        "trend": {"status": "BULLISH", "ema_200": 160.0},
        "momentum": {"rsi": 58.0},
        "volatility": {"atr": 5.0},
        "volume": {"surge": True},
        "risk": "Bajo",
        "profile": {"poc": 178.0, "vah": 185.0, "val": 172.0},
        "decision": {
            "positives": ["EMA alignment", "Above POC"],
            "warnings": ["Low volume session"],
        },
    }

    ctx = ContextBuilder.build_from_signal_event(
        signal_event=sig,
        market_report=market_report,
        extra_metadata={"custom_tag": "research_alpha"},
    )

    assert ctx.signal.positives == ("EMA alignment", "Above POC")
    assert ctx.signal.warnings == ("Low volume session",)
    assert ctx.risk.risk_category == "Bajo"
    assert ctx.risk.atr == 5.0
    assert ctx.volume_profile["poc"] == 178.0
    assert ctx.technical_indicators["trend"] == {"status": "BULLISH", "ema_200": 160.0}
    assert ctx.metadata["custom_tag"] == "research_alpha"


def test_build_from_decision_utility_path():
    candle = {
        "timestamp": "2026-04-01 12:00:00",
        "open": 64000.0,
        "high": 65500.0,
        "low": 63800.0,
        "close": 65000.0,
        "volume": 1250.0,
    }

    decision = DecisionResult(
        decision="BUY",
        confidence=0.85,
        positives=["Breakout", "High predictive score"],
        warnings=["Macro risk"],
        market_state="TRENDING",
        signal="BUY",
        technical_score=80.0,
        predictive_score=0.88,
        regime="TRENDING_BULL",
        tp_multiplier=2.5,
        sl_multiplier=1.0,
        reasoning="Favorable breakout context",
        direction="LONG",
    )

    ctx = ContextBuilder.build_from_decision(
        decision_result=decision,
        candle=candle,
        symbol="BTCUSDT",
        timeframe="1h",
        stop_loss=63500.0,
        take_profit=68750.0,
    )

    assert ctx.symbol == "BTCUSDT"
    assert ctx.timeframe == "1h"
    assert ctx.current_price == 65000.0
    assert ctx.market_regime == "TRENDING_BULL"
    assert ctx.signal.action == "BUY"
    assert ctx.signal.direction == "LONG"
    assert ctx.signal.positives == ("Breakout", "High predictive score")
    assert ctx.risk.stop_loss == 63500.0
    assert ctx.risk.take_profit == 68750.0
    # Reward = 3750, Risk = 1500 -> ratio = 2.5
    assert ctx.risk.risk_ratio == 2.5


def test_build_from_signal_event_risk_engine_dict_fallback():
    ts = pd.Timestamp("2026-04-01 10:00:00")
    sig = SignalEvent(
        timestamp=ts,
        symbol="ADAUSDT",
        timeframe="1h",
        action="WAIT",
        direction="NEUTRAL",
        confidence=0.5,
        predictive_score=0.4,
        regime="RANGING_CONSOLIDATION",
        reasoning="Testing fallback",
        price=0.5,
        metadata={},
    )
    # market_report where risk is not a str, but risk_engine is a dict
    market_report = {
        "symbol": "ADAUSDT",
        "price": 0.5,
        "risk_engine": {"risk": "Moderado"},
    }
    ctx = ContextBuilder.build_from_signal_event(sig, market_report=market_report)
    assert ctx.risk.risk_category == "Moderado"

