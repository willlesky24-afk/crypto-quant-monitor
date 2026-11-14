"""v4 market service: same numbers as the engine, gaps stay None."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.daily_summary import market_conditions
from src.indicators import TechnicalIndicators
from src.market_service import funding_for, level, today_payload


def _df(n=400, spread=False):
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
    if spread:
        raw["spread"] = close * 0.0002
    return TechnicalIndicators().calculate_all(raw).reset_index(drop=True)


def test_level_bands():
    assert level(None, "Alto", "Bajo")["status"] == "Sin dato"
    assert level(90.0, "Alto", "Bajo") == {"status": "Alto", "tone": "warn"}
    assert level(10.0, "Alto", "Bajo") == {"status": "Bajo", "tone": "good"}
    assert level(50.0, "Alto", "Bajo")["status"] == "Normal"


def test_payload_matches_the_engine_and_keeps_gaps_as_none():
    df = _df()
    p = today_payload(df, "BTCUSDT", "1h")
    assert p["price"] == pytest.approx(float(df["close"].iloc[-1]))
    expected = market_conditions(df)["volatility_percentile"]
    assert p["volatility"]["percentile"] == pytest.approx(expected)
    assert p["cost"]["spread_pct"] is None
    assert p["cost"]["status"] == "Sin dato"
    assert p["funding"] is None
    assert len(p["candles"]) == 300
    assert p["candles"][-1]["close"] == pytest.approx(float(df["close"].iloc[-1]))
    assert p["source"] == "BINANCE"


def test_payload_with_spread_reports_cost():
    # Spread 0.0002 of price = 0.020 %.
    p = today_payload(_df(spread=True), "EURUSD=X", "1h")
    assert p["cost"]["spread_pct"] == pytest.approx(0.02)


def test_funding_is_only_for_crypto_and_errors_are_reported():
    assert funding_for("EURUSD=X") is None

    def failing(symbol):
        raise OSError("sin red")

    assert funding_for("BTCUSDT", fetch=failing) == {"error": "sin red"}


def test_candles_are_reused_for_a_minute_and_errors_are_not_cached(monkeypatch):
    from src import market_service

    market_service._CACHE.clear()
    calls = []

    def fetch(symbol, interval, bars):
        calls.append(symbol)
        if symbol == "BAD":
            raise market_service.MarketDataError("sin red")
        return _df(60)

    monkeypatch.setattr(market_service, "_fetch_candles", fetch)
    market_service.load_candles("BTCUSDT", "1h")
    market_service.load_candles("BTCUSDT", "1h")
    assert calls == ["BTCUSDT"]
    for _ in range(2):
        with pytest.raises(market_service.MarketDataError):
            market_service.load_candles("BAD", "1h")
    assert calls == ["BTCUSDT", "BAD", "BAD"]
    market_service._CACHE.clear()


def test_markets_lists_crypto_without_emojis():
    from src.market_service import markets

    m = markets()
    assert m["crypto"][0] == {"symbol": "BTCUSDT", "label": "BTC / USDT"}
    assert "1h" in m["intervals"]
