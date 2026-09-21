from __future__ import annotations

from dataclasses import FrozenInstanceError

import pandas as pd
import pytest

from src.ai_agent.models import (
    AgentExplanation,
    AgentMarketSummary,
    MarketContext,
    RiskMetrics,
    SignalInfo,
)


def test_signal_info_creation_and_immutability():
    sig = SignalInfo(
        action="BUY",
        direction="LONG",
        confidence=0.85,
        reasoning="Bullish structure break",
        positives=("RSI oversold", "EMA crossover"),
        warnings=("Approaching major resistance",),
    )
    assert sig.action == "BUY"
    assert sig.direction == "LONG"
    assert sig.confidence == 0.85
    assert sig.reasoning == "Bullish structure break"
    assert len(sig.positives) == 2
    assert len(sig.warnings) == 1

    with pytest.raises(FrozenInstanceError):
        sig.action = "SELL"  # type: ignore[misc]

    d = sig.to_dict()
    assert d["action"] == "BUY"
    assert d["direction"] == "LONG"
    assert isinstance(d["positives"], list)
    assert isinstance(d["warnings"], list)


def test_risk_metrics_creation_and_immutability():
    risk = RiskMetrics(
        stop_loss=48000.0,
        take_profit=54000.0,
        risk_ratio=3.0,
        risk_category="Bajo",
        atr=1200.0,
        tp_multiplier=3.0,
        sl_multiplier=1.0,
    )
    assert risk.stop_loss == 48000.0
    assert risk.take_profit == 54000.0
    assert risk.risk_ratio == 3.0
    assert risk.risk_category == "Bajo"

    with pytest.raises(FrozenInstanceError):
        risk.stop_loss = 45000.0  # type: ignore[misc]

    d = risk.to_dict()
    assert d["stop_loss"] == 48000.0
    assert d["risk_ratio"] == 3.0


def test_market_context_creation_and_serialization():
    ts = pd.Timestamp("2026-03-15 12:00:00")
    sig = SignalInfo(
        action="BUY",
        direction="LONG",
        confidence=0.9,
        reasoning="Trend continuation",
        positives=("EMA 50 > EMA 200",),
        warnings=(),
    )
    risk = RiskMetrics(
        stop_loss=49000.0,
        take_profit=53000.0,
        risk_ratio=3.0,
        risk_category="Medio",
        atr=1000.0,
    )
    ctx = MarketContext(
        timestamp=ts,
        symbol="BTCUSDT",
        timeframe="1h",
        current_price=50000.0,
        market_regime="TRENDING_BULL",
        predictive_score=0.82,
        quant_score=85.0,
        signal=sig,
        risk=risk,
        technical_indicators={"rsi": 62.5, "ema_50": 49500.0, "ema_200": 47000.0},
        volume_profile={"poc": 49800.0, "vah": 51200.0, "val": 48900.0},
        metadata={"p_continuation": 0.75, "p_reversal": 0.25},
    )

    assert ctx.symbol == "BTCUSDT"
    assert ctx.current_price == 50000.0

    with pytest.raises(FrozenInstanceError):
        ctx.current_price = 51000.0  # type: ignore[misc]

    d = ctx.to_dict()
    assert d["symbol"] == "BTCUSDT"
    assert d["timestamp"] == "2026-03-15 12:00:00"
    assert d["signal"]["action"] == "BUY"
    assert d["risk"]["stop_loss"] == 49000.0
    assert d["technical_indicators"]["rsi"] == 62.5
    assert d["volume_profile"]["poc"] == 49800.0


def test_market_context_format_for_prompt():
    ts = pd.Timestamp("2026-03-15 12:00:00")
    sig = SignalInfo(
        action="SELL",
        direction="SHORT",
        confidence=0.75,
        reasoning="Overbought breakdown",
        positives=("Bearish Divergence",),
        warnings=("High market volatility",),
    )
    risk = RiskMetrics(
        stop_loss=52000.0,
        take_profit=47000.0,
        risk_ratio=1.5,
        risk_category="Alto",
        atr=1500.0,
    )
    ctx = MarketContext(
        timestamp=ts,
        symbol="ETHUSDT",
        timeframe="4h",
        current_price=50000.0,
        market_regime="TRENDING_BEAR",
        predictive_score=0.35,
        quant_score=42.0,
        signal=sig,
        risk=risk,
        technical_indicators={"rsi": 78.5, "trend": "BEARISH"},
        volume_profile={"poc": 50500.0, "vah": 52000.0, "val": 48000.0},
    )

    prompt = ctx.format_for_prompt()
    assert "# Market Context: ETHUSDT (4h)" in prompt
    assert "Current Price: 50,000.00" in prompt
    assert "Quant Score: 42.0/100" in prompt
    assert "Predictive Score: 0.35" in prompt
    assert "Market Regime: TRENDING_BEAR" in prompt
    assert "Action: SELL" in prompt
    assert "Direction: SHORT" in prompt
    assert "Bearish Divergence" in prompt
    assert "High market volatility" in prompt
    assert "Stop Loss: 52,000.00" in prompt
    assert "Take Profit: 47,000.00" in prompt
    assert "Risk/Reward Ratio: 1.50" in prompt
    assert "POC (Point of Control): 50500.0" in prompt
    assert "rsi: 78.50" in prompt
    assert "trend: BEARISH" in prompt


def test_market_context_format_for_prompt_minimal_fields():
    ts = pd.Timestamp("2026-03-15 12:00:00")
    sig = SignalInfo(
        action="WAIT",
        direction="NEUTRAL",
        confidence=0.5,
        reasoning="",
    )
    risk = RiskMetrics()
    ctx = MarketContext(
        timestamp=ts,
        symbol="SOLUSDT",
        timeframe="15m",
        current_price=150.0,
        market_regime="RANGING_CONSOLIDATION",
        predictive_score=0.5,
        quant_score=50.0,
        signal=sig,
        risk=risk,
    )

    prompt = ctx.format_for_prompt()
    assert "# Market Context: SOLUSDT (15m)" in prompt
    assert "Stop Loss: None" in prompt
    assert "Take Profit: None" in prompt
    assert "Risk/Reward Ratio: N/A" in prompt
    assert "Primary Reasoning: N/A" in prompt


def test_agent_explanation_and_summary_models():
    expl = AgentExplanation(
        summary="Clear buy signal on BTC.",
        rationale="Strong momentum across all technical timeframes.",
        key_drivers=("EMA support", "High volume"),
        risk_assessment="Low risk entry.",
        confidence=0.95,
        raw_response="RAW_EXPLANATION",
    )
    assert expl.summary == "Clear buy signal on BTC."
    assert expl.confidence == 0.95

    with pytest.raises(FrozenInstanceError):
        expl.confidence = 0.5  # type: ignore[misc]

    d_expl = expl.to_dict()
    assert isinstance(d_expl["key_drivers"], list)
    assert d_expl["raw_response"] == "RAW_EXPLANATION"

    summ = AgentMarketSummary(
        title="BTC Briefing",
        overview="Consolidating near ATH.",
        regime_interpretation="Range bound before breakout.",
        outlook="Neutral-to-bullish.",
        key_levels={"POC": 68000.0, "VAH": 70000.0},
    )
    assert summ.title == "BTC Briefing"
    assert summ.key_levels["POC"] == 68000.0

    with pytest.raises(FrozenInstanceError):
        summ.title = "New Title"  # type: ignore[misc]

    d_summ = summ.to_dict()
    assert d_summ["key_levels"]["POC"] == 68000.0
