from __future__ import annotations

import pandas as pd
import pytest

from src.ai_agent.interfaces import MockAIProvider
from src.ai_agent.models import MarketContext, RiskMetrics, SignalInfo
from src.operator_assistant.assistant import OperatorAssistant
from src.operator_assistant.models import (
    AnalysisRequest,
    AnalysisResponse,
    OperatorQuery,
    OperatorResponse,
)
from src.operator_service.interfaces import InMemoryMarketContextProvider


def _create_sample_context(
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    regime: str = "TRENDING_BULL",
    quant_score: float = 85.0,
    predictive_score: float = 0.82,
    action: str = "BUY",
    direction: str = "LONG",
) -> MarketContext:
    return MarketContext(
        timestamp=pd.Timestamp("2026-09-20 12:00:00", tz="UTC"),
        symbol=symbol,
        timeframe=timeframe,
        current_price=64250.0,
        market_regime=regime,
        predictive_score=predictive_score,
        quant_score=quant_score,
        signal=SignalInfo(
            action=action,
            direction=direction,
            confidence=0.88,
            reasoning="High momentum with RSI expansion.",
            positives=("EMA alignment bullish", "Volume confirmation"),
            warnings=("Approaching local resistance",),
        ),
        risk=RiskMetrics(
            stop_loss=62500.0,
            take_profit=68000.0,
            risk_ratio=2.14,
            risk_category="LOW",
            atr=1250.0,
        ),
        technical_indicators={"rsi": 68.5, "adx": 32.1},
        volume_profile={"poc": 63900.0, "vah": 64800.0, "val": 63200.0},
    )


@pytest.mark.anyio
async def test_operator_query_and_response_models():
    q = OperatorQuery(query="Analyze BTCUSDT", symbol="BTCUSDT")
    d = q.to_dict()
    assert d["query"] == "Analyze BTCUSDT"
    assert d["symbol"] == "BTCUSDT"

    r = OperatorResponse(
        answer="Analysis text",
        symbol="BTCUSDT",
        timeframe="1h",
        market_regime="TRENDING_BULL",
        quant_score=85.0,
        predictive_score=0.82,
        confidence=0.88,
        key_drivers=("EMA alignment",),
        risk_factors=("Resistance",),
        scenarios=("Bullish continuation",),
    )
    rd = r.to_dict()
    assert rd["symbol"] == "BTCUSDT"
    assert "DECISION SUPPORT ONLY" in r.disclaimer
    assert len(rd["key_drivers"]) == 1


@pytest.mark.anyio
async def test_analysis_request_and_response_models():
    req = AnalysisRequest(symbol="ETHUSDT", timeframe="4h")
    assert req.to_dict()["symbol"] == "ETHUSDT"

    res = AnalysisResponse(
        symbol="ETHUSDT",
        timeframe="4h",
        current_price=3500.0,
        market_regime="CONSOLIDATION",
        quant_score=55.0,
        predictive_score=0.52,
        technical_summary="Neutral",
        volume_analysis="Balanced",
        risk_assessment="Moderate",
        possible_scenarios=("Range bounce",),
    )
    assert res.to_dict()["current_price"] == 3500.0


@pytest.mark.anyio
async def test_operator_assistant_ask_success():
    provider = InMemoryMarketContextProvider()
    ctx = _create_sample_context()
    provider.update_context(ctx)

    assistant = OperatorAssistant(context_provider=provider, ai_provider=MockAIProvider())
    assert assistant.context_provider is provider
    assert isinstance(assistant.ai_provider, MockAIProvider)

    query = OperatorQuery(query="What is the current BTC status?", symbol="BTCUSDT", timeframe="1h")
    response = await assistant.ask(query)

    assert response.symbol == "BTCUSDT"
    assert response.market_regime == "TRENDING_BULL"
    assert response.quant_score == 85.0
    assert response.predictive_score == 0.82
    assert "Copilot Intelligence" in response.answer
    assert len(response.scenarios) > 0
    assert "DECISION SUPPORT ONLY" in response.disclaimer
    assert "🏁 Conclusión Operativa y Veredicto Técnico" in response.answer
    assert "Respuesta técnica" in response.answer
    assert "Parámetros de Riesgo Sugeridos" in response.answer
    assert "Stop Loss (Corte de pérdida)" in response.answer
    assert "Take Profit (Toma de beneficio)" in response.answer


