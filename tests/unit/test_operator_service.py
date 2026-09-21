from __future__ import annotations

import pandas as pd
import pytest

from src.ai_agent.explanation import SignalExplanationService
from src.ai_agent.interfaces import MockAIProvider
from src.ai_agent.models import (
    MarketContext,
    RiskMetrics,
    SignalInfo,
)
from src.ai_agent.reporting import MarketReportGenerator
from src.operator_service.interfaces import (
    BaseMarketContextProvider,
    BaseOperatorService,
    InMemoryMarketContextProvider,
)
from src.operator_service.models import (
    MarketSummaryRequest,
    MarketSummaryResponse,
    OperatorServiceHealthResponse,
    SignalExplanationRequest,
    SignalExplanationResponse,
)
from src.operator_service.service import OperatorService


def _create_test_context(
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    action: str = "BUY",
    direction: str = "LONG",
    price: float = 64000.0,
    regime: str = "TRENDING_BULL",
) -> MarketContext:
    ts = pd.Timestamp("2026-04-12 12:00:00")
    return MarketContext(
        timestamp=ts,
        symbol=symbol,
        timeframe=timeframe,
        current_price=price,
        market_regime=regime,
        predictive_score=0.85,
        quant_score=88.0,
        signal=SignalInfo(
            action=action,
            direction=direction,
            confidence=0.9,
            reasoning="Bullish continuation with volume surge",
            positives=("Above EMA 200", "High Volume"),
            warnings=(),
        ),
        risk=RiskMetrics(
            stop_loss=62000.0,
            take_profit=70000.0,
            risk_ratio=3.0,
            risk_category="Bajo",
            atr=1000.0,
        ),
        volume_profile={"poc": 63500.0, "vah": 65000.0, "val": 62500.0},
    )


def test_models_normalization_and_serialization():
    req_expl = SignalExplanationRequest(symbol="  btcusdt  ", timeframe=" 1H ")
    assert req_expl.symbol == "BTCUSDT"
    assert req_expl.timeframe == "1h"
    d_req = req_expl.to_dict()
    assert d_req["symbol"] == "BTCUSDT"
    assert d_req["timeframe"] == "1h"

    res_expl = SignalExplanationResponse(
        success=False,
        symbol="BTCUSDT",
        timeframe="1h",
        error="Not found",
    )
    d_res = res_expl.to_dict()
    assert d_res["success"] is False
    assert d_res["explanation"] is None
    assert d_res["error"] == "Not found"

    req_sum = MarketSummaryRequest(symbol="ethusdt", timeframe="4H")
    assert req_sum.symbol == "ETHUSDT"
    assert req_sum.timeframe == "4h"
    assert req_sum.to_dict()["symbol"] == "ETHUSDT"

    res_sum = MarketSummaryResponse(
        success=False,
        symbol="ETHUSDT",
        timeframe="4h",
        error="Missing",
    )
    d_sum = res_sum.to_dict()
    assert d_sum["success"] is False
    assert d_sum["summary"] is None

    health = OperatorServiceHealthResponse(status="HEALTHY", available_symbols=["BTCUSDT"])
    d_health = health.to_dict()
    assert d_health["status"] == "HEALTHY"
    assert d_health["available_symbols"] == ["BTCUSDT"]


def test_abstract_interfaces_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseMarketContextProvider()  # type: ignore[abstract]

    with pytest.raises(TypeError):
        BaseOperatorService()  # type: ignore[abstract]


@pytest.mark.anyio
async def test_in_memory_context_provider():
    provider = InMemoryMarketContextProvider()
    assert await provider.get_available_symbols() == []
    assert await provider.get_latest_context("BTCUSDT", "1h") is None

    ctx_btc = _create_test_context(symbol="BTCUSDT", timeframe="1h")
    ctx_eth = _create_test_context(symbol="ETHUSDT", timeframe="4h")

    provider.update_context(ctx_btc)
    provider.update_context(ctx_eth)

    assert await provider.get_available_symbols() == ["BTCUSDT", "ETHUSDT"]

    # Case-insensitive lookup
    retrieved = await provider.get_latest_context("btcusdt", "1H")
    assert retrieved is not None
    assert retrieved.symbol == "BTCUSDT"
    assert retrieved.current_price == 64000.0

    missing = await provider.get_latest_context("SOLUSDT", "1h")
    assert missing is None


