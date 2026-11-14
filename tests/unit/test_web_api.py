"""v4 web API: same numbers as the engine, readable errors, server-side attempts."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src import idea_verifier, market_service
from src.indicators import TechnicalIndicators
from src.operator_api import web_router
from src.operator_api.app import create_app
from src.operator_api.config import APISecurityConfig
from src.operator_api.dependencies import reset_security_config


def _df(n=400):
    rng = np.random.default_rng(3)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    raw = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC"),
            "open": close,
            "high": close * 1.004,
            "low": close * 0.996,
            "close": close,
            "volume": rng.uniform(50, 150, n),
        }
    )
    return TechnicalIndicators().calculate_all(raw).reset_index(drop=True)


@pytest.fixture
def client(monkeypatch, fresh_journal):
    reset_security_config()
    df = _df()
    monkeypatch.setenv("WEB_LOGIN_DISABLED", "true")  # login is tested in test_web_auth
    monkeypatch.setattr(idea_verifier, "random_runs_for", lambda attempts: 4)  # speed
    monkeypatch.setattr(market_service, "load_candles", lambda s, i, bars=0: df)
    monkeypatch.setattr(market_service, "funding_for", lambda s, fetch=None: None)
    monkeypatch.setattr(web_router, "load_history", lambda s, i: None)
    app = create_app(config=APISecurityConfig(security_enabled=False))
    yield TestClient(app), df
    reset_security_config()


def test_hoy_returns_engine_figures(client):
    c, df = client
    r = c.get("/api/v1/hoy", params={"symbol": "BTCUSDT", "interval": "1h"})
    assert r.status_code == 200
    body = r.json()
    assert body["price"] == pytest.approx(float(df["close"].iloc[-1]))
    assert body["cost"]["spread_pct"] is None


def test_load_failure_is_a_readable_502(monkeypatch, client):
    c, _ = client

    def fail(s, i, bars=0):
        raise market_service.MarketDataError("No se pudo cargar X: sin red")

    monkeypatch.setattr(market_service, "load_candles", fail)
    r = c.get("/api/v1/hoy")
    assert r.status_code == 502
    assert "sin red" in r.json()["detail"]


def test_riesgo_risks_the_requested_amount(client):
    c, df = client
    r = c.post(
        "/api/v1/riesgo",
        json={"symbol": "BTCUSDT", "capital": 1_000_000, "risk_pct": 1.0},
    )
    assert r.status_code == 200
    # Large capital so the size is not capped: the loss equals 1 % of capital.
    assert r.json()["max_loss"] == pytest.approx(10_000.0)
    assert r.json()["entry_price"] == pytest.approx(float(df["close"].iloc[-1]))


def test_riesgo_rejects_invalid_side(client):
    c, _ = client
    r = c.post(
        "/api/v1/riesgo",
        json={"symbol": "BTCUSDT", "capital": 1000, "risk_pct": 1.0, "side": "X"},
    )
    assert r.status_code == 422


def test_metodos_lists_the_gallery(client):
    c, _ = client
    assert len(c.get("/api/v1/metodos").json()["methods"]) == 4


def test_verify_counts_attempts_on_the_server(client):
    c, _ = client
    body = {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "entry": "reversion_rsi",
        "sl_atr": 1.0,
        "tp_atr": 2.0,
        "max_bars": 24,
    }
    first = c.post("/api/v1/verificar", json=body).json()
    second = c.post("/api/v1/verificar", json=body).json()
    assert (first["attempts"], second["attempts"]) == (1, 2)
    assert first["data_source"].startswith("datos en vivo")
    assert "habría" in first["story"] or "habrías" in first["story"]


def test_unknown_entry_is_422(client):
    c, _ = client
    body = {
        "symbol": "BTCUSDT",
        "entry": "magia",
        "sl_atr": 1.0,
        "tp_atr": 2.0,
        "max_bars": 24,
    }
    assert c.post("/api/v1/verificar", json=body).status_code == 422


def test_security_applies_to_the_new_routes():
    reset_security_config()
    app = create_app(
        config=APISecurityConfig(api_key="clave-de-prueba", security_enabled=True)
    )
    assert TestClient(app).get("/api/v1/metodos").status_code == 401
    reset_security_config()


def test_built_interface_is_served_without_hiding_the_api(tmp_path, monkeypatch):
    import importlib

    app_module = importlib.import_module("src.operator_api.app")

    (tmp_path / "index.html").write_text("<h1>Quant Monitor</h1>", encoding="utf-8")
    monkeypatch.setattr(app_module, "WEB_DIST", tmp_path)
    monkeypatch.setenv("WEB_LOGIN_DISABLED", "true")
    reset_security_config()
    c = TestClient(
        app_module.create_app(config=APISecurityConfig(security_enabled=False))
    )
    assert "Quant Monitor" in c.get("/").text
    assert c.get("/api/v1/metodos").status_code == 200
    reset_security_config()


def test_radar_reports_tests_and_failures(monkeypatch, client):
    c, _ = client
    df = _df(700)  # the radar needs at least 500 bars of history per measure

    def load(symbol, interval, bars=0):
        if symbol == "ETHUSDT":
            raise market_service.MarketDataError("sin datos de ETHUSDT")
        return df

    monkeypatch.setattr(market_service, "load_candles", load)
    monkeypatch.setattr(
        market_service,
        "markets",
        lambda: {
            "crypto": [{"symbol": "BTCUSDT"}, {"symbol": "ETHUSDT"}],
            "other": [],
            "other_error": None,
        },
    )
    body = c.get("/api/v1/radar").json()
    assert body["failed"] == {"ETHUSDT": "sin datos de ETHUSDT"}
    assert body["tests"] >= 1
    assert body["alpha"] == pytest.approx(0.05 / body["tests"])