@pytest.mark.anyio
async def test_operator_assistant_ask_no_context():
    provider = InMemoryMarketContextProvider()
    assistant = OperatorAssistant(context_provider=provider, enable_on_demand_context=False)

    query = OperatorQuery(query="Analyze SOLUSDT", symbol="SOLUSDT", timeframe="15m")
    response = await assistant.ask(query)

    assert response.symbol == "SOLUSDT"
    assert response.market_regime == "UNKNOWN"
    assert "No closed-candle quantitative context is currently available" in response.answer


@pytest.mark.anyio
async def test_operator_assistant_token_extraction_and_scenarios():
    provider = InMemoryMarketContextProvider()
    # Bearish context
    ctx = _create_sample_context(
        symbol="ETHUSDT", timeframe="4h", regime="TRENDING_BEAR", predictive_score=0.25, action="SELL", direction="SHORT"
    )
    provider.update_context(ctx)

    assistant = OperatorAssistant(context_provider=provider)
    query = OperatorQuery(query="Tell me about ETHUSDT on 4h", symbol="BTCUSDT", timeframe="1h")
    response = await assistant.ask(query)

    assert response.symbol == "ETHUSDT"
    assert response.timeframe == "4h"
    assert "Bearish Continuation" in response.scenarios[0]


@pytest.mark.anyio
async def test_operator_assistant_consolidation_scenarios():
    provider = InMemoryMarketContextProvider()
    ctx = _create_sample_context(
        symbol="ADAUSDT", timeframe="1h", regime="CHOPPY_RANGE", predictive_score=0.50, action="WAIT", direction="NEUTRAL"
    )
    provider.update_context(ctx)

    assistant = OperatorAssistant(context_provider=provider)
    query = OperatorQuery(query="ADAUSDT 1h update", symbol="ADAUSDT", timeframe="1h")
    response = await assistant.ask(query)

    assert "Range Bound" in response.scenarios[0]


@pytest.mark.anyio
async def test_operator_assistant_no_drivers():
    provider = InMemoryMarketContextProvider()
    ctx = MarketContext(
        timestamp=pd.Timestamp("2026-09-20 12:00:00", tz="UTC"),
        symbol="DOTUSDT",
        timeframe="1h",
        current_price=10.0,
        market_regime="CONSOLIDATION",
        predictive_score=0.50,
        quant_score=50.0,
        signal=SignalInfo(
            action="WAIT",
            direction="NEUTRAL",
            confidence=0.50,
            positives=(),
            warnings=(),
        ),
        risk=RiskMetrics(),
    )
    provider.update_context(ctx)


    # Test custom AI provider returning empty key_drivers

    from src.ai_agent.interfaces import BaseAIProvider
    from src.ai_agent.models import AgentExplanation, AgentMarketSummary

    class EmptyDriverAIProvider(BaseAIProvider):
        async def generate_explanation(self, context: MarketContext) -> AgentExplanation:
            return AgentExplanation(summary="test", rationale="test", key_drivers=())

        async def summarize_market(self, context: MarketContext) -> AgentMarketSummary:
            return AgentMarketSummary(title="t", overview="o", regime_interpretation="r", outlook="out")

        async def health_check(self) -> bool:
            return True

    assistant_custom = OperatorAssistant(context_provider=provider, ai_provider=EmptyDriverAIProvider())
    res_custom = await assistant_custom.ask(OperatorQuery(query="Analyze DOT", symbol="DOTUSDT"))
    assert "Regime: CONSOLIDATION" in res_custom.key_drivers
    assert "Quant Score: 50.0" in res_custom.key_drivers




