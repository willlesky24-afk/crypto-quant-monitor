from __future__ import annotations

import pytest
import requests

from src.historical_data_loader import HistoricalDataLoader


class FakeResponse:
    def __init__(self, payload=None, headers=None, error=None):
        self.payload = payload or []
        self.headers = headers or {}
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.payload


def generate_raw_candle_chunk(start_ts_ms: int, count: int, interval_ms: int = 3_600_000) -> list:
    chunk = []
    for i in range(count):
        open_time = start_ts_ms + i * interval_ms
        close_time = open_time + interval_ms - 1
        chunk.append(
            [
                open_time,
                "100.0",
                "105.0",
                "95.0",
                "102.0",
                "1000.0",
                close_time,
                "102000.0",
                500,
                "600.0",
                "61200.0",
                "0",
            ]
        )
    return chunk


def test_historical_loader_paginates_multiple_chunks(monkeypatch):
    loader = HistoricalDataLoader(chunk_size=10, request_delay=0.0)
    start_ms = 1_700_000_000_000
    interval_ms = 3_600_000

    chunk1 = generate_raw_candle_chunk(start_ms, 10, interval_ms)
    chunk2 = generate_raw_candle_chunk(start_ms + 10 * interval_ms, 5, interval_ms)

    calls = []

    def mock_get(url, *, params, timeout):
        calls.append(params)
        if len(calls) == 1:
            return FakeResponse(chunk1)
        return FakeResponse(chunk2)

    monkeypatch.setattr("src.historical_data_loader.requests.get", mock_get)

    df = loader.get_historical_klines(
        symbol="BTCUSDT",
        interval="1h",
        start_time=start_ms,
        end_time=start_ms + 15 * interval_ms,
        include_open_candle=True,
    )

    assert len(calls) == 2
    assert len(df) == 15
    assert df.loc[0, "close"] == 102.0
    assert "quote_volume" in df.columns
    assert "trades" in df.columns


def test_historical_loader_filters_open_candle_by_default(monkeypatch):
    loader = HistoricalDataLoader(chunk_size=10, request_delay=0.0)
    past_chunk = generate_raw_candle_chunk(1_700_000_000_000, 2, 3_600_000)
    # Give the last candle a future close_time
    past_chunk[-1][6] = 2_000_000_000_000

    monkeypatch.setattr(
        "src.historical_data_loader.requests.get",
        lambda *args, **kwargs: FakeResponse(past_chunk),
    )
    monkeypatch.setattr("src.historical_data_loader.time.time", lambda: 1_800_000_000.0)

    df = loader.get_historical_klines(
        symbol="ETHUSDT",
        interval="1h",
        start_time="2023-11-14",
        include_open_candle=False,
    )
    assert len(df) == 1


def test_historical_loader_retries_on_transient_error(monkeypatch):
    loader = HistoricalDataLoader(chunk_size=10, request_delay=0.0, max_retries=3)
    attempt = 0
    chunk = generate_raw_candle_chunk(1_700_000_000_000, 2)

    def mock_get(*args, **kwargs):
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            return FakeResponse(error=requests.HTTPError("429 rate limit"))
        return FakeResponse(chunk)

    monkeypatch.setattr("src.historical_data_loader.requests.get", mock_get)
    monkeypatch.setattr("src.historical_data_loader.time.sleep", lambda s: None)

    df = loader.get_historical_klines("BTCUSDT", "1h", start_time=1_700_000_000_000)
    assert attempt == 2
    assert len(df) == 2


def test_historical_loader_exhausted_retries_raises_error(monkeypatch):
    loader = HistoricalDataLoader(chunk_size=10, request_delay=0.0, max_retries=2)

    monkeypatch.setattr(
        "src.historical_data_loader.requests.get",
        lambda *args, **kwargs: FakeResponse(error=requests.HTTPError("Fatal network error")),
    )
    monkeypatch.setattr("src.historical_data_loader.time.sleep", lambda s: None)

    with pytest.raises(requests.HTTPError, match="Fatal network error"):
        loader.get_historical_klines("BTCUSDT", "1h", start_time="2024-01-01")


