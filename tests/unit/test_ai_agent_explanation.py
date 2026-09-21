from __future__ import annotations

import pandas as pd
import pytest

from src.ai_agent.explanation import SignalExplanationService
from src.ai_agent.interfaces import MockAIProvider
from src.ai_agent.models import (
    AgentExplanation,
    MarketContext,
    RiskMetrics,
    SignalInfo,
)


def _make_context(
    action: str = "BUY",
    direction: str = "LONG",
    price: float = 65000.0,
    regime: str = "TRENDING_BULL",
    score: float = 85.0,
    pred_score: float = 0.82,
    reasoning: str = "Breakout confirmed by volume",
    positives: tuple[str, ...] = ("EMA crossover", "Volume expansion"),
    warnings: tuple[str, ...] = ("Near resistance",),
    stop_loss: float | None = 62000.0,
    take_profit: float | None = 71000.0,
    risk_ratio: float | None = 2.0,
    risk_category: str = "Bajo",
    atr: float | None = 1500.0,
    tp_mult: float | None = 3.0,
    sl_mult: float | None = 1.0,
    poc: float | None = 64000.0,
    metadata: dict | None = None,
) -> MarketContext:
    ts = pd.Timestamp("2026-04-10 14:00:00")
    sig = SignalInfo(
        action=action,
        direction=direction,
        confidence=0.88,
        reasoning=reasoning,
        positives=positives,
        warnings=warnings,
    )
    risk = RiskMetrics(
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_ratio=risk_ratio,
        risk_category=risk_category,
        atr=atr,
        tp_multiplier=tp_mult,
        sl_multiplier=sl_mult,
    )
    vp = {}
    if poc is not None:
        vp["poc"] = poc
        vp["vah"] = poc + 1000.0
        vp["val"] = poc - 1000.0

    return MarketContext(
        timestamp=ts,
        symbol="BTCUSDT",
        timeframe="1h",
        current_price=price,
        market_regime=regime,
        predictive_score=pred_score,
        quant_score=score,
        signal=sig,
        risk=risk,
        volume_profile=vp,
        metadata=metadata or {},
    )


def test_explain_buy_signal():
    service = SignalExplanationService()
    ctx = _make_context(
        action="BUY",
        direction="LONG",
        price=65000.0,
        poc=64000.0,
        metadata={"test_run": "alpha_1"},
    )

    explanation = service.explain(ctx)

    assert isinstance(explanation, AgentExplanation)
    assert "BUY signal identified for BTCUSDT (1h) with LONG bias at 65,000.00 under TRENDING_BULL regime." in explanation.summary
    assert "Quant Score of 85.0/100" in explanation.rationale
    assert "Predictive Score of 0.82" in explanation.rationale
    assert "established bullish trend" in explanation.rationale
    assert "trading above the high-volume node (POC at 64,000.00)" in explanation.rationale

    # Key drivers
    assert "EMA crossover" in explanation.key_drivers
    assert "Volume expansion" in explanation.key_drivers
    assert "Caution: Near resistance" in explanation.key_drivers

    # Risk assessment
    assert "Risk profile: Bajo." in explanation.risk_assessment
    assert "Protective Stop Loss set at 62,000.00." in explanation.risk_assessment
    assert "Target Take Profit set at 71,000.00." in explanation.risk_assessment
    assert "Risk/Reward ratio is calculated at 2.00." in explanation.risk_assessment
    assert "Local volatility measured by ATR is 1,500.00." in explanation.risk_assessment
    assert "Dynamic ATR bounds: 3.0x TP / 1.0x SL." in explanation.risk_assessment

    assert explanation.confidence == 0.88
    assert explanation.metadata["symbol"] == "BTCUSDT"
    assert explanation.metadata["action"] == "BUY"
    assert explanation.metadata["deterministic"] is True
    assert explanation.metadata["context_metadata"]["test_run"] == "alpha_1"



def test_explain_sell_signal():
    service = SignalExplanationService()
    ctx = _make_context(
        action="SELL",
        direction="SHORT",
        price=3200.0,
        regime="TRENDING_BEAR",
        score=35.0,
        pred_score=0.25,
        reasoning="Bearish breakdown below key level",
        positives=("Death cross",),
        warnings=(),
        stop_loss=3400.0,
        take_profit=2800.0,
        risk_ratio=2.0,
        risk_category="Medio",
        poc=3300.0,
    )

    explanation = service.explain(ctx)

    assert "SELL signal identified for BTCUSDT (1h) with SHORT bias at 3,200.00 under TRENDING_BEAR regime." in explanation.summary
    assert "established bearish trend with downward pressure dominant" in explanation.rationale
    assert "trading below the high-volume node (POC at 3,300.00)" in explanation.rationale
    assert "Protective Stop Loss set at 3,400.00." in explanation.risk_assessment
    assert "Target Take Profit set at 2,800.00." in explanation.risk_assessment