@pytest.mark.anyio
async def test_operator_assistant_deep_analyze():
    provider = InMemoryMarketContextProvider()
    ctx = _create_sample_context()
    provider.update_context(ctx)

    assistant = OperatorAssistant(context_provider=provider)
    req = AnalysisRequest(symbol="BTCUSDT", timeframe="1h")
    res = await assistant.analyze(req)

    assert res.symbol == "BTCUSDT"
    assert res.current_price == 64250.0
    assert "POC: 63900.0" in res.volume_analysis
    assert "rsi: 68.50" in res.technical_summary


@pytest.mark.anyio
async def test_operator_assistant_deep_analyze_missing():
    provider = InMemoryMarketContextProvider()
    assistant = OperatorAssistant(context_provider=provider)
    req = AnalysisRequest(symbol="XRPUSDT", timeframe="1h")
    res = await assistant.analyze(req)

    assert res.current_price == 0.0
    assert "No data available" in res.technical_summary


def test_resolve_mentioned_symbol():
    from src.operator_assistant.on_demand_context import resolve_mentioned_symbol

    # Forex tests
    sym, tf, is_fx = resolve_mentioned_symbol("USDCAD, me conviene entrar a comprar?", "EURUSD=X", "1h")
    assert sym == "USDCAD=X"
    assert tf == "1h"
    assert is_fx is True

    sym, tf, is_fx = resolve_mentioned_symbol("Que opinas de USD/JPY en 15m?", "BTCUSDT", "1h")
    assert sym == "USDJPY=X"
    assert tf == "15m"
    assert is_fx is True

    # Crypto tests
    sym, tf, is_fx = resolve_mentioned_symbol("Cual es la proyeccion de SOL?", "BTCUSDT", "1h")
    assert sym == "SOLUSDT"
    assert is_fx is False

    sym, tf, is_fx = resolve_mentioned_symbol("Como ves ETH en 4h?", "BTCUSDT", "1h")
    assert sym == "ETHUSDT"
    assert tf == "4h"
    assert is_fx is False

    # Fallback test
    sym, tf, is_fx = resolve_mentioned_symbol("Cual es el riesgo general?", "EURUSD=X", "1h")
    assert sym == "EURUSD=X"
    assert is_fx is True


@pytest.mark.anyio
async def test_operator_assistant_conclusive_verdict_coherence_wait_signal():
    """Verify that when action is WAIT despite bullish regime, the verdict does NOT say 'Sí'."""
    provider = InMemoryMarketContextProvider()
    ctx = MarketContext(
        timestamp=pd.Timestamp("2026-09-22 18:00:00", tz="UTC"),
        symbol="USDCAD=X",
        timeframe="1h",
        current_price=1.4081,
        market_regime="TRENDING_BULL",
        predictive_score=0.65,
        quant_score=75.0,
        signal=SignalInfo(
            action="WAIT",
            direction="LONG",
            confidence=0.502,
            reasoning="Contexto débil",
            warnings=("Momentum débil", "Volumen sin confirmación"),
        ),
        risk=RiskMetrics(
            stop_loss=None,
            take_profit=None,
            atr=0.0020,
        ),
    )
    provider.update_context(ctx)

    assistant = OperatorAssistant(context_provider=provider, ai_provider=MockAIProvider())
    query = OperatorQuery(query="USDCAD, me conviene entrar a comprar?", symbol="USDCAD=X", timeframe="1h")
    res = await assistant.ask(query)

    # Coherence check: MUST NOT say 'Sí, el sesgo matemático favorece las compras'
    assert "Sí, el sesgo matemático favorece las compras" not in res.answer
    assert "En Espera / Precaución (NO entrar ahora)" in res.answer
    assert "Momentum débil" in res.answer
    # Concrete risk numbers check: MUST NOT say 'No especificado'
    assert "No especificado" not in res.answer
    assert "Stop Loss (Corte de pérdida)" in res.answer
    assert "Take Profit (Toma de beneficio)" in res.answer
