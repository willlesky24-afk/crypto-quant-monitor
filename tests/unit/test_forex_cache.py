"""Offline tests for the incremental Parquet cache of provider candles (v2.2)."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.market_data_providers import CachedCandleSource


class FakeProvider:
    name = "oanda"
    supports_metals = True

    def __init__(self, frames):
        self.frames = list(frames)
        self.calls = 0

    def get_klines(self, symbol, interval, limit):
        self.calls += 1
        df = self.frames.pop(0)
        df.attrs.update(
            {"provider": "oanda", "provider_symbol": "EUR_USD", "volume_kind": "tick"}
        )
        return df


def _bars(start, n, close=1.1):
    ts = pd.date_range(start, periods=n, freq="1h", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": close,
            "high": close + 0.01,
            "low": close - 0.01,
            "close": close,
            "volume": 10.0,
        }
    )


def _clock(iso):
    return lambda: datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


def test_cache_serves_fresh_data_without_network(tmp_path):
    prov = FakeProvider([_bars("2026-11-04 00:00", 5)])  # last bar 04:00, closes 05:00
    src = CachedCandleSource(prov, tmp_path, now=_clock("2026-11-04 05:30"))
    first = src.get_klines("EURUSD=X", "1h", 5)
    second = src.get_klines("EURUSD=X", "1h", 5)
    assert prov.calls == 1
    pd.testing.assert_frame_equal(first, second)
    assert second.attrs["cache"] == "HIT"
    assert second.attrs["provider"] == "oanda"
    assert second.attrs["volume_kind"] == "tick"


def test_cache_refreshes_when_a_new_candle_has_closed_and_merges(tmp_path):
    prov = FakeProvider([_bars("2026-11-04 00:00", 5), _bars("2026-11-04 03:00", 4)])
    src = CachedCandleSource(prov, tmp_path, now=_clock("2026-11-04 05:30"))
    src.get_klines("EURUSD=X", "1h", 5)
    src._now = _clock("2026-11-04 07:10")  # 05:00 and 06:00 bars have closed
    out = src.get_klines("EURUSD=X", "1h", 10)
    assert prov.calls == 2
    assert out.attrs["cache"] == "REFRESH"
    assert list(out["timestamp"].dt.hour) == [0, 1, 2, 3, 4, 5, 6]


def test_cache_keeps_providers_apart(tmp_path):
    prov = FakeProvider([_bars("2026-11-04 00:00", 3)])
    CachedCandleSource(prov, tmp_path, now=_clock("2026-11-04 03:30")).get_klines(
        "EURUSD=X", "1h", 3
    )
    assert (tmp_path / "EURUSD_OANDA" / "1h").is_dir()


def test_cache_records_provider_revisions(tmp_path):
    prov = FakeProvider(
        [
            _bars("2026-11-04 00:00", 3, close=1.1),
            _bars("2026-11-04 00:00", 5, close=1.2),
        ]
    )
    src = CachedCandleSource(prov, tmp_path, now=_clock("2026-11-04 03:30"))
    src.get_klines("EURUSD=X", "1h", 3)
    src._now = _clock("2026-11-04 05:30")
    out = src.get_klines("EURUSD=X", "1h", 5)
    assert out.attrs["revised_bars"] == 3
    assert (out["close"] == 1.2).all()  # newest provider values win


def test_cache_refetches_when_cache_is_shorter_than_limit(tmp_path):
    prov = FakeProvider([_bars("2026-11-04 03:00", 2), _bars("2026-11-04 00:00", 5)])
    src = CachedCandleSource(prov, tmp_path, now=_clock("2026-11-04 05:30"))
    src.get_klines("EURUSD=X", "1h", 2)
    out = src.get_klines("EURUSD=X", "1h", 5)
    assert prov.calls == 2
    assert len(out) == 5


def test_loader_uses_cache_only_when_configured(monkeypatch, tmp_path):
    from src.forex_data_loader import ForexDataLoader

    monkeypatch.setenv("FOREX_PROVIDER", "oanda")
    monkeypatch.setenv("OANDA_API_TOKEN", "tok")
    monkeypatch.delenv("FOREX_CACHE_DIR", raising=False)
    assert not isinstance(ForexDataLoader()._source, CachedCandleSource)
    monkeypatch.setenv("FOREX_CACHE_DIR", str(tmp_path))
    assert isinstance(ForexDataLoader()._source, CachedCandleSource)


def test_cache_restarts_when_spread_column_appears(tmp_path):
    old = _bars("2026-11-04 00:00", 3)
    new = _bars("2026-11-04 02:00", 3)
    new["spread"] = 0.0002
    prov = FakeProvider([old, new])
    src = CachedCandleSource(prov, tmp_path, now=_clock("2026-11-04 03:30"))
    src.get_klines("EURUSD=X", "1h", 3)
    src._now = _clock("2026-11-04 05:30")
    out = src.get_klines("EURUSD=X", "1h", 10)
    assert out["spread"].notna().all()
    assert list(out["timestamp"].dt.hour) == [2, 3, 4]
