from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def analysis_factory() -> Callable[..., dict]:
    def build(**overrides):
        analysis = {
            "trend": "Alcista",
            "momentum": "Positivo",
            "volatility": "Baja",
            "volume": "Superior al promedio",
            "profile": "Dentro del área de valor",
            "score": 4,
            "market_context": "Alta confluencia, requiere confirmación",
            "price": 105.0,
            "rsi": 60.0,
            "atr": 2.0,
            "poc": 100.0,
            "vah": 104.0,
            "val": 96.0,
        }
        analysis.update(overrides)
        return analysis

    return build


@pytest.fixture
def profile() -> dict:
    return {"poc": 100.0, "vah": 104.0, "val": 96.0}


@pytest.fixture
def synthetic_ohlcv() -> pd.DataFrame:
    """240 closed, deterministic hourly candles; enough warm-up for EMA 200."""
    rows = 240
    timestamps = pd.date_range("2025-01-01", periods=rows, freq="h", tz="UTC")
    trend = np.linspace(100.0, 160.0, rows)
    cycle = np.sin(np.arange(rows) / 8.0) * 1.5
    close = trend + cycle
    open_ = close - 0.25
    high = np.maximum(open_, close) + 1.0
    low = np.minimum(open_, close) - 1.0
    volume = 1_000.0 + (np.arange(rows) % 24) * 20.0

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )

