"""v3.1 explosiveness test. References: independent OLS and simulated known truths."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.stress_measures import (
    bsadf_last,
    bsadf_series,
    critical_value,
    explosive_status,
    min_window,
)


def _ols_t(y):
    """Independent reference: textbook OLS with numpy's least squares."""
    dy, lag = np.diff(y), y[:-1]
    x = np.column_stack([np.ones(len(lag)), lag])
    coef = np.linalg.lstsq(x, dy, rcond=None)[0]
    resid = dy - x @ coef
    s2 = resid @ resid / (len(dy) - 2)
    return coef[1] / np.sqrt(s2 * np.linalg.inv(x.T @ x)[1, 1])


def test_min_window_rule():
    # T=400: 0.01 + 1.8/20 = 0.10, so 40 bars.
    assert min_window(400) == 40


def test_bsadf_is_the_largest_adf_over_all_start_points():
    y = np.cumsum(np.random.default_rng(3).normal(size=60))
    expected = max(_ols_t(y[s:]) for s in range(0, 60 - 20))
    assert bsadf_last(y, window=20) == pytest.approx(expected, rel=1e-8)


def test_series_equals_last_value_on_each_cut():
    y = np.cumsum(np.random.default_rng(4).normal(size=80))
    series = bsadf_series(pd.Series(y), lookback=50, window=20)
    assert series.iloc[:49].isna().all()
    assert series.iloc[79] == pytest.approx(bsadf_last(y[30:], 20), rel=1e-9)
    assert series.iloc[60] == pytest.approx(bsadf_last(y[11:61], 20), rel=1e-9)


def test_random_walks_exceed_the_95_value_about_5_percent():
    # Fresh seed, different from the one that built the critical value.
    t, cv = 100, critical_value(100, 0.95, n_sims=4000)
    rng = np.random.default_rng(999)
    hits = sum(
        bsadf_last(np.cumsum(rng.normal(size=t)), min_window(t)) > cv
        for _ in range(1000)
    )
    assert 25 <= hits <= 80  # 5% of 1000 is 50; about 3 standard errors around it


def test_explosive_series_is_detected():
    rng = np.random.default_rng(5)
    y = list(np.cumsum(rng.normal(0, 0.01, 400)))
    for _ in range(50):
        y.append(y[-1] + 0.03 * max(1.0, abs(y[-1])) + rng.normal(0, 0.01))
    close = pd.Series(np.exp(np.array(y)))
    status = explosive_status(close, tests=1, n_sims=2000)
    assert status["explosive"] is True


def test_quiet_series_is_not_detected():
    y = np.cumsum(np.random.default_rng(6).normal(0, 0.01, 450))
    status = explosive_status(pd.Series(np.exp(y)), tests=1, n_sims=2000)
    assert status["explosive"] is False


def test_short_history_is_unavailable():
    assert explosive_status(pd.Series([1.0] * 50), tests=1)["explosive"] is None
