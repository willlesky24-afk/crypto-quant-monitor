from __future__ import annotations

import httpx
import pandas as pd
import pytest
from starlette.requests import Request

from src.ai_agent.models import MarketContext, RiskMetrics, SignalInfo
from src.operator_api.app import create_app
from src.operator_api.config import APISecurityConfig
from src.operator_api.dependencies import (
    reset_operator_service,
    reset_security_config,
)
from src.operator_api.security import (
    InMemoryRateLimiter,
    SecurityGuard,
    get_client_identifier,
)
from src.operator_service.interfaces import InMemoryMarketContextProvider
from src.operator_service.service import OperatorService


def _create_sample_context(
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
) -> MarketContext:
    ts = pd.Timestamp("2026-04-20 12:00:00")
    return MarketContext(
        timestamp=ts,
        symbol=symbol,
        timeframe=timeframe,
        current_price=65000.0,
        market_regime="TRENDING_BULL",
        predictive_score=0.8,
        quant_score=85.0,
        signal=SignalInfo(
            action="BUY",
            direction="LONG",
            confidence=0.9,
            reasoning="Trend confirmed",
            positives=("Above EMA",),
            warnings=(),
        ),
        risk=RiskMetrics(
            stop_loss=63000.0,
            take_profit=69000.0,
            risk_ratio=2.0,
            risk_category="Bajo",
            atr=1000.0,
        ),
        volume_profile={"poc": 64500.0, "vah": 66000.0, "val": 63500.0},
    )


@pytest.fixture(autouse=True)
def cleanup_state():
    reset_operator_service()
    reset_security_config()
    yield
    reset_operator_service()
    reset_security_config()


def test_api_security_config_from_env(monkeypatch):
    # Test with custom environment variables
    monkeypatch.setenv("OPERATOR_API_KEY", "secret-test-key-123")
    monkeypatch.setenv("OPERATOR_API_SECURITY_ENABLED", "true")
    monkeypatch.setenv("OPERATOR_API_RATE_LIMIT_PER_MINUTE", "120")
    monkeypatch.setenv("OPERATOR_API_RATE_LIMIT_ENABLED", "yes")
    monkeypatch.setenv("OPERATOR_API_CORS_ORIGINS", "https://app.cryptoquant.com, https://localhost:3000")
    monkeypatch.setenv("OPERATOR_API_REQUIRE_AUTH_FOR_HEALTH", "1")

    cfg = APISecurityConfig.from_env()

    assert cfg.api_key == "secret-test-key-123"
    assert cfg.security_enabled is True
    assert cfg.rate_limit_per_minute == 120
    assert cfg.rate_limit_enabled is True
    assert cfg.cors_origins == ("https://app.cryptoquant.com", "https://localhost:3000")
    assert cfg.require_auth_for_health is True


def test_api_security_config_from_env_defaults_and_fallbacks(monkeypatch):
    monkeypatch.delenv("OPERATOR_API_KEY", raising=False)
    monkeypatch.delenv("OPERATOR_API_SECURITY_ENABLED", raising=False)
    monkeypatch.delenv("OPERATOR_API_RATE_LIMIT_PER_MINUTE", raising=False)
    monkeypatch.delenv("OPERATOR_API_RATE_LIMIT_ENABLED", raising=False)
    monkeypatch.delenv("OPERATOR_API_CORS_ORIGINS", raising=False)
    monkeypatch.delenv("OPERATOR_API_REQUIRE_AUTH_FOR_HEALTH", raising=False)

    cfg = APISecurityConfig.from_env()
    assert cfg.api_key is None
    assert cfg.security_enabled is False
    assert cfg.rate_limit_per_minute == 60
    assert cfg.rate_limit_enabled is False
    assert cfg.cors_origins == ("*",)
    assert cfg.require_auth_for_health is False

    # Invalid rate limit integer fallback
    monkeypatch.setenv("OPERATOR_API_RATE_LIMIT_PER_MINUTE", "invalid_number")
    cfg_invalid = APISecurityConfig.from_env()
    assert cfg_invalid.rate_limit_per_minute == 60


def test_rate_limiter_logic():
    limiter = InMemoryRateLimiter(limit_per_minute=3)
    key = "test-client"

    # First 3 requests allowed
    r1 = limiter.check(key)
    assert r1.allowed is True
    assert r1.remaining == 2

    r2 = limiter.check(key)
    assert r2.allowed is True
    assert r2.remaining == 1

    r3 = limiter.check(key)
    assert r3.allowed is True
    assert r3.remaining == 0

    # 4th request blocked
    r4 = limiter.check(key)
    assert r4.allowed is False
    assert r4.remaining == 0
    assert r4.retry_after > 0

    # Reset
    limiter.reset()
    r5 = limiter.check(key)
    assert r5.allowed is True

    # Test window expiration of old requests
    limiter._requests[key].appendleft(100.0)  # very old timestamp
    r6 = limiter.check(key)
    assert r6.allowed is True
    assert 100.0 not in limiter._requests[key]



