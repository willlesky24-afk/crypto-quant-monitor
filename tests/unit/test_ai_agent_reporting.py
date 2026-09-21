from __future__ import annotations

import pandas as pd
import pytest

from src.ai_agent.interfaces import MockAIProvider
from src.ai_agent.models import (
    AgentMarketSummary,
    MarketContext,
    RiskMetrics,
    SignalInfo,
)
from src.ai_agent.reporting import MarketReportGenerator


def _create_report_context(
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    price: float = 65000.0,
    regime: str = "TRENDING_BULL",
    score: float = 85.0,
    pred_score: float = 0.82,
    action: str = "BUY",
    direction: str = "LONG",
    reasoning: str = "Bullish continuation pattern",
    stop_loss: float | None = 62000.0,
    take_profit: float | None = 71000.0,
    risk_ratio: float | None = 2.0,
    risk_category: str = "Bajo",
    atr: float | None = 1500.0,
    poc: float | None = 64000.0,
    vah: float | None = 66000.0,
    val: float | None = 63000.0,
    metadata: dict | None = None,
) -> MarketContext:
    ts = pd.Timestamp("2026-04-10 16:00:00")
    sig = SignalInfo(
        action=action,
        direction=direction,
        confidence=0.88,
        reasoning=reasoning,
        positives=("Bullish structure",),
        warnings=(),
    )
    risk = RiskMetrics(
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_ratio=risk_ratio,
        risk_category=risk_category,
        atr=atr,
    )
    vp = {}
    if poc is not None:
        vp["poc"] = poc
    if vah is not None:
        vp["vah"] = vah
    if val is not None:
        vp["val"] = val

    return MarketContext(
        timestamp=ts,
        symbol=symbol,
        timeframe=timeframe,
        current_price=price,
        market_regime=regime,
        predictive_score=pred_score,
        quant_score=score,
        signal=sig,
        risk=risk,
        volume_profile=vp,
        metadata=metadata or {},
    )


def test_generate_bullish_market_summary():
    gen = MarketReportGenerator()
    # Price 67000 is above VAH (66000)
    ctx = _create_report_context(
        symbol="BTCUSDT",
        price=67000.0,
        regime="TRENDING_BULL",
        vah=66000.0,
        val=63000.0,
        poc=64500.0,
        metadata={"market_state": "BULLISH_TREND"},
    )

    report = gen.generate_report(ctx)

    assert isinstance(report, AgentMarketSummary)
    assert report.title == "BTCUSDT Market Intelligence Report (1h)"
    assert "BTCUSDT is trading at 67,000.00 on the 1h timeframe" in report.overview
    assert "Quant Score of 85.0/100" in report.overview
    assert "predictive continuation/reversal score at 0.82" in report.overview
    assert "System stance is BUY (LONG)" in report.overview

    assert "Bullish trend regime identified" in report.regime_interpretation
    assert "trading above the Value Area (VAH at 66,000.00)" in report.regime_interpretation

    assert "Operational focus: Bullish continuation pattern." in report.outlook
    assert "Risk environment is assessed as Bajo." in report.outlook
    assert "Stop Loss at 62,000.00 and Take Profit at 71,000.00 (R:R 2.00)" in report.outlook

    assert report.key_levels["CurrentPrice"] == 67000.0
    assert report.key_levels["POC"] == 64500.0
    assert report.key_levels["VAH"] == 66000.0
    assert report.key_levels["VAL"] == 63000.0
    assert report.key_levels["StopLoss"] == 62000.0
    assert report.key_levels["TakeProfit"] == 71000.0

    assert report.metadata["deterministic"] is True
    assert report.metadata["market_state"] == "BULLISH_TREND"


def test_generate_bearish_market_summary():
    gen = MarketReportGenerator()
    # Price 3100 is below VAL (3200)
    ctx = _create_report_context(
        symbol="ETHUSDT",
        timeframe="4h",
        price=3100.0,
        regime="TRENDING_BEAR",
        score=32.0,
        pred_score=0.22,
        action="SELL",
        direction="SHORT",
        reasoning="Bearish breakdown below value area",
        stop_loss=3350.0,
        take_profit=2700.0,
        risk_ratio=1.6,
        risk_category="Medio",
        poc=3400.0,
        vah=3550.0,
        val=3200.0,
    )

    report = gen.generate_report(ctx)

    assert "ETHUSDT Market Intelligence Report (4h)" == report.title
    assert "System stance is SELL (SHORT)" in report.overview
    assert "Bearish trend regime identified" in report.regime_interpretation
    assert "trading below the Value Area (VAL at 3,200.00)" in report.regime_interpretation
    assert "Stop Loss at 3,350.00 and Take Profit at 2,700.00" in report.outlook
    assert report.key_levels["StopLoss"] == 3350.0
    assert report.key_levels["TakeProfit"] == 2700.0


