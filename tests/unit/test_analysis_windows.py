"""v3.0: one analysis window for every route (backtest, live, dashboard, scanner,
copilot, validator). Expected values are derived by hand in the comments."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from src.constants import (
    ANALYSIS_WINDOW_BARS,
    LIVE_HISTORY_BARS,
    PREDICTIVE_MEMORY_BARS,
)
from src.predictive_engine import PredictiveEngine
from src.regime_classifier import MarketRegime, RegimeResult
from src.volume_profile import VolumeProfile


def test_window_constants_are_the_approved_values():
    assert ANALYSIS_WINDOW_BARS == 300
    assert PREDICTIVE_MEMORY_BARS == 2000
    # Live/dashboard history must cover the predictive memory plus its warm-up
    # (24 regime warm-up bars) and the default 5-bar horizon.
    assert LIVE_HISTORY_BARS >= PREDICTIVE_MEMORY_BARS + 24 + 5


def _vp_frame():
    # 100 old bars at price 50 with volume 1000, then 300 bars at 100/102, volume 1.
    old = [(50.0, 50.0, 50.0, 1000.0)] * 100
    new = [(101.0, 99.0, 100.0, 1.0), (103.0, 101.0, 102.0, 1.0)] * 150
    return pd.DataFrame(old + new, columns=["high", "low", "close", "volume"])


def test_volume_profile_uses_only_the_last_300_bars():
    # Typical prices in the window lie in [100, 102]; the old 50-price volume
    # mass must not drag the POC down.
    profile = VolumeProfile().calculate(_vp_frame())
    assert 100.0 <= profile["poc"] <= 102.0
    assert profile["val"] >= 100.0 - 1e-9


def test_volume_profile_window_equals_explicit_tail():
    df = _vp_frame()
    assert VolumeProfile().calculate(df) == VolumeProfile().calculate(df.tail(300))


def _pred_frame(n, closes):
    ts = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": c,
            "high": c + 1,
            "low": c - 1,
            "close": c,
            "volume": 10.0,
            "rsi": 50.0,
            "atr": 1.0,
            "ema_50": c,
            "ema_200": c,
            "volume_average": 10.0,
        }
    )


def test_predictive_memory_limits_historical_matches():
    # memory 50, horizon 2, n 200: regimes all TRENDING_BULL -> bias LONG.
    # Matching candidates are past bars idx in [24, 197]; with memory only
    # idx >= 200 - 50 = 150 count -> idx 150..197 = 48 matches.
    # Closes rise until bar 149 then fall: inside the memory window every
    # future close is lower -> 0 successes. P = (0+1)/(48+2) = 0.02.
    closes = list(range(1000, 1150)) + list(range(1149, 1099, -1))
    df = _pred_frame(200, closes)
    regime = RegimeResult(
        timestamp=df["timestamp"].iloc[-1],
        regime=MarketRegime.TRENDING_BULL,
        confidence=0.8,
        features_used={"ema_slope_50": 0.0},
    )
    values = np.array([MarketRegime.TRENDING_BULL.value] * (200 - 2 - 24), dtype=object)
    engine = PredictiveEngine(horizon_bars=2, min_history_bars=30, memory_bars=50)
    res = engine.evaluate(
        df, current_regime_res=regime, precomputed_past_regime_values=values
    )
    assert res.features_used["matched_historical_samples"] == 48
    assert res.features_used["favorable_historical_samples"] == 0
    assert res.probability_continuation == pytest.approx(1 / 50)


def test_binance_loader_paginates_beyond_1000(monkeypatch):
    from src import data_loader as dl

    hour = 3_600_000
    end = 10_000 * hour

    def fake_get(url, params, timeout):
        limit = params["limit"]
        stop = params.get("endTime", end + hour - 1)
        last_open = (stop + 1) // hour * hour - hour
        opens = [last_open - k * hour for k in range(limit)][::-1]
        resp = MagicMock()
        resp.json.return_value = [
            [o, "1", "2", "0.5", "1.5", "10", o + hour - 1, 0, 0, 0, 0, 0]
            for o in opens
        ]
        resp.raise_for_status.return_value = None
        return resp

    monkeypatch.setattr(dl.requests, "get", fake_get)
    monkeypatch.setattr(dl.time, "time", lambda: (end + 2 * hour) / 1000)
    df = dl.BinanceDataLoader().get_klines("BTCUSDT", "1h", limit=2500)
    assert len(df) == 2500
    assert df["timestamp"].is_monotonic_increasing
    assert not df["timestamp"].duplicated().any()
