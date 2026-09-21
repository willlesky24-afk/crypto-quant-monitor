from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.ai_agent.models import MarketContext, RiskMetrics, SignalInfo
from src.operator_api.app import create_app
from src.operator_api.config import APISecurityConfig
from src.operator_api.dependencies import (
    reset_operator_service,
    reset_security_config,
    set_operator_service,
    set_security_config,
)
from src.operator_service.interfaces import InMemoryMarketContextProvider
from src.operator_service.service import OperatorService


def _create_sample_context() -> MarketContext:
    return MarketContext(
        timestamp=pd.Timestamp("2026-09-20 12:00:00", tz="UTC"),
        symbol="BTCUSDT",
        timeframe="1h",
        current_price=64000.0,
        market_regime="TRENDING_BULL",
        predictive_score=0.82,
        quant_score=85.0,
        signal=SignalInfo(
            action="BUY",
            direction="LONG",
            confidence=0.88,
            reasoning="Momentum expansion",
        ),
        risk=RiskMetrics(
            stop_loss=62000.0,
            take_profit=68000.0,
            risk_ratio=2.0,
            risk_category="LOW",
            atr=1000.0,
        ),
        technical_indicators={"volume": 50000.0},
        volume_profile={"poc": 63500.0},
    )


@pytest.fixture(autouse=True)
def clean_api_state():
    reset_operator_service()
    reset_security_config()
    yield
    reset_operator_service()
    reset_security_config()


@pytest.mark.anyio
async def test_copilot_query_api_endpoint():
    provider = InMemoryMarketContextProvider()
    provider.update_context(_create_sample_context())
    service = OperatorService(context_provider=provider)
    set_operator_service(service)

    # Disable auth for test
    set_security_config(APISecurityConfig(security_enabled=False, rate_limit_enabled=False))

    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/copilot/query",
        json={"query": "Analyze BTCUSDT right now", "symbol": "BTCUSDT", "timeframe": "1h"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["response"]["symbol"] == "BTCUSDT"
    assert "Copilot Intelligence" in data["response"]["answer"]
    assert "DECISION SUPPORT ONLY" in data["response"]["disclaimer"]


@pytest.mark.anyio
async def test_copilot_reports_endpoints():
    provider = InMemoryMarketContextProvider()
    provider.update_context(_create_sample_context())
    service = OperatorService(context_provider=provider)
    set_operator_service(service)
    set_security_config(APISecurityConfig(security_enabled=False, rate_limit_enabled=False))

    app = create_app()
    client = TestClient(app)

    # Daily Briefing
    res_daily = client.get("/copilot/reports/daily?symbol=BTCUSDT&timeframe=1h")
    assert res_daily.status_code == 200
    daily_data = res_daily.json()
    assert daily_data["symbol"] == "BTCUSDT"
    assert "market_overview" in daily_data

    # Intraday Update
    res_intra = client.get("/copilot/reports/intraday?symbol=BTCUSDT&timeframe=1h")
    assert res_intra.status_code == 200
    intra_data = res_intra.json()
    assert intra_data["symbol"] == "BTCUSDT"
    assert "what_changed" in intra_data

    # 404 for unknown asset
    res_404 = client.get("/copilot/reports/daily?symbol=UNKNOWN&timeframe=1h")
    assert res_404.status_code == 404


@pytest.mark.anyio
async def test_copilot_anomalies_and_memory_endpoints():
    provider = InMemoryMarketContextProvider()
    provider.update_context(_create_sample_context())
    service = OperatorService(context_provider=provider)
    set_operator_service(service)
    set_security_config(APISecurityConfig(security_enabled=False, rate_limit_enabled=False))

    app = create_app()
    client = TestClient(app)

    # Anomalies
    res_alt = client.get("/copilot/anomalies?symbol=BTCUSDT&timeframe=1h")
    assert res_alt.status_code == 200
    assert isinstance(res_alt.json(), list)

    # Memory entries
    res_mem = client.get("/copilot/memory?symbol=BTCUSDT")
    assert res_mem.status_code == 200
    assert isinstance(res_mem.json(), list)
