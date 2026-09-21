from __future__ import annotations

import pandas as pd

from src.ai_agent.models import MarketContext, RiskMetrics, SignalInfo
from src.ai_providers.prompt_builder import PromptBuilder
from src.anomaly_detection.models import AlertSeverity, AnomalyType, MarketAlert
from src.market_reports.models import DailyBriefingReport


def _create_sample_context() -> MarketContext:
    return MarketContext(
        timestamp=pd.Timestamp("2026-09-20 12:00:00", tz="UTC"),
        symbol="BTCUSDT",
        timeframe="1h",
        current_price=64500.0,
        market_regime="TRENDING_BULL",
        predictive_score=0.82,
        quant_score=85.0,
        signal=SignalInfo(
            action="BUY",
            direction="LONG",
            confidence=0.88,
            reasoning="Momentum breakout above 20 EMA",
            positives=("Volume confirmation", "RSI healthy"),
            warnings=("Nearby resistance at 66k",),
        ),
        risk=RiskMetrics(
            stop_loss=63000.0,
            take_profit=67500.0,
            risk_category="LOW",
            atr=1200.0,
        ),
        technical_indicators={"rsi": 66.5},
        volume_profile={"poc": 64200.0, "vah": 65000.0, "val": 63800.0},
    )


def test_prompt_builder_basic_construction():
    builder = PromptBuilder()
    ctx = _create_sample_context()
    prompt = builder.build_copilot_prompt(context=ctx, query="Analyze BTC right now")

    assert "You are an institutional AI Quant Trading Copilot" in prompt
    assert "DO NOT provide definitive financial or investment instructions" in prompt
    assert "DO NOT generate or execute trades" in prompt
    assert "Asset: BTCUSDT | Interval: 1H" in prompt
    assert "$64,500.00" in prompt
    assert "TRENDING_BULL" in prompt
    assert "Quant Score: 85.0/100" in prompt
    assert "Predictive Score: 0.82" in prompt
    assert "Stop Loss: $63,000.00" in prompt
    assert "Take Profit: $67,500.00" in prompt
    assert "POC: 64200.0" in prompt
    assert "Query: \"Analyze BTC right now\"" in prompt



def test_prompt_builder_with_reports_and_anomalies():
    builder = PromptBuilder()
    ctx = _create_sample_context()

    briefing = DailyBriefingReport(
        report_id="rep-1",
        symbol="BTCUSDT",
        timeframe="1h",
        timestamp="2026-09-20T12:00:00Z",
        market_overview="Executive macro overview",
        current_regime="TRENDING_BULL",
        quant_score=85.0,
        predictive_score=0.82,
        strongest_signals=("BUY signal active",),
        main_risks=("Resistance at 66k",),
        important_levels={"Stop Loss": 63000.0},
        volatility_analysis="ATR normalized at 1200",
        historical_context="Closed candle T context",
    )

    alert = MarketAlert(
        alert_id="alt-1",
        anomaly_type=AnomalyType.VOLATILITY_EXPANSION,
        severity=AlertSeverity.WARNING,
        symbol="BTCUSDT",
        timeframe="1h",
        headline="BTC Volatility Expansion (+35%)",
        reason="ATR jumped from 900 to 1200",
        current_value=1200.0,
        reference_value=900.0,
    )

    prompt = builder.build_copilot_prompt(
        context=ctx,
        query="Explain recent volatility",
        briefing=briefing,
        alerts=[alert],
    )

    assert "DAILY MARKET BRIEFING CONTEXT" in prompt
    assert "Overview: Executive macro overview" in prompt
    assert "PASSIVE MARKET ANOMALY ALERTS DETECTED" in prompt
    assert "[WARNING] BTC Volatility Expansion (+35%): ATR jumped from 900 to 1200" in prompt