@pytest.mark.anyio
async def test_operator_service_signal_explanation_success_and_missing():
    provider = InMemoryMarketContextProvider()
    ctx = _create_test_context(symbol="BTCUSDT", timeframe="1h")
    provider.update_context(ctx)

    service = OperatorService(context_provider=provider)
    assert service.context_provider is provider

    # Success retrieval
    req = SignalExplanationRequest(symbol="BTCUSDT", timeframe="1h")
    resp = await service.get_signal_explanation(req)

    assert resp.success is True
    assert resp.symbol == "BTCUSDT"
    assert resp.timeframe == "1h"
    assert resp.error is None
    assert resp.explanation is not None
    assert "BUY signal identified for BTCUSDT" in resp.explanation.summary

    # Missing symbol
    req_missing = SignalExplanationRequest(symbol="SOLUSDT", timeframe="1h")
    resp_missing = await service.get_signal_explanation(req_missing)

    assert resp_missing.success is False
    assert resp_missing.explanation is None
    assert "No quantitative context found for SOLUSDT (1h)." in resp_missing.error  # type: ignore[operator]


@pytest.mark.anyio
async def test_operator_service_market_summary_success_and_missing():
    provider = InMemoryMarketContextProvider()
    ctx = _create_test_context(symbol="ETHUSDT", timeframe="4h")
    provider.update_context(ctx)

    service = OperatorService(context_provider=provider)

    req = MarketSummaryRequest(symbol="ETHUSDT", timeframe="4h")
    resp = await service.get_market_summary(req)

    assert resp.success is True
    assert resp.symbol == "ETHUSDT"
    assert resp.timeframe == "4h"
    assert resp.error is None
    assert resp.summary is not None
    assert "ETHUSDT Market Intelligence Report (4h)" == resp.summary.title

    # Missing timeframe
    req_missing = MarketSummaryRequest(symbol="ETHUSDT", timeframe="15m")
    resp_missing = await service.get_market_summary(req_missing)

    assert resp_missing.success is False
    assert resp_missing.summary is None
    assert "No quantitative context found for ETHUSDT (15m)." in resp_missing.error  # type: ignore[operator]


@pytest.mark.anyio
async def test_operator_service_health_check():
    provider = InMemoryMarketContextProvider()
    provider.update_context(_create_test_context(symbol="BTCUSDT", timeframe="1h"))
    provider.update_context(_create_test_context(symbol="SOLUSDT", timeframe="1h"))

    service = OperatorService(context_provider=provider)
    health = await service.health_check()

    assert health.status == "HEALTHY"
    assert health.available_symbols == ["BTCUSDT", "SOLUSDT"]
    assert isinstance(health.timestamp, str)


@pytest.mark.anyio
async def test_operator_service_read_only_and_deterministic():
    provider = InMemoryMarketContextProvider()
    ctx = _create_test_context(symbol="BTCUSDT", timeframe="1h", price=64000.0)
    provider.update_context(ctx)

    service = OperatorService(context_provider=provider)

    req_expl = SignalExplanationRequest(symbol="BTCUSDT", timeframe="1h")
    resp1 = await service.get_signal_explanation(req_expl)
    resp2 = await service.get_signal_explanation(req_expl)

    # Determinism
    assert resp1.explanation is not None and resp2.explanation is not None
    assert resp1.explanation.summary == resp2.explanation.summary
    assert resp1.explanation.rationale == resp2.explanation.rationale

    # Read-only verification: context in provider is still identical
    stored_ctx = await provider.get_latest_context("BTCUSDT", "1h")
    assert stored_ctx is not None
    assert stored_ctx.current_price == 64000.0
    assert stored_ctx.quant_score == 88.0
    assert stored_ctx.signal.action == "BUY"


@pytest.mark.anyio
async def test_operator_service_custom_providers_injection():
    mock_provider = MockAIProvider(name="custom-operator-mock")
    expl_service = SignalExplanationService(provider=mock_provider)
    report_gen = MarketReportGenerator(provider=mock_provider)

    provider = InMemoryMarketContextProvider()
    ctx = _create_test_context(symbol="BTCUSDT", timeframe="1h")
    provider.update_context(ctx)

    service = OperatorService(
        context_provider=provider,
        explanation_service=expl_service,
        report_generator=report_gen,
    )

    resp_expl = await service.get_signal_explanation(
        SignalExplanationRequest(symbol="BTCUSDT", timeframe="1h")
    )
    assert resp_expl.success is True
    assert resp_expl.explanation is not None
    assert resp_expl.explanation.metadata["provider"] == "custom-operator-mock"

    resp_sum = await service.get_market_summary(
        MarketSummaryRequest(symbol="BTCUSDT", timeframe="1h")
    )
    assert resp_sum.success is True
    assert resp_sum.summary is not None
    assert resp_sum.summary.metadata["provider"] == "custom-operator-mock"
