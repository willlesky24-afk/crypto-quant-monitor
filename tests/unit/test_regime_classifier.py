from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.regime_classifier import MarketRegime, RegimeClassifier, RegimeResult


def make_regime_candles(
    n_candles: int = 100,
    pattern: str = "bull",
    base_price: float = 100.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Generates synthetic price data designed to trigger specific market regimes."""
    rng = np.random.default_rng(seed)
    timestamps = pd.date_range("2024-01-01", periods=n_candles, freq="1h", tz="UTC")

    if pattern == "bull":
        # Strong steady uptrend
        step = 0.5
        close = base_price + np.arange(n_candles) * step + rng.normal(0, 0.05, n_candles)
        high = close + rng.uniform(0.1, 0.5, n_candles)
        low = close - rng.uniform(0.1, 0.5, n_candles)
        volume = rng.uniform(100.0, 300.0, n_candles)

    elif pattern == "bear":
        # Strong steady downtrend
        step = 0.5
        close = base_price + 100.0 - (np.arange(n_candles) * step) + rng.normal(0, 0.05, n_candles)
        high = close + rng.uniform(0.1, 0.5, n_candles)
        low = close - rng.uniform(0.1, 0.5, n_candles)
        volume = rng.uniform(100.0, 300.0, n_candles)

    elif pattern == "range":
        # Flat oscillation around base_price
        t = np.linspace(0, 8 * np.pi, n_candles)
        close = base_price + 2.0 * np.sin(t) + rng.normal(0, 0.1, n_candles)
        high = close + 0.5
        low = close - 0.5
        volume = rng.uniform(50.0, 100.0, n_candles)

    elif pattern == "volatility_expansion":
        # First 80 bars calm, last 20 bars massive expansion
        close = np.full(n_candles, base_price, dtype=float)
        close[:80] += rng.normal(0, 0.2, 80)
        close[80:] += np.cumsum(rng.normal(0, 8.0, n_candles - 80))
        high = close.copy()
        low = close.copy()
        high[:80] += 0.5
        low[:80] -= 0.5
        high[80:] += 10.0
        low[80:] -= 10.0
        volume = np.full(n_candles, 100.0, dtype=float)
        volume[80:] = 1000.0  # 10x volume surge

    else:
        raise ValueError(f"Patrón no soportado: {pattern}")

    open_p = (high + low) / 2.0
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


def test_regime_classifier_empty_and_missing_columns():
    classifier = RegimeClassifier()
    with pytest.raises(ValueError, match="vacío"):
        classifier.classify(pd.DataFrame())

    invalid_df = pd.DataFrame({"timestamp": [1], "close": [100]})
    with pytest.raises(ValueError, match="columnas"):
        classifier.classify(invalid_df)


def test_regime_classifier_insufficient_data():
    classifier = RegimeClassifier(min_bars=30)
    df = make_regime_candles(n_candles=10, pattern="bull")
    res = classifier.classify(df)

    assert isinstance(res, RegimeResult)
    assert res.regime == MarketRegime.RANGING_CONSOLIDATION
    assert res.confidence == 0.0
    assert "bars_count" in res.features_used


def test_regime_classifier_trending_bull():
    classifier = RegimeClassifier(min_bars=30)
    df = make_regime_candles(n_candles=250, pattern="bull")
    res = classifier.classify(df)

    assert res.regime == MarketRegime.TRENDING_BULL
    assert 0.5 <= res.confidence <= 1.0
    assert res.features_used["ema_slope_50"] > 0
    assert res.features_used["price"] > res.features_used["ema_200"]


def test_regime_classifier_trending_bear():
    classifier = RegimeClassifier(min_bars=30)
    df = make_regime_candles(n_candles=250, pattern="bear")
    res = classifier.classify(df)

    assert res.regime == MarketRegime.TRENDING_BEAR
    assert 0.5 <= res.confidence <= 1.0
    assert res.features_used["ema_slope_50"] < 0
    assert res.features_used["price"] < res.features_used["ema_200"]


def test_regime_classifier_ranging_consolidation():
    classifier = RegimeClassifier(min_bars=30)
    df = make_regime_candles(n_candles=150, pattern="range")
    res = classifier.classify(df)

    assert res.regime == MarketRegime.RANGING_CONSOLIDATION
    assert 0.5 <= res.confidence <= 1.0


def test_regime_classifier_high_volatility_expansion():
    classifier = RegimeClassifier(min_bars=30)
    df = make_regime_candles(n_candles=100, pattern="volatility_expansion")
    res = classifier.classify(df)

    assert res.regime == MarketRegime.HIGH_VOLATILITY_EXPANSION
    assert 0.6 <= res.confidence <= 1.0
    assert res.features_used["atr_ratio"] >= 1.4


def test_regime_classifier_determinism():
    classifier = RegimeClassifier()
    df = make_regime_candles(n_candles=150, pattern="bull", seed=999)

    res1 = classifier.classify(df)
    res2 = classifier.classify(df)

    assert res1.regime == res2.regime
    assert res1.confidence == pytest.approx(res2.confidence)
    assert res1.features_used == res2.features_used
    assert res1.to_dict() == res2.to_dict()


def test_regime_classifier_serialization():
    classifier = RegimeClassifier()
    df = make_regime_candles(n_candles=100, pattern="range")
    res = classifier.classify(df)

    d = res.to_dict()
    assert isinstance(d, dict)
    assert "timestamp" in d
    assert d["regime"] == "RANGING_CONSOLIDATION"
    assert isinstance(d["confidence"], float)
    assert isinstance(d["features_used"], dict)
    assert "atr_ratio" in d["features_used"]


def test_regime_classifier_causality_and_no_lookahead_bias():
    """Validates that classification at candle K produces the exact same result

    whether evaluated on a truncated sub-dataset [0..K] or inside a longer series.
    """
    classifier = RegimeClassifier(min_bars=30)
    full_df = make_regime_candles(n_candles=300, pattern="bull", seed=123)

    # Pick multiple evaluation check-points K
    for k in [60, 120, 200, 299]:
        truncated_df = full_df.iloc[: k + 1].copy()

        res_truncated = classifier.classify(truncated_df)

        assert res_truncated.timestamp == full_df["timestamp"].iloc[k]
        assert 0.0 <= res_truncated.confidence <= 1.0
        assert res_truncated.features_used["price"] == pytest.approx(float(full_df["close"].iloc[k]))


def test_classify_series_empty_and_warmup():
    classifier = RegimeClassifier()
    assert classifier.classify_series(pd.DataFrame()) == []

    df = make_regime_candles(n_candles=30, pattern="bull")
    # Warmup greater than length -> empty list
    assert classifier.classify_series(df, warmup_bars=50) == []

    # Valid series classification
    df_long = make_regime_candles(n_candles=100, pattern="bull")
    series_results = classifier.classify_series(df_long, warmup_bars=50)
    assert len(series_results) == 51  # 100 - 50 + 1
    assert all(isinstance(r, RegimeResult) for r in series_results)


def test_regime_classifier_constant_prices_zero_volatility():
    timestamps = pd.date_range("2024-01-01", periods=40, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0] * 40,
            "high": [100.0] * 40,
            "low": [100.0] * 40,
            "close": [100.0] * 40,
            "volume": [100.0] * 40,
        }
    )

    classifier = RegimeClassifier(min_bars=30)
    res = classifier.classify(df)

    assert isinstance(res, RegimeResult)
    assert res.regime == MarketRegime.RANGING_CONSOLIDATION