def test_historical_loader_invalid_date_range_raises_value_error():
    loader = HistoricalDataLoader()
    with pytest.raises(ValueError, match="no puede ser posterior"):
        loader.get_historical_klines("BTCUSDT", "1h", start_time="2025-01-01", end_time="2024-01-01")


def test_historical_loader_invalid_interval_raises_value_error():
    loader = HistoricalDataLoader()
    with pytest.raises(ValueError, match="no soportado"):
        loader.get_historical_klines("BTCUSDT", "99x", start_time="2024-01-01")


def test_historical_loader_empty_response_returns_empty_df(monkeypatch):
    loader = HistoricalDataLoader(request_delay=0.0)
    monkeypatch.setattr(
        "src.historical_data_loader.requests.get",
        lambda *args, **kwargs: FakeResponse([]),
    )

    df = loader.get_historical_klines("BTCUSDT", "1h", start_time="2024-01-01")
    assert df.empty
    assert list(df.columns) == [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_volume",
        "trades",
        "taker_buy_base",
        "taker_buy_quote",
    ]


def test_historical_loader_weight_throttling(monkeypatch):
    loader = HistoricalDataLoader(chunk_size=10, request_delay=0.0)
    chunk = generate_raw_candle_chunk(1_700_000_000_000, 2)
    throttled = False

    def mock_sleep(seconds):
        nonlocal throttled
        if seconds >= 1.0:
            throttled = True

    monkeypatch.setattr(
        "src.historical_data_loader.requests.get",
        lambda *args, **kwargs: FakeResponse(chunk, headers={"x-mbx-used-weight-1m": "1150"}),
    )
    monkeypatch.setattr("src.historical_data_loader.time.sleep", mock_sleep)

    df = loader.get_historical_klines("BTCUSDT", "1h", start_time=1_700_000_000_000)
    assert throttled
    assert len(df) == 2

def test_historical_loader_seconds_epoch_conversion(monkeypatch):
    loader = HistoricalDataLoader(chunk_size=10, request_delay=0.0)
    chunk = generate_raw_candle_chunk(1_700_000_000_000, 2)
    monkeypatch.setattr(
        "src.historical_data_loader.requests.get",
        lambda *args, **kwargs: FakeResponse(chunk),
    )

    # Pass start_time as epoch seconds (float)
    df = loader.get_historical_klines("BTCUSDT", "1h", start_time=1_700_000_000.0)
    assert len(df) == 2


def test_historical_loader_only_open_candle_filtered_returns_empty(monkeypatch):
    loader = HistoricalDataLoader(chunk_size=10, request_delay=0.0)
    # Only 1 candle which is currently open (future close_time)
    chunk = generate_raw_candle_chunk(1_700_000_000_000, 1)
    chunk[0][6] = 2_000_000_000_000

    monkeypatch.setattr(
        "src.historical_data_loader.requests.get",
        lambda *args, **kwargs: FakeResponse(chunk),
    )
    monkeypatch.setattr("src.historical_data_loader.time.time", lambda: 1_800_000_000.0)

    df = loader.get_historical_klines("BTCUSDT", "1h", start_time=1_700_000_000_000, include_open_candle=False)
    assert df.empty


def test_historical_loader_with_request_delay(monkeypatch):
    loader = HistoricalDataLoader(chunk_size=5, request_delay=0.05)
    start_ms = 1_700_000_000_000
    chunk1 = generate_raw_candle_chunk(start_ms, 5)
    chunk2 = generate_raw_candle_chunk(start_ms + 5 * 3_600_000, 2)

    calls = []

    def mock_get(url, *, params, timeout):
        calls.append(params)
        if len(calls) == 1:
            return FakeResponse(chunk1)
        return FakeResponse(chunk2)

    sleeps = []
    monkeypatch.setattr("src.historical_data_loader.requests.get", mock_get)
    monkeypatch.setattr("src.historical_data_loader.time.sleep", lambda s: sleeps.append(s))

    df = loader.get_historical_klines("BTCUSDT", "1h", start_time=start_ms, include_open_candle=True)
    assert len(df) == 7
    assert 0.05 in sleeps

