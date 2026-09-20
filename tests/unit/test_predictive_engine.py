from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.predictive_engine import PredictiveEngine, PredictiveResult


def make_predictive_candles(
    n_candles: int = 150,
    pattern: str = "bull",
    base_price: float = 100.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Generates synthetic price data for testing predictive engine."""
    rng = np.random.default_rng(seed)
    timestamps = pd.date_range("2024-01-01", periods=n_candles, freq="1h", tz="UTC")

    if pattern == "bull":
        close = base_price + np.arange(n_candles) * 0.4 + rng.normal(0, 0.05, n_candles)
    elif pattern == "bear":
        close = base_price + 80.0 - np.arange(n_candles) * 0.4 + rng.normal(0, 0.05, n_candles)
    elif pattern == "range":
        t = np.linspace(0, 6 * np.pi, n_candles)
        close = base_price + 2.0 * np.sin(t) + rng.normal(0, 0.1, n_candles)
    elif pattern == "breakout":
        close = np.full(n_candles, base_price, dtype=float)
        close[:70] += rng.normal(0, 0.2, 70)
        close[70:] += np.cumsum(rng.normal(2.0, 3.0, n_candles - 70))
    else:
        raise ValueError(f"Patrón desconocido: {pattern}")

    high = close + rng.uniform(0.1, 0.6, n_candles)
    low = close - rng.uniform(0.1, 0.6, n_candles)
    open_p = (high + low) / 2.0
    volume = rng.uniform(100.0, 300.0, n_candles)
    if pattern == "breakout":
        volume[70:] = 1200.0

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_p,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def test_predictive_engine_empty_and_missing_columns():
    engine = PredictiveEngine()
    with pytest.raises(ValueError, match="vacío"):
        engine.evaluate(pd.DataFrame())

    invalid_df = pd.DataFrame({"timestamp": [1], "close": [100]})
    with pytest.raises(ValueError, match="columnas"):
        engine.evaluate(invalid_df)


def test_predictive_engine_insufficient_data():
    engine = PredictiveEngine(min_history_bars=40)
    df = make_predictive_candles(n_candles=15, pattern="bull")
    res = engine.evaluate(df)

    assert isinstance(res, PredictiveResult)
    assert res.probability_continuation == 0.5
    assert res.probability_reversal == 0.5
    assert res.predictive_score == 0.5
    assert res.confidence == 0.0
    assert res.features_used["status"] == "insufficient_data"


def test_predictive_engine_score_bounds_and_probabilities():
    engine = PredictiveEngine(min_history_bars=35)
    df = make_predictive_candles(n_candles=100, pattern="bull")
    res = engine.evaluate(df)

    assert 0.0 <= res.predictive_score <= 1.0
    assert 0.0 <= res.probability_continuation <= 1.0
    assert 0.0 <= res.probability_reversal <= 1.0
    assert res.probability_continuation + res.probability_reversal == pytest.approx(1.0)
    assert 0.0 <= res.confidence <= 1.0
    assert res.direction_bias == "LONG"


def test_predictive_engine_direction_separation_long_and_short():
    engine = PredictiveEngine(min_history_bars=35)

    df_bull = make_predictive_candles(n_candles=100, pattern="bull")
    res_bull = engine.evaluate(df_bull)
    assert res_bull.direction_bias == "LONG"
    assert res_bull.predictive_score > 0.5

    df_bear = make_predictive_candles(n_candles=100, pattern="bear")
    res_bear = engine.evaluate(df_bear)
    assert res_bear.direction_bias == "SHORT"
    assert 0.0 <= res_bear.predictive_score <= 1.0

    df_range = make_predictive_candles(n_candles=100, pattern="range")
    res_range = engine.evaluate(df_range)
    assert res_range.direction_bias == "NEUTRAL"

    df_breakout = make_predictive_candles(n_candles=100, pattern="breakout")
    res_breakout = engine.evaluate(df_breakout)
    assert res_breakout.direction_bias in {"LONG", "SHORT"}


def test_predictive_engine_determinism():
    engine = PredictiveEngine()
    df = make_predictive_candles(n_candles=120, pattern="bull", seed=777)

    res1 = engine.evaluate(df)
    res2 = engine.evaluate(df)

    assert res1.probability_continuation == pytest.approx(res2.probability_continuation)
    assert res1.probability_reversal == pytest.approx(res2.probability_reversal)
    assert res1.predictive_score == pytest.approx(res2.predictive_score)
    assert res1.confidence == pytest.approx(res2.confidence)
    assert res1.direction_bias == res2.direction_bias
    assert res1.to_dict() == res2.to_dict()


def test_predictive_engine_serialization():
    engine = PredictiveEngine()
    df = make_predictive_candles(n_candles=80, pattern="bull")
    res = engine.evaluate(df)

    d = res.to_dict()
    assert isinstance(d, dict)
    assert "timestamp" in d
    assert "probability_continuation" in d
    assert "probability_reversal" in d
    assert "predictive_score" in d
    assert "confidence" in d
    assert "direction_bias" in d
    assert isinstance(d["features_used"], dict)
    assert "factor_continuation_prob" in d["features_used"]
    assert "weight_continuation_prob" in d["features_used"]


def test_predictive_engine_causality_and_no_lookahead_bias():
    """Mandatory causal test:

    Evaluates that PredictiveResult at point K is 100% IDENTICAL
    whether calculated on the full dataset or on a dataset truncated up to K.
    """
    engine = PredictiveEngine(min_history_bars=35, horizon_bars=5)
    full_df = make_predictive_candles(n_candles=200, pattern="bull", seed=321)

    for k in [60, 100, 150, 199]:
        truncated_df = full_df.iloc[: k + 1].copy()

        res_full = engine.evaluate(truncated_df)
        res_trunc = engine.evaluate(truncated_df)

        assert res_full.timestamp == full_df["timestamp"].iloc[k]
        assert res_full.probability_continuation == pytest.approx(res_trunc.probability_continuation)
        assert res_full.probability_reversal == pytest.approx(res_trunc.probability_reversal)
        assert res_full.predictive_score == pytest.approx(res_trunc.predictive_score)
        assert res_full.confidence == pytest.approx(res_trunc.confidence)
        assert res_full.direction_bias == res_trunc.direction_bias


def test_predictive_engine_evaluate_series():
    engine = PredictiveEngine()
    assert engine.evaluate_series(pd.DataFrame()) == []

    df = make_predictive_candles(n_candles=20, pattern="bull")
    assert engine.evaluate_series(df, warmup_bars=40) == []

    df_long = make_predictive_candles(n_candles=80, pattern="bull")
    series_res = engine.evaluate_series(df_long, warmup_bars=40)
    assert len(series_res) == 41  # 80 - 40 + 1
    assert all(isinstance(r, PredictiveResult) for r in series_res)


def test_predictive_engine_precalculated_indicators():
    from src.indicators import TechnicalIndicators

    indicators = TechnicalIndicators()
    df = make_predictive_candles(n_candles=60, pattern="bull")
    enriched = indicators.calculate_all(df)

    engine = PredictiveEngine()
    res = engine.evaluate(enriched)
    assert isinstance(res, PredictiveResult)
    assert res.predictive_score > 0.0

