from __future__ import annotations

from dataclasses import replace

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
    assert 'Query: "Analyze BTC right now"' in prompt


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
    assert (
        "[WARNING] BTC Volatility Expansion (+35%): ATR jumped from 900 to 1200"
        in prompt
    )


def test_prompt_builder_multimodal_single_and_multiple_images():
    builder = PromptBuilder()
    ctx = _create_sample_context()

    # Single image test
    prompt_single = builder.build_copilot_prompt(
        context=ctx,
        query="Analiza este gráfico",
        has_image=True,
        num_images=1,
    )
    assert "(1 imagen adjunta)" in prompt_single
    assert "El operador ha subido 1 captura(s)" in prompt_single
    assert "DIRECTIVAS ESTRICTAS DE VISIÓN" in prompt_single

    # Multiple images test
    prompt_multi = builder.build_copilot_prompt(
        context=ctx,
        query="Compara estos dos gráficos",
        has_image=True,
        num_images=3,
    )
    assert "(3 imágenes adjuntas)" in prompt_multi
    assert "El operador ha subido 3 captura(s)" in prompt_multi
    assert (
        "Si se adjuntaron múltiples imágenes, compáralas o relaciónalas" in prompt_multi
    )


def test_prompt_separates_verified_engine_levels_from_image_observations():
    ctx = _create_sample_context()
    ctx = replace(
        ctx,
        risk=replace(ctx.risk, risk_ratio=2.0),
        metadata={
            "signal_status": "CANDIDATA",
            "entry_confirmed": False,
            "entry_price": 64500.0,
            "risk_reward_ratio": 2.0,
        },
    )
    prompt = PromptBuilder().build_copilot_prompt(
        ctx, "La imagen muestra SL 61,000 y TP 70,000", has_image=True
    )
    verified_section = prompt.split(
        "Risk Parameters — VERIFIED BY RiskEngine ONLY:", 1
    )[1].split("DESCRIPTIVE TECHNICAL LEVELS", 1)[0]
    assert "Stop Loss: $63,000.00" in verified_section
    assert "Take Profit: $67,500.00" in verified_section
    assert "61,000" not in verified_section
    assert "70,000" not in verified_section
    assert "Engine Signal Action: WAIT" in prompt
    assert "entry confirmed: False" in prompt
    assert "OBSERVADOS, NO VERIFICADOS" in prompt
    assert "No transfieras niveles visuales al bloque de riesgo verificado" in prompt


def test_prompt_rejects_inverted_or_missing_levels_in_verified_section():
    ctx = _create_sample_context()
    for risk in (
        replace(ctx.risk, stop_loss=66000.0, risk_ratio=2.0),
        replace(ctx.risk, stop_loss=None, take_profit=None, atr=None, risk_ratio=None),
    ):
        prompt = PromptBuilder().build_copilot_prompt(
            replace(ctx, risk=risk, metadata={"signal_status": "NO DISPONIBLE"}),
            "Analiza el mercado",
            has_image=True,
        )
        section = prompt.split("Risk Parameters — VERIFIED BY RiskEngine ONLY:", 1)[
            1
        ].split("DESCRIPTIVE TECHNICAL LEVELS", 1)[0]
        assert "Stop Loss: None" in section
        assert "Take Profit: None" in section
        assert "Gross R:R without costs: N/A" in section
        assert "66,000" not in section
