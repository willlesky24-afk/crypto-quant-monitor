"""v3.2 idea verifier. Verdict thresholds are checked on constructed samples."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.idea_verifier import (
    ENTRIES,
    EXPLORE_SHARE,
    METHODS,
    MIN_TRADES,
    IdeaSpec,
    IdeaVerifierError,
    ci_level,
    config_for,
    load_history,
    past_story,
    verdict_from,
    verify_idea,
    worst_streak,
)
from src.parquet_store import ParquetStore


def test_each_attempt_tightens_the_level():
    assert ci_level(1) == pytest.approx(0.95)
    assert ci_level(10) == pytest.approx(0.995)


def _sample(mean, n=400):
    # Half at mean+1, half at mean-1: exact mean, standard deviation 1.
    return [mean + 1.0, mean - 1.0] * (n // 2)


def test_too_few_trades():
    assert verdict_from(_sample(0.5, 20), [0.0] * 5, 1)["code"] == "POCAS_OPERACIONES"
    assert MIN_TRADES == 100


def test_clear_loser():
    # Mean -0.5, se 1/20 = 0.05: the interval is entirely below 0.
    assert verdict_from(_sample(-0.5), [0.0] * 5, 1)["code"] == "PIERDE"


def test_near_zero_is_not_distinguishable():
    assert verdict_from(_sample(0.01), [0.0] * 5, 1)["code"] == "NO_SE_DISTINGUE"


def test_positive_and_better_than_random_deserves_study():
    assert verdict_from(_sample(0.5), [0.0] * 5, 1)["code"] == "MERECE_ESTUDIO"


def test_positive_but_no_better_than_random_is_not_distinguishable():
    assert verdict_from(_sample(0.5), [0.1, 0.6], 1)["code"] == "NO_SE_DISTINGUE"


def test_many_attempts_can_remove_a_result():
    # Mean 0.13, se 0.05, 2.6 sigmas: clears 95%, not 1 - 0.05/1000.
    assert verdict_from(_sample(0.13), [0.0] * 5, 1)["code"] == "MERECE_ESTUDIO"
    assert verdict_from(_sample(0.13), [0.0] * 5, 1000)["code"] == "NO_SE_DISTINGUE"


def test_verdict_never_says_it_works():
    text = verdict_from(_sample(0.5), [0.0] * 5, 1)["text"].lower()
    for word in ("funciona", "rentable", "compra", "vende"):
        assert word not in text


def test_config_for_market_type():
    assert config_for("BTCUSDT", "AMBOS").direction == "LONG"
    forex = config_for("EURUSD=X", "AMBOS")
    assert (forex.market_type, forex.direction) == ("MARGIN_1X", "BOTH")
    assert forex.taker_fee_pct == 0.0
    assert config_for("EURUSD=X", "SHORT").direction == "SHORT"
    with pytest.raises(IdeaVerifierError):
        config_for("BTCUSDT", "SHORT")


def _candles(n=600):
    rng = np.random.default_rng(2)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.005, n)))
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-05", periods=n, freq="4h", tz="UTC"),
            "open": close,
            "high": close * 1.003,
            "low": close * 0.997,
            "close": close,
            "volume": rng.uniform(50, 150, n),
            "volume_average": 100.0,
            "atr": close * 0.004,
            "rsi": 50.0 + 25.0 * np.sin(np.arange(n) / 4.0),
            "ema_50": close * 0.99,
            "ema_200": close * 0.98,
        }
    )


def test_verify_uses_only_the_explore_part():
    df = _candles()
    spec = IdeaSpec("BTCUSDT", "4h", "reversion_rsi", "LONG", 1.0, 2.0, 24)
    result = verify_idea(df, spec, attempts=1, n_random=2)
    cut = df["timestamp"].iloc[int(len(df) * EXPLORE_SHARE) - 1]
    assert result["trades"] > 0
    assert result["last_entry"] <= cut
    assert result["reserved_bars"] == len(df) - int(len(df) * EXPLORE_SHARE)


def test_unknown_entry_rejected():
    spec = IdeaSpec("BTCUSDT", "4h", "magia", "LONG", 1.0, 2.0, 24)
    with pytest.raises(IdeaVerifierError):
        verify_idea(_candles(), spec, attempts=1)


def test_entries_are_a_closed_list():
    assert "reversion_rsi" in ENTRIES and "control_random" not in ENTRIES


def test_load_history_reads_each_universe_and_reports_absence(tmp_path):
    df = _candles()[["timestamp", "open", "high", "low", "close", "volume"]]
    df["timestamp"] = pd.date_range("2023-01-02", periods=len(df), freq="4h", tz="UTC")
    ParquetStore(tmp_path / "indices").save_dataset(
        df, "SPX500_OANDA", "4h", source="oanda"
    )
    loaded = load_history("SPX500=X", "4h", tmp_path)
    assert len(loaded) == len(df)
    assert {"atr", "rsi", "ema_50", "volume_average"} <= set(loaded.columns)
    assert load_history("BTCUSDT", "4h", tmp_path) is None


def test_load_history_never_returns_the_protected_test_period(tmp_path):
    df = _candles()[["timestamp", "open", "high", "low", "close", "volume"]]
    df["timestamp"] = pd.date_range("2024-11-01", periods=len(df), freq="4h", tz="UTC")
    ParquetStore(tmp_path / "evidence").save_dataset(
        df, "BTCUSDT_BINANCE", "4h", source="binance"
    )
    loaded = load_history("BTCUSDT", "4h", tmp_path)
    assert loaded["timestamp"].max() < pd.Timestamp("2025-01-01", tz="UTC")


def test_worst_streak_counts_consecutive_losses():
    assert worst_streak([1.0, -1.0, -2.0, 3.0, -1.0, -1.0, -1.0, 0.0, -1.0]) == 3
    assert worst_streak([]) == 0


def test_gallery_only_uses_available_entries():
    assert {m["entry"] for m in METHODS} <= set(ENTRIES)


def test_story_is_in_the_past_and_promises_nothing():
    text = past_story(
        {
            "trades": 10,
            "capital": 1000.0,
            "final_capital": 900.0,
            "worst_streak": 4,
            "max_drawdown_pct": 15.5,
            "hold_final": 1200.0,
            "first_date": "2022-01-01",
            "last_date": "2024-01-01",
        }
    )
    assert "habrías terminado con $900" in text and "4 pérdidas seguidas" in text
    assert "15.5 %" in text and "$1,200" in text
    assert "podría dar" not in text and "ganarás" not in text


def test_story_with_no_trades():
    assert "no habría operado" in past_story({"trades": 0})


def test_final_capital_adds_the_trades_and_hold_uses_prices():
    df = _candles()
    spec = IdeaSpec("BTCUSDT", "4h", "reversion_rsi", "LONG", 1.0, 2.0, 24)
    r = verify_idea(df, spec, attempts=1, n_random=1, capital=500.0)
    explore = df.iloc[: int(len(df) * EXPLORE_SHARE)]
    expected = 500.0 * explore["close"].iloc[-1] / explore["close"].iloc[0]
    assert r["hold_final"] == pytest.approx(expected)
    assert r["capital"] == 500.0
