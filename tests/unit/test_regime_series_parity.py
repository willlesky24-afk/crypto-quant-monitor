"""The fast series must equal classifying each bar on its own (reference: classify)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.indicators import TechnicalIndicators
from src.regime_classifier import RegimeClassifier


def _candles(n=400, seed=7):
    rng = np.random.default_rng(seed)
    # Calm, then a volatile stretch, so that all regimes can appear.
    scale = np.where(np.arange(n) % 120 < 25, 0.03, 0.004)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0002, scale)))
    spread = close * scale
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC"),
            "open": close,
            "high": close + spread,
            "low": close - spread,
            "close": close,
            "volume": rng.uniform(50, 200, n),
        }
    )


@pytest.mark.parametrize("warmup", [25, 50])
def test_series_equals_bar_by_bar(warmup):
    df = _candles()
    clf = RegimeClassifier()
    fast = clf.classify_series(df, warmup_bars=warmup)
    enriched = TechnicalIndicators().calculate_all(df.copy())
    slow = [
        clf.classify(enriched.iloc[: i + 1]) for i in range(warmup - 1, len(enriched))
    ]
    assert len(fast) == len(slow)
    assert len({r.regime for r in slow}) >= 3  # the data really exercises branches
    for a, b in zip(fast, slow, strict=True):
        assert a.timestamp == b.timestamp
        assert a.regime == b.regime
        assert a.confidence == pytest.approx(b.confidence, abs=1e-9)
        assert a.features_used.keys() == b.features_used.keys()
        for key, value in a.features_used.items():
            assert value == pytest.approx(b.features_used[key], rel=1e-9, abs=1e-9)
