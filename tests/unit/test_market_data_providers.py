"""Offline contract tests for multi-provider Forex/metals data (v2.2).

Payloads mimic the documented response shapes of each provider; they are
synthetic fixtures, not authenticated market history.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.forex_data_loader import (
    FOREX_PAIRS,
    METAL_PAIRS,
    ForexDataLoader,
    ForexInvalidDataError,
    ForexProviderUnavailableError,
)
from src.market_data_providers import (
    OandaProvider,
    TwelveDataProvider,
    compare_sources,
    provider_symbol,
)

NOW = datetime(2026, 11, 3, 12, 30, tzinfo=timezone.utc)


def _mock_urlopen(monkeypatch, payload):
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    cm = MagicMock()
    cm.__enter__.return_value = response
    urlopen = MagicMock(return_value=cm)
    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    return urlopen


def _twelve_payload(n=5, last_hour=12):
    values = []
    for i in range(n):
        ts = datetime(2026, 11, 3, last_hour, tzinfo=timezone.utc) - timedelta(hours=i)
        base = 1.10 + i * 0.001
        values.append(
            {
                "datetime": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "open": f"{base:.5f}",
                "high": f"{base + 0.002:.5f}",
                "low": f"{base - 0.002:.5f}",
                "close": f"{base + 0.001:.5f}",
            }
        )
    return {
        "meta": {"symbol": "EUR/USD", "interval": "1h"},
        "values": values,
        "status": "ok",
    }


def _oanda_payload(n=4, last_complete=False):
    candles = []
    for i in range(n):
        ts = datetime(2026, 11, 3, 8 + i, tzinfo=timezone.utc)
        base = 1.10 + i * 0.001
        candles.append(
            {
                "complete": True if i < n - 1 else last_complete,
                "volume": 100 + i,
                "time": ts.strftime("%Y-%m-%dT%H:%M:%S.000000000Z"),
                "mid": {
                    "o": f"{base:.5f}",
                    "h": f"{base + 0.002:.5f}",
                    "l": f"{base - 0.002:.5f}",
                    "c": f"{base + 0.001:.5f}",
                },
            }
        )
    return {"instrument": "EUR_USD", "granularity": "H1", "candles": candles}


# --- Symbol mapping -------------------------------------------------------


@pytest.mark.parametrize(
    "canonical,provider,expected",
    [
        ("EURUSD=X", "twelvedata", "EUR/USD"),
        ("XAUUSD=X", "twelvedata", "XAU/USD"),
        ("EURUSD=X", "oanda", "EUR_USD"),
        ("XAGUSD=X", "oanda", "XAG_USD"),
        ("eur/usd", "oanda", "EUR_USD"),
    ],
)
def test_provider_symbol_mapping(canonical, provider, expected):
    assert provider_symbol(canonical, provider) == expected


def test_metal_pairs_use_canonical_suffix_and_stay_out_of_forex_catalog():
    assert set(METAL_PAIRS.values()) == {"XAUUSD=X", "XAGUSD=X"}
    assert not set(METAL_PAIRS.values()) & set(FOREX_PAIRS.values())


# --- Twelve Data ------------------------------------------------------------


def test_twelvedata_requires_key():
    with pytest.raises(ForexProviderUnavailableError, match="TWELVEDATA_API_KEY"):
        TwelveDataProvider(api_key="")


def test_twelvedata_parses_sorts_and_drops_open_candle(monkeypatch):
    urlopen = _mock_urlopen(monkeypatch, _twelve_payload(n=5, last_hour=12))
    df = TwelveDataProvider(api_key="k", now=lambda: NOW).get_klines(
        "EURUSD=X", "1h", 10
    )
    # The 12:00 bar is still open at 12:30 and must not be used (anti-repainting).
    assert list(df["timestamp"]) == [
        pd.Timestamp(f"2026-11-03 {h:02d}:00", tz="UTC") for h in (8, 9, 10, 11)
    ]
    assert df["timestamp"].is_monotonic_increasing
    assert (df["volume"] == 0.0).all()
    assert df.attrs["provider"] == "twelvedata"
    assert df.attrs["provider_symbol"] == "EUR/USD"
    assert df.attrs["volume_kind"] == "none"
    url = urlopen.call_args[0][0].full_url
    assert "symbol=EUR%2FUSD" in url and "interval=1h" in url and "timezone=UTC" in url


def test_twelvedata_error_status_is_explicit(monkeypatch):
    _mock_urlopen(monkeypatch, {"status": "error", "code": 401, "message": "bad key"})
    with pytest.raises(ForexProviderUnavailableError, match="bad key"):
        TwelveDataProvider(api_key="k", now=lambda: NOW).get_klines(
            "EURUSD=X", "1h", 10
        )


def test_twelvedata_incoherent_candle_is_rejected(monkeypatch):
    payload = _twelve_payload(n=3, last_hour=10)
    payload["values"][1]["high"] = "0.5"
    _mock_urlopen(monkeypatch, payload)
    with pytest.raises(ForexInvalidDataError, match="Inconsistent"):
        TwelveDataProvider(api_key="k", now=lambda: NOW).get_klines(
            "EURUSD=X", "1h", 10
        )


def test_twelvedata_unsupported_interval_is_rejected():
    with pytest.raises(ForexInvalidDataError, match="intervalo"):
        TwelveDataProvider(api_key="k").get_klines("EURUSD=X", "3m", 10)


# --- OANDA ----------------------------------------------------------------


def test_oanda_requires_token():
    with pytest.raises(ForexProviderUnavailableError, match="OANDA_API_TOKEN"):
        OandaProvider(token="")


def test_oanda_uses_practice_host_bearer_and_complete_candles(monkeypatch):
    urlopen = _mock_urlopen(monkeypatch, _oanda_payload(n=4, last_complete=False))
    df = OandaProvider(token="tok").get_klines("EURUSD=X", "1h", 10)
    assert len(df) == 3  # incomplete last candle excluded
    assert list(df["volume"]) == [100.0, 101.0, 102.0]
    assert df.attrs["volume_kind"] == "tick"
    assert df.attrs["provider"] == "oanda"
    req = urlopen.call_args[0][0]
    assert req.full_url.startswith(
        "https://api-fxpractice.oanda.com/v3/instruments/EUR_USD/candles"
    )
    assert "granularity=H1" in req.full_url and "price=M" in req.full_url
    assert req.get_header("Authorization") == "Bearer tok"


def test_oanda_live_environment_uses_trade_host(monkeypatch):
    urlopen = _mock_urlopen(monkeypatch, _oanda_payload(n=2, last_complete=True))
    OandaProvider(token="tok", environment="live").get_klines("XAUUSD=X", "4h", 5)
    url = urlopen.call_args[0][0].full_url
    assert url.startswith("https://api-fxtrade.oanda.com/v3/instruments/XAU_USD/")
    assert "granularity=H4" in url


def test_oanda_rejects_unknown_environment():
    with pytest.raises(ForexProviderUnavailableError, match="OANDA_ENVIRONMENT"):
        OandaProvider(token="tok", environment="demo")


def test_oanda_missing_mid_prices_is_invalid(monkeypatch):
    payload = _oanda_payload(n=2, last_complete=True)
    del payload["candles"][0]["mid"]
    _mock_urlopen(monkeypatch, payload)
    with pytest.raises(ForexInvalidDataError):
        OandaProvider(token="tok").get_klines("EURUSD=X", "1h", 5)


# --- Facade selection -------------------------------------------------------


def test_loader_defaults_to_yahoo_without_metals(monkeypatch):
    monkeypatch.delenv("FOREX_PROVIDER", raising=False)
    loader = ForexDataLoader()
    assert loader.provider_name == "yahoo"
    assert loader.available_pairs() == FOREX_PAIRS
    with pytest.raises(ForexProviderUnavailableError, match="Twelve Data u OANDA"):
        loader.get_forex_klines("XAUUSD=X", "1h", 10)


def test_loader_selects_twelvedata_from_env_and_offers_metals(monkeypatch):
    monkeypatch.setenv("FOREX_PROVIDER", "twelvedata")
    monkeypatch.setenv("TWELVEDATA_API_KEY", "k")
    _mock_urlopen(monkeypatch, _twelve_payload(n=3, last_hour=10))
    loader = ForexDataLoader()
    assert loader.provider_name == "twelvedata"
    assert {**FOREX_PAIRS, **METAL_PAIRS} == loader.available_pairs()
    df = loader.get_klines("XAUUSD=X", "1h", 2)
    assert len(df) == 2
    assert df.attrs["provider"] == "twelvedata"


def test_loader_unknown_provider_is_explicit(monkeypatch):
    monkeypatch.setenv("FOREX_PROVIDER", "bloomberg")
    with pytest.raises(ForexProviderUnavailableError, match="FOREX_PROVIDER"):
        ForexDataLoader()


def test_loader_configured_provider_without_key_fails_loudly(monkeypatch):
    monkeypatch.setenv("FOREX_PROVIDER", "oanda")
    monkeypatch.delenv("OANDA_API_TOKEN", raising=False)
    with pytest.raises(ForexProviderUnavailableError, match="OANDA_API_TOKEN"):
        ForexDataLoader()


# --- Cross-source verification ------------------------------------------------


def _frame(closes, start="2026-11-03 08:00"):
    ts = pd.date_range(start, periods=len(closes), freq="1h", tz="UTC")
    return pd.DataFrame({"timestamp": ts, "close": closes})


def test_compare_sources_agree_within_tolerance():
    a = _frame([1.1000, 1.1010, 1.1020])
    b = _frame([1.1001, 1.1010, 1.1019])
    res = compare_sources(a, b, tolerance_pct=0.05, min_overlap=3)
    assert res["status"] == "AGREE"
    assert res["overlap"] == 3
    # 0.0001 / 1.1000 * 100 = 0.00909...%
    assert res["max_close_diff_pct"] == pytest.approx(0.0001 / 1.1 * 100)


def test_compare_sources_flags_disagreement_and_timestamp():
    a = _frame([1.1000, 1.1010, 1.1020])
    b = _frame([1.1000, 1.1110, 1.1020])
    res = compare_sources(a, b, tolerance_pct=0.05, min_overlap=3)
    assert res["status"] == "DISAGREE"
    assert res["worst_timestamp"] == pd.Timestamp("2026-11-03 09:00", tz="UTC")


def test_compare_sources_insufficient_overlap_never_claims_agreement():
    a = _frame([1.1, 1.2])
    b = _frame([1.1, 1.2], start="2026-11-04 08:00")
    res = compare_sources(a, b, tolerance_pct=0.05, min_overlap=2)
    assert res["status"] == "INSUFFICIENT_OVERLAP"
    assert res["max_close_diff_pct"] is None


@pytest.mark.parametrize("tol", [0, -1, float("nan")])
def test_compare_sources_requires_positive_tolerance(tol):
    with pytest.raises(ValueError):
        compare_sources(_frame([1.1]), _frame([1.1]), tolerance_pct=tol, min_overlap=1)


# --- Weekly market closure (Fri 17:00 New York -> Sun 17:00 New York) -------

from src.market_data_providers import drop_weekend_closure  # noqa: E402


def _hourly(start_utc, hours):
    ts = pd.date_range(start_utc, periods=hours, freq="1h", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": 1.1,
            "high": 1.2,
            "low": 1.0,
            "close": 1.1,
            "volume": 0.0,
        }
    )


def test_weekend_closure_summer_time_uses_21_utc():
    # 2026-10-30 is a Friday; New York is on EDT (UTC-4): close 21:00 UTC.
    df = _hourly("2026-10-30 19:00", 4)  # 19,20,21,22 UTC Friday
    out = drop_weekend_closure(df)
    assert list(out["timestamp"].dt.hour) == [19, 20]
    assert out.attrs["weekend_bars_removed"] == 2


def test_weekend_closure_winter_time_reopens_22_utc():
    # 2026-11-08 is a Sunday; New York on EST (UTC-5): reopen 22:00 UTC.
    df = _hourly("2026-11-08 20:00", 4)  # 20,21,22,23 UTC Sunday
    out = drop_weekend_closure(df)
    assert list(out["timestamp"].dt.hour) == [22, 23]


def test_weekend_closure_removes_saturday_and_keeps_weekdays():
    df = _hourly("2026-10-31 00:00", 24)  # whole Saturday
    assert drop_weekend_closure(df).empty
    weekday = _hourly("2026-11-04 00:00", 24)  # Wednesday
    assert len(drop_weekend_closure(weekday)) == 24


def test_twelvedata_drops_weekend_bars(monkeypatch):
    payload = _twelve_payload(n=3, last_hour=10)
    sat = {
        "datetime": "2026-10-31 05:00:00",
        "open": "1.1",
        "high": "1.2",
        "low": "1.0",
        "close": "1.1",
    }
    payload["values"].append(sat)
    _mock_urlopen(monkeypatch, payload)
    df = TwelveDataProvider(api_key="k", now=lambda: NOW).get_klines(
        "EURUSD=X", "1h", 10
    )
    assert pd.Timestamp("2026-10-31 05:00", tz="UTC") not in set(df["timestamp"])
    assert df.attrs["weekend_bars_removed"] == 1
