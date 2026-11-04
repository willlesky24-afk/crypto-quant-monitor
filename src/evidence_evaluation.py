"""v3.0 evidence protocol: fixed periods, robust statistics, success criteria.

Pre-registered before looking at results (supervisor approval, v3.0 D4/D5):
- Periods: train 2021-11-01..2023-12-31, validation 2024, test
  2025-01-01..2026-10-31. The test period is evaluated once.
- Success (test period, net of costs): profit factor >= 1.2; 95% bootstrap
  CI of mean net R entirely above 0; >= 100 trades; Monte Carlo 95th
  percentile max drawdown <= 20%; >= 60% of instruments with positive net PnL.

Statistics are deterministic given a seed so any report can be reproduced.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

PERIODS: dict[str, tuple[str, str]] = {
    "train": ("2021-11-01", "2024-01-01"),
    "validation": ("2024-01-01", "2025-01-01"),
    "test": ("2025-01-01", "2026-11-01"),
}


@dataclass(frozen=True)
class SuccessCriteria:
    min_profit_factor: float = 1.2
    min_expectancy_ci_low: float = 0.0
    min_trades: int = 100
    max_mc_drawdown_pct: float = 20.0
    min_positive_instruments_pct: float = 60.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assign_period(ts: pd.Timestamp) -> str | None:
    """Period of a trade by its entry time (half-open intervals, UTC)."""
    for name, (start, end) in PERIODS.items():
        if pd.Timestamp(start, tz="UTC") <= ts < pd.Timestamp(end, tz="UTC"):
            return name
    return None


def summarize_trades(trades: list[Any]) -> dict[str, Any]:
    """Profit factor on net PnL, expectancy as mean net R, win rate."""
    n = len(trades)
    pnl = np.array([float(t.net_pnl) for t in trades], dtype=float)
    r = np.array(
        [
            float(t.net_r_multiple)
            for t in trades
            if t.net_r_multiple is not None and math.isfinite(t.net_r_multiple)
        ],
        dtype=float,
    )
    gains = float(pnl[pnl > 0].sum()) if n else 0.0
    losses = float(-pnl[pnl < 0].sum()) if n else 0.0
    return {
        "trades": n,
        "net_pnl": float(pnl.sum()) if n else 0.0,
        "profit_factor": (gains / losses) if losses > 0 else None,
        "expectancy_r": float(r.mean()) if r.size else None,
        "win_rate_pct": float((pnl > 0).mean() * 100.0) if n else None,
        "r_trades": int(r.size),
    }


def bootstrap_mean_ci(
    values: list[float], n_boot: int = 10_000, seed: int = 20261101, level: float = 0.95
) -> tuple[float, float]:
    """Percentile bootstrap CI of the mean (resampling trades with replacement)."""
    data = np.asarray(values, dtype=float)
    if data.size == 0:
        raise ValueError("bootstrap_mean_ci requiere al menos un valor.")
    rng = np.random.default_rng(seed)
    means = rng.choice(data, size=(n_boot, data.size), replace=True).mean(axis=1)
    alpha = (1.0 - level) / 2.0
    return float(np.quantile(means, alpha)), float(np.quantile(means, 1.0 - alpha))


def _max_drawdown_pct(returns_pct: np.ndarray) -> float:
    equity = np.concatenate(([1.0], np.cumprod(1.0 + returns_pct / 100.0)))
    peaks = np.maximum.accumulate(equity)
    return float(((peaks - equity) / peaks).max() * 100.0)


def monte_carlo_drawdown(
    returns_pct: list[float], n_sims: int = 5_000, seed: int = 20261101, q: float = 0.95
) -> float:
    """q-quantile of max drawdown over random reorderings of trade returns.

    Each trade return is a percentage of the capital committed to it (the
    engine commits 100% of equity per trade), compounded in sequence.
    """
    data = np.asarray(returns_pct, dtype=float)
    if data.size == 0:
        raise ValueError("monte_carlo_drawdown requiere al menos un retorno.")
    rng = np.random.default_rng(seed)
    dds = [_max_drawdown_pct(rng.permutation(data)) for _ in range(n_sims)]
    return float(np.quantile(dds, q))


def evaluate_criteria(
    stats: dict[str, Any], criteria: SuccessCriteria
) -> tuple[bool, list[str]]:
    """Fail closed: a missing or non-finite statistic is a failed criterion."""
    checks = [
        ("trades", ">=", criteria.min_trades),
        ("profit_factor", ">=", criteria.min_profit_factor),
        ("expectancy_ci_low", ">", criteria.min_expectancy_ci_low),
        ("mc_drawdown_p95_pct", "<=", criteria.max_mc_drawdown_pct),
        ("positive_instruments_pct", ">=", criteria.min_positive_instruments_pct),
    ]
    reasons = []
    for key, op, threshold in checks:
        value = stats.get(key)
        valid = isinstance(value, (int, float)) and math.isfinite(value)
        ok = valid and (
            value >= threshold
            if op == ">="
            else value > threshold
            if op == ">"
            else value <= threshold
        )
        if not ok:
            reasons.append(f"{key}={value!r} no cumple {op} {threshold}")
    return (not reasons, reasons)
