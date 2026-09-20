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


def candle(timestamp=1_700_000_000_000):
    return [
        timestamp,
        "100.1",
        "105.2",
        "99.3",
        "104.4",
        "123.5",
        timestamp + 3_599_999,
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


def test_get_klines_propagates_http_errors(monkeypatch):
    error = requests.HTTPError("rate limited")
    monkeypatch.setattr(
        "src.data_loader.requests.get",
        lambda *args, **kwargs: FakeResponse(error=error),
    )

    with pytest.raises(requests.HTTPError, match="rate limited"):
        BinanceDataLoader().get_klines()