def test_generate_ranging_market_summary():
    gen = MarketReportGenerator()
    # Price 150 is between VAL (145) and VAH (155)
    ctx = _create_report_context(
        symbol="SOLUSDT",
        timeframe="15m",
        price=150.0,
        regime="RANGING_CONSOLIDATION",
        score=50.0,
        pred_score=0.5,
        action="WAIT",
        direction="NEUTRAL",
        reasoning="Consolidation in midpoint",
        stop_loss=None,
        take_profit=None,
        risk_ratio=None,
        risk_category="Bajo",
        poc=150.0,
        vah=155.0,
        val=145.0,
    )

    report = gen.generate_report(ctx)

    assert "Consolidation/Range regime identified" in report.regime_interpretation
    assert "trading within the Value Area (145.00 - 155.00)" in report.regime_interpretation
    assert "confirming fair value acceptance centered at POC (150.00)" in report.regime_interpretation
    assert "No explicit Stop Loss or Take Profit targets defined for this posture." in report.outlook


def test_generate_high_volatility_summary():
    gen = MarketReportGenerator()
    ctx = _create_report_context(
        symbol="AVAXUSDT",
        price=35.0,
        regime="HIGH_VOLATILITY_EXPANSION",
        score=45.0,
        pred_score=0.4,
        action="WAIT",
        direction="NEUTRAL",
        reasoning="Volatility spike with wide spreads",
        stop_loss=30.0,
        take_profit=None,
        risk_category="Alto",
        atr=3.5,
        poc=None,
        vah=None,
        val=None,
    )

    report = gen.generate_report(ctx)

    assert "High volatility expansion regime identified" in report.regime_interpretation
    assert "Local volatility measured by ATR is 3.50." in report.outlook
    assert "Risk environment is assessed as Alto." in report.outlook
    assert "Protective Stop Loss is stationed at 30.00." in report.outlook
    assert "POC" not in report.key_levels
    assert report.key_levels["StopLoss"] == 30.0


def test_generate_custom_regime_and_missing_optional_fields():
    gen = MarketReportGenerator()
    ts = pd.Timestamp("2026-04-10 16:00:00")
    ctx = MarketContext(
        timestamp=ts,
        symbol="DOGEUSDT",
        timeframe="1h",
        current_price=0.15,
        market_regime="UNKNOWN_ANOMALY",
        predictive_score=0.5,
        quant_score=50.0,
        signal=SignalInfo(action="WAIT", direction="NEUTRAL", confidence=0.5),
        risk=RiskMetrics(take_profit=0.20),
        volume_profile={"poc": 0.14},  # POC only, no VAH/VAL
    )

    report = gen.generate_report(ctx)

    assert "Market is operating under an unclassified or custom UNKNOWN_ANOMALY regime." in report.regime_interpretation
    assert "Point of Control (POC) is situated at 0.14." in report.regime_interpretation
    assert "Operational focus: Quantitative parameters monitor for confirmed setups." in report.outlook
    assert "Target Take Profit is set at 0.20." in report.outlook
    assert report.key_levels["TakeProfit"] == 0.20
    assert report.key_levels["POC"] == 0.14
    assert "StopLoss" not in report.key_levels


def test_report_generator_determinism():
    gen = MarketReportGenerator()
    ctx = _create_report_context()

    r1 = gen.generate_report(ctx)
    r2 = gen.generate_report(ctx)

    assert r1.title == r2.title
    assert r1.overview == r2.overview
    assert r1.regime_interpretation == r2.regime_interpretation
    assert r1.outlook == r2.outlook
    assert r1.key_levels == r2.key_levels
    assert r1.to_dict() == r2.to_dict()


@pytest.mark.anyio
async def test_generate_report_async_without_provider():
    gen = MarketReportGenerator(provider=None)
    assert gen.provider is None
    ctx = _create_report_context()

    report = await gen.generate_report_async(ctx)
    assert report.title.startswith("BTCUSDT Market Intelligence Report")
    assert report.metadata["generator"] == "MarketReportGenerator"


@pytest.mark.anyio
async def test_generate_report_async_with_provider():
    provider = MockAIProvider(name="mock-briefing-provider")
    gen = MarketReportGenerator(provider=provider)
    assert gen.provider is provider
    ctx = _create_report_context()

    report = await gen.generate_report_async(ctx)
    assert report.metadata["provider"] == "mock-briefing-provider"
