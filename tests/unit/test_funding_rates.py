"""v3.1 funding sources. Payloads follow each provider's public response shape."""

from __future__ import annotations

import pandas as pd
import pytest

from src.funding_rates import (
    FundingSource,
    FundingUnavailableError,
    funding_snapshot,
    provider_from_env,
)

T0 = 1_700_000_000_000  # ms
H8 = 8 * 3_600_000


def _okx_get(pages):
    calls = []

    def get(url, params):
        calls.append(params)
        rows = pages[len(calls) - 1]
        return 200, {
            "code": "0",
            "data": [{"fundingTime": str(t), "fundingRate": str(r)} for t, r in rows],
        }

    return get, calls


def test_okx_pages_backwards_and_sorts_oldest_first():
    newest = [(T0 + 3 * H8, 0.0004), (T0 + 2 * H8, 0.0003)]
    older = [(T0 + H8, 0.0002), (T0, 0.0001)]
    get, calls = _okx_get([newest, older, []])
    s = FundingSource("okx", get=get, page_size=2).fetch("BTCUSDT", limit=10)
    assert s.tolist() == [0.0001, 0.0002, 0.0003, 0.0004]
    assert s.index.is_monotonic_increasing
    assert s.index[0] == pd.Timestamp(T0, unit="ms", tz="UTC")
    assert calls[0]["instId"] == "BTC-USDT-SWAP"
    assert "after" not in calls[0]
    assert calls[1]["after"] == str(T0 + 2 * H8)


def test_limit_keeps_the_newest_records():
    rows = [(T0 + 2 * H8, 0.3), (T0 + H8, 0.2)]
    get, _ = _okx_get([rows])
    s = FundingSource("okx", get=get, page_size=2).fetch("BTCUSDT", limit=2)
    assert s.tolist() == [0.2, 0.3]


def test_binance_shape_and_symbol():
    seen = {}

    def get(url, params):
        seen.update(params)
        return 200, [
            {"fundingTime": T0, "fundingRate": "0.00010000"},
            {"fundingTime": T0 + H8, "fundingRate": "-0.00020000"},
        ]

    s = FundingSource("binance", get=get).fetch("ETHUSDT", limit=2)
    assert seen["symbol"] == "ETHUSDT"
    assert s.tolist() == [0.0001, -0.0002]


def test_restricted_location_is_reported_clearly_without_fallback():
    calls = []

    def get(url, params):
        calls.append(url)
        return 451, {"msg": "restricted location"}

    with pytest.raises(FundingUnavailableError, match="ubicacion"):
        FundingSource("binance", get=get).fetch("BTCUSDT")
    assert len(calls) == 1


def test_okx_error_code_is_not_empty_data():
    with pytest.raises(FundingUnavailableError, match="okx"):
        FundingSource("okx", get=lambda u, p: (200, {"code": "51001"})).fetch("BTCUSDT")


def test_no_records_fail_loudly():
    get, _ = _okx_get([[]])
    with pytest.raises(FundingUnavailableError):
        FundingSource("okx", get=get).fetch("BTCUSDT")


def test_unknown_provider_rejected():
    with pytest.raises(FundingUnavailableError):
        FundingSource("otro")


def test_provider_from_env(monkeypatch):
    monkeypatch.delenv("FUNDING_PROVIDER", raising=False)
    assert provider_from_env() == "okx"
    monkeypatch.setenv("FUNDING_PROVIDER", "binance")
    assert provider_from_env() == "binance"


def test_snapshot_compares_size_either_way():
    # Sizes before: 0.1, 0.2, 0.3, 0.4; latest -0.35 has size 0.35: 3 of 4 below.
    s = funding_snapshot(pd.Series([0.001, -0.002, 0.003, 0.004, -0.0035]))
    assert s["rate_pct"] == pytest.approx(-0.35)
    assert s["size_percentile"] == pytest.approx(75.0)
    assert s["records"] == 5
