"""v3.0 screening signals. +1 long, -1 short, 0 nothing, decided on closed bars.

Expected values are derived by hand from the stated prices.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.signal_candidates import (
    CANDIDATES,
    WARMUP_BARS,
    signal_bollinger,
    signal_donchian,
    signal_random,
    signal_rsi_momentum,
    signal_rsi_reversion,
    signal_trend,
    signal_tsmom,
    signal_volume_direction,
    signals_to_events,
)


def _df(close, **extra):
    n = len(close)
    data = {
        "timestamp": pd.date_range("2023-01-02", periods=n, freq="4h", tz="UTC"),
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": [100.0] * n,
    }
    data.update(extra)
    return pd.DataFrame(data)


def test_trend_requires_full_ema_stack():
    df = _df(
        [110.0, 90.0, 100.0, 104.0],
        ema_50=[105.0, 95.0, 105.0, 105.0],
        ema_200=[100.0, 100.0, 100.0, 100.0],
    )
    # 110>105>100 long; 90<95<100 short; 100<105 but 105>100 none; 104 none.
    assert signal_trend(df).tolist() == [1, -1, 0, 0]


def test_rsi_momentum_uses_the_model_bands():
    df = _df([1.0] * 5, rsi=[50.0, 69.9, 70.0, 30.0, 29.9])
    assert signal_rsi_momentum(df).tolist() == [1, 1, 0, 0, -1]


def test_rsi_reversion_is_contrarian():
    df = _df([1.0] * 3, rsi=[29.9, 50.0, 70.1])
    assert signal_rsi_reversion(df).tolist() == [1, 0, -1]


def test_missing_indicator_gives_no_signal():
    df = _df([1.0], rsi=[float("nan")])
    assert signal_rsi_reversion(df).tolist() == [0]


def test_volume_direction():
    df = _df([10.0, 10.0, 12.0, 10.0], volume_average=[50.0, 200.0, 50.0, 50.0])
    df["open"] = [9.0, 9.0, 12.0, 11.0]
    # up & loud long; up & quiet none; flat none; down & loud short.
    assert signal_volume_direction(df).tolist() == [1, 0, 0, -1]


def test_donchian_breaks_prior_channel_excluding_current_bar():
    df = _df([10.0, 11.0, 12.0, 12.0, 9.0])
    # Window 3 over previous bars. Bar 3: max(10,11,12)=12, 12>12 false.
    # Bar 4: min(11,12,12)=11, 9<11 short. Bars 0-2 have no full window.
    assert signal_donchian(df, window=3).tolist() == [0, 0, 0, 0, -1]
    df2 = _df([10.0, 11.0, 12.0, 13.0])
    assert signal_donchian(df2, window=3).tolist() == [0, 0, 0, 1]


def test_tsmom_sign_of_lookback_return():
    df = _df([10.0, 12.0, 11.0, 9.0, 11.0])
    # Lookback 2: 11 vs 10 up; 9 vs 12 down; 11 vs 11 flat.
    assert signal_tsmom(df, lookback=2).tolist() == [0, 0, 1, -1, 0]


def test_bollinger_reversion_uses_population_std():
    # Window 4 of [10,10,10,20]: mean 12.5, population std sqrt(18.75)=4.33.
    # k=2: upper 21.16, 20 inside. k=1: upper 16.83, 20 above, so short.
    df = _df([10.0, 10.0, 10.0, 20.0])
    assert signal_bollinger(df, window=4, k=2.0).tolist() == [0, 0, 0, 0]
    assert signal_bollinger(df, window=4, k=1.0).tolist() == [0, 0, 0, -1]
    df2 = _df([20.0, 20.0, 20.0, 10.0])
    assert signal_bollinger(df2, window=4, k=1.0).tolist() == [0, 0, 0, 1]


def test_signals_are_causal_later_bars_do_not_change_past_values():
    close = [float(100 + (i % 7) - (i % 3)) for i in range(60)]
    full = _df(close)
    cut = full.iloc[:40].copy()
    pd.testing.assert_series_equal(
        signal_donchian(full, window=5).iloc[:40], signal_donchian(cut, window=5)
    )


def test_random_control_is_reproducible_and_two_sided():
    df = _df([1.0] * 500)
    a = signal_random(df, seed=5)
    assert a.equals(signal_random(df, seed=5))
    assert set(a.unique()) == {-1, 1}


def test_events_skip_warmup_flat_bars_and_invalid_atr():
    n = WARMUP_BARS + 3
    df = _df([100.0] * n, atr=[2.0] * (n - 1) + [float("nan")])
    sig = pd.Series([1] * n)
    sig.iloc[WARMUP_BARS] = 0
    sig.iloc[WARMUP_BARS + 1] = -1
    ev = signals_to_events(df, sig, "EURUSD=X", "4h")
    assert [e.direction for e in ev] == ["SHORT"]
    assert ev[0].candle_timestamp == df["timestamp"].iloc[WARMUP_BARS + 1]
    assert ev[0].atr == pytest.approx(2.0)
    assert ev[0].quant_score == pytest.approx(100.0)


def test_candidate_list_is_the_preregistered_one():
    assert set(CANDIDATES) == {
        "trend_ema",
        "momentum_rsi",
        "volume_direction",
        "profile_value_area",
        "regime",
        "predictive",
        "donchian_20",
        "tsmom_180",
        "bollinger_20_2",
        "reversion_rsi",
        "control_random",
    }