def test_client_identifier_resolution():
    scope_api_key = {
        "type": "http",
        "headers": [(b"x-api-key", b"my-client-key")],
    }
    assert get_client_identifier(Request(scope_api_key)) == "key:my-client-key"

    scope_forwarded = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"203.0.113.195, 70.41.3.18")],
    }
    assert get_client_identifier(Request(scope_forwarded)) == "ip:203.0.113.195"

    scope_client = {
        "type": "http",
        "headers": [],
        "client": ("192.168.1.50", 12345),
    }
    assert get_client_identifier(Request(scope_client)) == "ip:192.168.1.50"

    scope_unknown = {
        "type": "http",
        "headers": [],
    }
    assert get_client_identifier(Request(scope_unknown)) == "unknown"


@pytest.mark.anyio
async def test_authorized_requests_succeed_and_unauthorized_rejected():
    provider = InMemoryMarketContextProvider()
    provider.update_context(_create_sample_context())
    service = OperatorService(context_provider=provider)

    sec_config = APISecurityConfig(
        api_key="valid-secret-key-999",
        security_enabled=True,
    )

    app = create_app(service=service, config=sec_config)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1. Unauthorized - Missing API Key
        resp_missing = await client.get("/signals/latest?symbol=BTCUSDT&timeframe=1h")
        assert resp_missing.status_code == 401
        assert "Invalid or missing API key" in resp_missing.json()["detail"]

        # 2. Unauthorized - Invalid API Key
        resp_invalid = await client.get(
            "/signals/latest?symbol=BTCUSDT&timeframe=1h",
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp_invalid.status_code == 401

        # 3. Authorized - Valid API Key
        resp_valid = await client.get(
            "/signals/latest?symbol=BTCUSDT&timeframe=1h",
            headers={"X-API-Key": "valid-secret-key-999"},
        )
        assert resp_valid.status_code == 200
        assert resp_valid.json()["success"] is True

        # 4. Market summary endpoint authorized
        resp_summary = await client.get(
            "/market/summary?symbol=BTCUSDT&timeframe=1h",
            headers={"X-API-Key": "valid-secret-key-999"},
        )
        assert resp_summary.status_code == 200

        # 5. Health check is public by default even when security is enabled
        resp_health = await client.get("/health")
        assert resp_health.status_code == 200
        assert resp_health.json()["status"] == "HEALTHY"


@pytest.mark.anyio
async def test_health_check_requires_auth_when_configured():
    provider = InMemoryMarketContextProvider()
    service = OperatorService(context_provider=provider)

    sec_config = APISecurityConfig(
        api_key="health-secret-key",
        security_enabled=True,
        require_auth_for_health=True,
    )

    app = create_app(service=service, config=sec_config)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Rejected without key
        resp_unauth = await client.get("/health")
        assert resp_unauth.status_code == 401

        # Accepted with valid key
        resp_auth = await client.get("/health", headers={"X-API-Key": "health-secret-key"})
        assert resp_auth.status_code == 200
        assert resp_auth.json()["status"] == "HEALTHY"


@pytest.mark.anyio
async def test_server_error_when_security_enabled_without_server_key():
    # Security enabled but api_key is None
    sec_config = APISecurityConfig(
        api_key=None,
        security_enabled=True,
    )

    guard = SecurityGuard(config=sec_config)

    scope = {
        "type": "http",
        "path": "/signals/latest",
        "headers": [(b"x-api-key", b"some-key")],
    }
    req = Request(scope)

    with pytest.raises(Exception) as exc_info:
        guard.verify_auth(req, x_api_key="some-key")

    assert exc_info.value.status_code == 500  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_rate_limiting_enforcement():
    provider = InMemoryMarketContextProvider()
    provider.update_context(_create_sample_context())
    service = OperatorService(context_provider=provider)

    sec_config = APISecurityConfig(
        api_key="rate-limited-key",
        security_enabled=True,
        rate_limit_enabled=True,
        rate_limit_per_minute=2,
    )

    app = create_app(service=service, config=sec_config)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        headers = {"X-API-Key": "rate-limited-key"}

        # Request 1: OK
        r1 = await client.get("/signals/latest?symbol=BTCUSDT&timeframe=1h", headers=headers)
        assert r1.status_code == 200

        # Request 2: OK
        r2 = await client.get("/signals/latest?symbol=BTCUSDT&timeframe=1h", headers=headers)
        assert r2.status_code == 200

        # Request 3: Rate limited -> 429
        r3 = await client.get("/signals/latest?symbol=BTCUSDT&timeframe=1h", headers=headers)
        assert r3.status_code == 429
        assert "Rate limit exceeded" in r3.json()["detail"]
        assert "retry-after" in r3.headers


@pytest.mark.anyio
async def test_cors_preflight_configuration():
    provider = InMemoryMarketContextProvider()
    service = OperatorService(context_provider=provider)

    sec_config = APISecurityConfig(
        cors_origins=("https://quant.cryptomonitor.io",),
    )

    app = create_app(service=service, config=sec_config)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.options(
            "/health",
            headers={
                "Origin": "https://quant.cryptomonitor.io",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "https://quant.cryptomonitor.io"
