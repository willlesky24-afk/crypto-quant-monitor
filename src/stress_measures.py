"""v3.1 stress: is the price growing explosively right now?

Backward SADF (Phillips, Shi, Yu 2015, International Economic Review 56(4)): the
largest ADF statistic over all windows that end at the latest bar. It describes
a state; it does not date a collapse, and it lags the start of a run-up.

- Minimum window r0 = 0.01 + 1.8/sqrt(T): rule attributed to that paper, confirmed
  in secondary sources only. [VERIFICAR] against the paper.
- Must hold for log(T) consecutive bars: the same paper's suggestion, also via a
  secondary source. [VERIFICAR]
- Lag order 0 and the 400-bar lookback are project choices.
- Critical values are simulated from random walks here, with a fixed seed, so
  no table value is copied from memory. They use a Bonferroni level for the
  number of tests. Only upward explosiveness is tested, by construction.
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
import pandas as pd

LOOKBACK_BARS = 400
ALPHA = 0.05
CRITICAL_SEED = 20261104
CRITICAL_SIMS = 20_000


def min_window(t: int) -> int:
    return int(math.floor((0.01 + 1.8 / math.sqrt(t)) * t))


def _bsadf(y: np.ndarray, window: int) -> np.ndarray:
    """Sup ADF for paths in rows, from cumulative OLS sums run back from the end."""
    y = np.atleast_2d(y)
    y = y - y[:, -1:]  # the statistic ignores the level; this protects precision
    x = y[:, -2::-1]
    d = (y[:, 1:] - y[:, :-1])[:, ::-1]
    n = np.arange(1, x.shape[1] + 1)
    sx, sd = x.cumsum(1), d.cumsum(1)
    sxx, sxd, sdd = (x * x).cumsum(1), (x * d).cumsum(1), (d * d).cumsum(1)
    den = n * sxx - sx * sx
    with np.errstate(divide="ignore", invalid="ignore"):
        b = (n * sxd - sx * sd) / den
        a = (sd - b * sx) / n
        rss = sdd - a * sd - b * sxd
        t = b / np.sqrt(rss / (n - 2) * n / den)
    return np.nanmax(t[:, window - 1 :], axis=1)


def bsadf_last(y: np.ndarray, window: int) -> float:
    """``window`` counts regression observations, so a window's path has one more."""
    return float(_bsadf(np.asarray(y, dtype=float), window)[0])


def bsadf_series(close: pd.Series, lookback: int, window: int) -> pd.Series:
    values = close.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    for end in range(lookback - 1, len(values)):
        out[end] = bsadf_last(values[end - lookback + 1 : end + 1], window)
    return pd.Series(out, index=close.index)


@lru_cache(maxsize=32)
def critical_value(t: int, level: float, n_sims: int = CRITICAL_SIMS) -> float:
    rng = np.random.default_rng(CRITICAL_SEED)
    window = min_window(t)
    stats = [
        _bsadf(rng.normal(size=(min(2000, n_sims - i), t)).cumsum(1), window)
        for i in range(0, n_sims, 2000)
    ]
    return float(np.quantile(np.concatenate(stats), level))


def explosive_status(
    close: pd.Series,
    tests: int,
    lookback: int = LOOKBACK_BARS,
    n_sims: int = CRITICAL_SIMS,
) -> dict[str, object]:
    """``explosive`` is None when the history is too short to test."""
    log_price = np.log(close.dropna().to_numpy(dtype=float))
    duration = max(1, int(math.log(lookback)))
    if len(log_price) < lookback + duration:
        return {"explosive": None, "statistic": None, "critical": None}
    window = min_window(lookback)
    level = 1.0 - ALPHA / tests
    critical = critical_value(lookback, level, n_sims)
    recent = pd.Series(log_price[-(lookback + duration - 1) :])
    stats = bsadf_series(recent, lookback, window).dropna()
    return {
        "explosive": bool((stats > critical).all()),
        "statistic": float(stats.iloc[-1]),
        "critical": critical,
    }