def test_explain_wait_signal():
    service = SignalExplanationService()
    ctx = _make_context(
        action="WAIT",
        direction="NEUTRAL",
        price=150.0,
        regime="RANGING_CONSOLIDATION",
        score=52.0,
        pred_score=0.48,
        reasoning="Range bound without clear momentum",
        positives=(),
        warnings=(),
        stop_loss=None,
        take_profit=None,
        risk_ratio=None,
        risk_category="Bajo",
        atr=4.0,
        tp_mult=None,
        sl_mult=None,
        poc=150.0,  # price == poc
    )

    explanation = service.explain(ctx)

    assert "WAIT condition for BTCUSDT (1h) at 150.00 under RANGING_CONSOLIDATION regime; awaiting clear market confirmation." in explanation.summary
    assert "consolidating in a range; caution is advised" in explanation.rationale
    assert "trading directly at the Point of Control (POC at 150.00)." in explanation.rationale
    assert "No explicit Stop Loss or Take Profit targets defined." in explanation.risk_assessment

    # Drivers fallback when no positives/warnings
    assert "Regime: RANGING_CONSOLIDATION" in explanation.key_drivers
    assert "Quant Score: 52.0/100" in explanation.key_drivers
    assert "Predictive Score: 0.48" in explanation.key_drivers


def test_explain_volatility_expansion_and_custom_regimes():
    service = SignalExplanationService()

    # Volatility expansion
    ctx_exp = _make_context(
        action="WAIT",
        regime="HIGH_VOLATILITY_EXPANSION",
        poc=None,
    )
    expl_exp = service.explain(ctx_exp)
    assert "volatility expansion with widening ranges" in expl_exp.rationale

    # Custom/unknown regime
    ctx_custom = _make_context(
        action="WAIT",
        regime="CUSTOM_CHOPPY_REGIME",
        reasoning="",
        poc=None,
    )
    expl_custom = service.explain(ctx_custom)
    assert "No explicit qualitative reason provided" in expl_custom.rationale
    assert "The market regime is categorized as CUSTOM_CHOPPY_REGIME." in expl_custom.rationale


def test_explain_missing_optional_fields():
    service = SignalExplanationService()
    ts = pd.Timestamp("2026-04-10 14:00:00")
    ctx = MarketContext(
        timestamp=ts,
        symbol="ETHUSDT",
        timeframe="15m",
        current_price=3000.0,
        market_regime="TRENDING_BULL",
        predictive_score=0.7,
        quant_score=75.0,
        signal=SignalInfo(action="BUY", direction="LONG", confidence=0.7),
        risk=RiskMetrics(),
    )

    explanation = service.explain(ctx)
    assert explanation.summary.startswith("BUY signal identified")
    assert "Risk profile: Standard." in explanation.risk_assessment
    assert "No explicit Stop Loss or Take Profit targets defined." in explanation.risk_assessment
    assert "Regime: TRENDING_BULL" in explanation.key_drivers


def test_explain_determinism():
    service = SignalExplanationService()
    ctx = _make_context()

    exp1 = service.explain(ctx)
    exp2 = service.explain(ctx)

    assert exp1.summary == exp2.summary
    assert exp1.rationale == exp2.rationale
    assert exp1.key_drivers == exp2.key_drivers
    assert exp1.risk_assessment == exp2.risk_assessment
    assert exp1.to_dict() == exp2.to_dict()


@pytest.mark.anyio
async def test_explain_async_without_provider():
    service = SignalExplanationService(provider=None)
    assert service.provider is None
    ctx = _make_context()

    explanation = await service.explain_async(ctx)
    assert "BUY signal identified" in explanation.summary
    assert explanation.metadata["service"] == "SignalExplanationService"


@pytest.mark.anyio
async def test_explain_async_with_provider():
    provider = MockAIProvider(name="mock-gemini")
    service = SignalExplanationService(provider=provider)
    assert service.provider is provider
    ctx = _make_context()

    explanation = await service.explain_async(ctx)
    assert explanation.metadata["provider"] == "mock-gemini"
    assert "mock-gemini" in explanation.metadata["provider"]
