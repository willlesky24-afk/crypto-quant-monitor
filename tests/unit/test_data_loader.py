from __future__ import annotations

import pytest
import requests

from src.data_loader import BinanceDataLoader


class FakeResponse:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.payload


def candle(timestamp=1_700_000_000_000, close_time=None):
    if close_time is None:
        close_time = timestamp + 3_599_999
    return [
        timestamp,
        "100.1",
        "105.2",
        "99.3",
        "104.4",
        "123.5",
        close_time,
        "0",
        10,
        "0",
        "0",
        "0",
    ]


def test_get_klines_maps_binance_payload_without_network(monkeypatch):
    captured = {}

    def fake_get(url, *, params, timeout):
        captured.update(url=url, params=params, timeout=timeout)
        return FakeResponse([candle()])

    monkeypatch.setattr("src.data_loader.requests.get", fake_get)
    result = BinanceDataLoader().get_klines("ETHUSDT", "4h", 1)

    assert captured["url"].endswith("/klines")
    assert captured["params"] == {"symbol": "ETHUSDT", "interval": "4h", "limit": 1}
    assert captured["timeout"] == 10
    assert list(result.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert result.loc[0, "close"] == pytest.approx(104.4)
    assert result.loc[0, ["open", "high", "low", "close", "volume"]].dtype.kind == "f"


def test_get_klines_filters_open_candle_by_default(monkeypatch):
    past_candle = candle(timestamp=1_700_000_000_000, close_time=1_700_003_599_999)
    future_candle = candle(timestamp=2_000_000_000_000, close_time=2_000_003_599_999)

    monkeypatch.setattr(
        "src.data_loader.requests.get",
        lambda *args, **kwargs: FakeResponse([past_candle, future_candle]),
    )
    monkeypatch.setattr("src.data_loader.time.time", lambda: 1_800_000_000.0)

    # By default, include_open_candle is False -> should drop the future (open) candle
    result = BinanceDataLoader().get_klines("BTCUSDT", "1h", 2)
    assert len(result) == 1
    assert result.loc[0, "close"] == pytest.approx(104.4)

    # When include_open_candle is True -> should keep both
    result_with_open = BinanceDataLoader().get_klines(
        "BTCUSDT", "1h", 2, include_open_candle=True
    )
    assert len(result_with_open) == 2


def test_get_klines_returns_empty_when_all_candles_are_open(monkeypatch):
    future_candle = candle(timestamp=2_000_000_000_000, close_time=2_000_003_599_999)

    monkeypatch.setattr(
        "src.data_loader.requests.get",
        lambda *args, **kwargs: FakeResponse([future_candle]),
    )
    monkeypatch.setattr("src.data_loader.time.time", lambda: 1_800_000_000.0)

    result = BinanceDataLoader().get_klines("BTCUSDT", "1h", 1)
    assert result.empty
    assert list(result.columns) == ["timestamp", "open", "high", "low", "close", "volume"]


def test_get_klines_returns_empty_when_api_returns_empty_list(monkeypatch):
    monkeypatch.setattr(
        "src.data_loader.requests.get",
        lambda *args, **kwargs: FakeResponse([]),
    )

    result = BinanceDataLoader().get_klines("BTCUSDT", "1h", 1)
    assert result.empty
    assert list(result.columns) == ["timestamp", "open", "high", "low", "close", "volume"]


def test_get_klines_propagates_http_errors(monkeypatch):
    error = requests.HTTPError("rate limited")
    monkeypatch.setattr(
        "src.data_loader.requests.get",
        lambda *args, **kwargs: FakeResponse(error=error),
    )

    with pytest.raises(requests.HTTPError, match="rate limited"):
        BinanceDataLoader().get_klines()


