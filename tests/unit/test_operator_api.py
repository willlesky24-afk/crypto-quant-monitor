from __future__ import annotations

import httpx
import pandas as pd
import pytest

from src.ai_agent.models import (
    MarketContext,
    RiskMetrics,
    SignalInfo,
)
from src.operator_api.app import create_app
from src.operator_api.dependencies import (
    get_operator_service,
    reset_operator_service,
    set_operator_service,
)
from src.operator_service.interfaces import InMemoryMarketContextProvider
from src.operator_service.service import OperatorService


def _create_sample_context(
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    price: float = 67000.0,
    action: str = "BUY",
    direction: str = "LONG",
) -> MarketContext:
    ts = pd.Timestamp("2026-04-15 10:00:00")
    sig = SignalInfo(
        action=action,
        direction=direction,
        confidence=0.92,
        reasoning="Strong momentum breakout",
        positives=("EMA bullish fan", "Volume surge"),
        warnings=(),
    )
    risk = RiskMetrics(
        stop_loss=64000.0,
        take_profit=73000.0,
        risk_ratio=2.0,
        risk_category="Bajo",
        atr=1500.0,
    )
    return MarketContext(
        timestamp=ts,
        symbol=symbol,
        timeframe=timeframe,
        current_price=price,
        market_regime="TRENDING_BULL",
        predictive_score=0.88,
        quant_score=86.0,
        signal=sig,
        risk=risk,
        volume_profile={"poc": 66000.0, "vah": 68000.0, "val": 65000.0},
    )


@pytest.fixture(autouse=True)
def cleanup_operator_service():
    """Reset dependency state before and after each test."""
    reset_operator_service()
    yield
    reset_operator_service()


@pytest.mark.anyio
async def test_health_endpoint():
    provider = InMemoryMarketContextProvider()
    provider.update_context(_create_sample_context(symbol="BTCUSDT"))
    provider.update_context(_create_sample_context(symbol="ETHUSDT", timeframe="4h"))

    service = OperatorService(context_provider=provider)
    app = create_app(service=service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "HEALTHY"
        assert sorted(data["available_symbols"]) == ["BTCUSDT", "ETHUSDT"]
        assert "timestamp" in data


@pytest.mark.anyio
async def test_get_latest_signal_explanation_success():
    provider = InMemoryMarketContextProvider()
    ctx = _create_sample_context(symbol="BTCUSDT", timeframe="1h", price=67000.0)
    provider.update_context(ctx)

    service = OperatorService(context_provider=provider)
    app = create_app(service=service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/signals/latest?symbol=btcusdt&timeframe=1H")
        assert resp.status_code == 200
        data = resp.json()

        assert data["success"] is True
        assert data["symbol"] == "BTCUSDT"
        assert data["timeframe"] == "1h"
        assert "explanation" in data

        expl = data["explanation"]
        assert "BUY signal identified for BTCUSDT" in expl["summary"]
        assert "Quant Score of 86.0/100" in expl["rationale"]
        assert "EMA bullish fan" in expl["key_drivers"]
        assert "Protective Stop Loss set at 64,000.00." in expl["risk_assessment"]
        assert expl["confidence"] == 0.92


@pytest.mark.anyio
async def test_get_latest_signal_explanation_not_found():
    provider = InMemoryMarketContextProvider()
    service = OperatorService(context_provider=provider)
    app = create_app(service=service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/signals/latest?symbol=SOLUSDT&timeframe=1h")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data
        assert "No quantitative context found for SOLUSDT (1h)" in data["detail"]


@pytest.mark.anyio
async def test_get_market_summary_success():
    provider = InMemoryMarketContextProvider()
    ctx = _create_sample_context(symbol="ETHUSDT", timeframe="4h", price=3500.0)
    provider.update_context(ctx)

    service = OperatorService(context_provider=provider)
    app = create_app(service=service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/market/summary?symbol=ethusdt&timeframe=4h")
        assert resp.status_code == 200
        data = resp.json()

        assert data["success"] is True
        assert data["symbol"] == "ETHUSDT"
        assert data["timeframe"] == "4h"

        summary = data["summary"]
        assert summary["title"] == "ETHUSDT Market Intelligence Report (4h)"
        assert "ETHUSDT is trading at 3,500.00" in summary["overview"]
        assert "Bullish trend regime identified" in summary["regime_interpretation"]
        assert "key_levels" in summary
        assert summary["key_levels"]["CurrentPrice"] == 3500.0


@pytest.mark.anyio
async def test_get_market_summary_not_found():
    provider = InMemoryMarketContextProvider()
    service = OperatorService(context_provider=provider)
    app = create_app(service=service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/market/summary?symbol=AVAXUSDT&timeframe=15m")
        assert resp.status_code == 404
        data = resp.json()
        assert "No quantitative context found for AVAXUSDT (15m)" in data["detail"]


@pytest.mark.anyio
async def test_no_mutation_of_underlying_context():
    provider = InMemoryMarketContextProvider()
    ctx = _create_sample_context(symbol="BTCUSDT", price=67000.0)
    provider.update_context(ctx)

    service = OperatorService(context_provider=provider)
    app = create_app(service=service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Multiple requests to endpoints
        await client.get("/signals/latest?symbol=BTCUSDT&timeframe=1h")
        await client.get("/market/summary?symbol=BTCUSDT&timeframe=1h")
        await client.get("/health")

    # Verify context in provider remains identical
    stored = await provider.get_latest_context("BTCUSDT", "1h")
    assert stored is not None
    assert stored.current_price == 67000.0
    assert stored.quant_score == 86.0
    assert stored.signal.action == "BUY"


def test_dependency_provider_singleton_and_override():
    reset_operator_service()
    s1 = get_operator_service()
    s2 = get_operator_service()
    assert s1 is s2

    custom_provider = InMemoryMarketContextProvider()
    custom_service = OperatorService(context_provider=custom_provider)
    set_operator_service(custom_service)
    assert get_operator_service() is custom_service
