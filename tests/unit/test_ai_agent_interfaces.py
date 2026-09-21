from __future__ import annotations

import pandas as pd
import pytest

from src.ai_agent.interfaces import BaseAIProvider, MockAIProvider
from src.ai_agent.models import (
    AgentExplanation,
    AgentMarketSummary,
    MarketContext,
    RiskMetrics,
    SignalInfo,
)


def _create_sample_context(
    action: str = "BUY",
    direction: str = "LONG",
    regime: str = "TRENDING_BULL",
    score: float = 85.0,
    pred_score: float = 0.8,
    positives: tuple[str, ...] = ("EMA alignment", "Above POC"),
    warnings: tuple[str, ...] = ("RSI elevated",),
) -> MarketContext:
    ts = pd.Timestamp("2026-04-01 12:00:00")
    sig = SignalInfo(
        action=action,
        direction=direction,
        confidence=0.85,
        reasoning="Trend confirmed by volume",
        positives=positives,
        warnings=warnings,
    )
    risk = RiskMetrics(
        stop_loss=60000.0,
        take_profit=66000.0,
        risk_ratio=3.0,
        risk_category="Bajo",
        atr=1000.0,
    )
    return MarketContext(
        timestamp=ts,
        symbol="BTCUSDT",
        timeframe="1h",
        current_price=62000.0,
        market_regime=regime,
        predictive_score=pred_score,
        quant_score=score,
        signal=sig,
        risk=risk,
        volume_profile={"poc": 61500.0, "vah": 63000.0, "val": 60500.0},
    )


def test_base_ai_provider_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        BaseAIProvider()  # type: ignore[abstract]


@pytest.mark.anyio
async def test_mock_ai_provider_generate_explanation_buy_signal():
    provider = MockAIProvider(name="test-mock")
    ctx = _create_sample_context(action="BUY", direction="LONG")

    explanation = await provider.generate_explanation(ctx)

    assert isinstance(explanation, AgentExplanation)
    assert "BUY signal identified for BTCUSDT on 1h with LONG bias" in explanation.summary
    assert "TRENDING_BULL" in explanation.summary
    assert "Quant Score of 85.0/100" in explanation.rationale
    assert "Predictive Score of 0.80" in explanation.rationale
    assert "EMA alignment" in explanation.key_drivers
    assert "Above POC" in explanation.key_drivers
    assert "Stop Loss at 60,000.00" in explanation.risk_assessment
    assert "Take Profit at 66,000.00" in explanation.risk_assessment
    assert "Risk/Reward ratio: 3.00" in explanation.risk_assessment
    assert explanation.confidence == 0.85
    assert explanation.metadata["provider"] == "test-mock"
    assert explanation.metadata["deterministic"] is True


@pytest.mark.anyio
async def test_mock_ai_provider_generate_explanation_wait_signal():
    provider = MockAIProvider(name="test-mock")
    ctx = _create_sample_context(
        action="WAIT",
        direction="NEUTRAL",
        regime="RANGING_CONSOLIDATION",
        score=50.0,
        pred_score=0.45,
        positives=(),
    )

    explanation = await provider.generate_explanation(ctx)

    assert "Neutral/Wait condition for BTCUSDT on 1h under RANGING_CONSOLIDATION regime" in explanation.summary
    assert "Quant Score of 50.0/100" in explanation.rationale
    assert "Predictive Score of 0.45" in explanation.rationale
    assert "Regime: RANGING_CONSOLIDATION" in explanation.key_drivers
    assert "Score: 50.0" in explanation.key_drivers


@pytest.mark.anyio
async def test_mock_ai_provider_summarize_market():
    provider = MockAIProvider(name="test-mock")
    ctx = _create_sample_context()

    summary = await provider.summarize_market(ctx)

    assert isinstance(summary, AgentMarketSummary)
    assert "BTCUSDT Market Intelligence Briefing (1h)" == summary.title
    assert "BTCUSDT is trading at 62,000.00 in a TRENDING_BULL environment." in summary.overview
    assert "Action status: BUY (LONG)" in summary.overview or "BUY" in summary.overview
    assert "TRENDING_BULL" in summary.regime_interpretation
    assert summary.key_levels["POC"] == 61500.0
    assert summary.key_levels["VAH"] == 63000.0
    assert summary.key_levels["VAL"] == 60500.0
    assert summary.key_levels["StopLoss"] == 60000.0
    assert summary.key_levels["TakeProfit"] == 66000.0


@pytest.mark.anyio
async def test_mock_ai_provider_health_check():
    healthy_provider = MockAIProvider(is_healthy=True)
    assert await healthy_provider.health_check() is True

    unhealthy_provider = MockAIProvider(is_healthy=False)
    assert await unhealthy_provider.health_check() is False


@pytest.mark.anyio
async def test_mock_ai_provider_determinism():
    provider = MockAIProvider()
    ctx = _create_sample_context()

    exp1 = await provider.generate_explanation(ctx)
    exp2 = await provider.generate_explanation(ctx)

    assert exp1.summary == exp2.summary
    assert exp1.rationale == exp2.rationale
    assert exp1.key_drivers == exp2.key_drivers
    assert exp1.risk_assessment == exp2.risk_assessment
    assert exp1.to_dict() == exp2.to_dict()
