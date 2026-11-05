"""v3.1 radar. Expected values are worked by hand from the stated series."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.unusual_radar import (
    MIN_HISTORY_BARS,
    build_markets,
    first_episodes,
    history_from_mask,
    run_radar,
    tail_share,
)


def test_tail_share_low_counts_prior_values_at_or_below_current():
    # Prior 1,2,3,4; current 2: 2 of 4 at or below.
    assert tail_share(pd.Series([1.0, 2.0, 3.0, 4.0, 2.0]), "low", 2) == 0.5


def test_tail_share_high():
    # Prior 1,2,3,4; current 4: 1 of 4 at or above.
    assert tail_share(pd.Series([1.0, 2.0, 3.0, 4.0, 4.0]), "high", 2) == 0.25


def test_tail_share_needs_history():
    assert tail_share(pd.Series([1.0, 2.0]), "low", 5) is None


def test_first_episodes_merge_nearby_bars():
    mask = pd.Series([False, True, True, False, True, False, False, True])
    # Keeps 1; 2 is 1 away; 4 is 3 away, so it counts; 7 is 3 from 4, so it counts.
    assert first_episodes(mask, gap=3) == [1, 4, 7]


def test_history_counts_cases_and_baseline():
    # Horizon 2, k 2, ATR 1, so a big move is |close[t+2]-close[t]| > 2.
    close = pd.Series([100.0, 100.0, 103.0, 103.0, 103.0, 103.0, 103.0, 103.0])
    atr = pd.Series([1.0] * 8)
    mask = pd.Series([True, False, False, False, True, False, False, True])
    # Valid bars 0..5. Moves: t0 3 big, t1 3 big, t2..t5 0. Baseline 2/6 = 33.3%.
    # Episodes (gap 2): 0, 4 and 7. 7 has no future yet. Cases 2, big 1.
    h = history_from_mask(mask, close, atr, horizon=2, k=2.0)
    assert h["cases"] == 2
    assert h["big_moves"] == 1
    assert h["baseline_pct"] == pytest.approx(100.0 * 2 / 6)


def test_big_move_uses_typical_atr_not_the_compressed_one():
    # ATR collapses at t=4 to 0.1. Move to t+2 is 1: above 2 x 0.1, but the median
    # ATR of the bars so far is 1, so 2 x 1 says it is not a big move.
    close = pd.Series([100.0] * 5 + [100.5, 101.0, 101.0])
    atr = pd.Series([1.0, 1.0, 1.0, 1.0, 0.1, 0.1, 0.1, 0.1])
    mask = pd.Series([False] * 4 + [True] + [False] * 3)
    h = history_from_mask(mask, close, atr, horizon=2, k=2.0)
    assert (h["cases"], h["big_moves"]) == (1, 0)


def _market(n, seed, atr=None):
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=n, freq="4h", tz="UTC"),
            "close": close,
            "atr": close * 0.01 if atr is None else atr,
        }
    )


def test_compression_alert_fires_on_the_lowest_atr_ever():
    n = MIN_HISTORY_BARS + 50
    m = _market(n, 1)
    m["atr"] = m["close"] * (0.01 + 0.002 * np.sin(np.arange(n) / 5.0))
    m.loc[n - 1, "atr"] = m["close"].iloc[-1] * 0.0001
    r = run_radar({"AAA": m}, groups=[], pairs=[])
    assert r.tests == 1
    assert r.alpha == pytest.approx(0.05)
    assert [a.measure for a in r.alerts] == ["compresion"]
    assert "vez" in r.alerts[0].text or "veces" in r.alerts[0].text


def test_more_tests_mean_a_stricter_bar():
    n = MIN_HISTORY_BARS + 100  # the correlation needs 61 bars before its first value
    markets = {"AAA": _market(n, 1), "BBB": _market(n, 2), "CCC": _market(n, 3)}
    r = run_radar(markets, groups=[["AAA", "BBB", "CCC"]], pairs=[("AAA", "BBB")])
    # 3 compression + 3 relative strength + 1 correlation.
    assert r.tests == 7
    assert r.alpha == pytest.approx(0.05 / 7)


def test_short_history_is_not_tested():
    r = run_radar({"AAA": _market(50, 1)}, groups=[], pairs=[])
    assert r.tests == 0 and r.alerts == []


def test_alert_text_never_suggests_action():
    n = MIN_HISTORY_BARS + 50
    m = _market(n, 1)
    m.loc[n - 1, "atr"] = 1e-9
    text = run_radar({"AAA": m}, groups=[], pairs=[]).alerts[0].text.lower()
    for word in ("compra", "vende", "oportunidad"):
        assert word not in text


def test_build_markets_reports_failures_instead_of_hiding_them():
    def fetch(symbol):
        if symbol == "BAD":
            raise ValueError("sin datos")
        return _market(10, 1)

    markets, failed = build_markets(fetch, ["OK", "BAD"])
    assert list(markets) == ["OK"]
    assert failed == {"BAD": "sin datos"}
