"""v3.0 D4/D5 evidence statistics. Expected values derived by hand."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from src.evidence_evaluation import (
    PERIODS,
    SuccessCriteria,
    assign_period,
    bootstrap_mean_ci,
    evaluate_criteria,
    monte_carlo_drawdown,
    summarize_trades,
)


def _t(net_pnl, net_r, ret_pct, ts="2025-03-01", symbol="EURUSD=X"):
    return SimpleNamespace(
        net_pnl=net_pnl,
        net_r_multiple=net_r,
        net_return_pct=ret_pct,
        entry_timestamp=pd.Timestamp(ts, tz="UTC"),
        symbol=symbol,
    )


def test_periods_are_the_preregistered_ones():
    assert PERIODS["train"] == ("2021-11-01", "2024-01-01")
    assert PERIODS["validation"] == ("2024-01-01", "2025-01-01")
    assert PERIODS["test"] == ("2025-01-01", "2026-11-01")


@pytest.mark.parametrize(
    "ts,period",
    [
        ("2023-12-31 23:00", "train"),
        ("2024-01-01 00:00", "validation"),
        ("2024-12-31 23:00", "validation"),
        ("2025-01-01 00:00", "test"),
        ("2026-11-01 00:00", None),
    ],
)
def test_assign_period_boundaries(ts, period):
    assert assign_period(pd.Timestamp(ts, tz="UTC")) == period


def test_summary_profit_factor_and_expectancy():
    # net pnl +200, -100, -100, +300 -> PF = 500 / 200 = 2.5
    # net R 2, -1, -1, 3 -> mean 0.75 ; win rate 50%
    trades = [_t(200, 2, 2), _t(-100, -1, -1), _t(-100, -1, -1), _t(300, 3, 3)]
    s = summarize_trades(trades)
    assert s["trades"] == 4
    assert s["profit_factor"] == pytest.approx(2.5)
    assert s["expectancy_r"] == pytest.approx(0.75)
    assert s["win_rate_pct"] == pytest.approx(50.0)


def test_summary_without_losses_has_no_finite_pf():
    s = summarize_trades([_t(10, 1, 1)])
    assert s["profit_factor"] is None


def test_bootstrap_constant_sample_has_degenerate_ci():
    lo, hi = bootstrap_mean_ci([0.5] * 30, n_boot=500, seed=1)
    assert lo == pytest.approx(0.5) and hi == pytest.approx(0.5)


def test_bootstrap_ci_brackets_mean_and_is_reproducible():
    data = [-1.0, 2.0, -1.0, 2.0, -1.0, 2.0, -1.0, 0.5] * 5
    a = bootstrap_mean_ci(data, n_boot=2000, seed=7)
    b = bootstrap_mean_ci(data, n_boot=2000, seed=7)
    assert a == b
    assert a[0] < sum(data) / len(data) < a[1]


def test_monte_carlo_drawdown_symmetric_case():
    # Returns +10% and -10% in any order: 1.0 -> 1.1 -> 0.99 (DD 10% from 1.1)
    # or 1.0 -> 0.9 -> 0.99 (DD 10% from 1.0). Every permutation: 10%.
    p95 = monte_carlo_drawdown([10.0, -10.0], n_sims=200, seed=3)
    assert p95 == pytest.approx(10.0)


def test_criteria_pass_and_fail_reasons():
    crit = SuccessCriteria()
    ok = {
        "trades": 150,
        "profit_factor": 1.3,
        "expectancy_ci_low": 0.02,
        "mc_drawdown_p95_pct": 15.0,
        "positive_instruments_pct": 65.0,
    }
    assert evaluate_criteria(ok, crit) == (True, [])
    bad = dict(ok, profit_factor=1.1, trades=90)
    passed, reasons = evaluate_criteria(bad, crit)
    assert not passed
    assert any("profit_factor" in r for r in reasons)
    assert any("trades" in r for r in reasons)


def test_criteria_missing_value_fails_closed():
    crit = SuccessCriteria()
    passed, reasons = evaluate_criteria(
        {
            "trades": 150,
            "profit_factor": None,
            "expectancy_ci_low": 0.1,
            "mc_drawdown_p95_pct": 5.0,
            "positive_instruments_pct": 80.0,
        },
        crit,
    )
    assert not passed and any("profit_factor" in r for r in reasons)


def test_default_criteria_are_the_approved_ones():
    c = SuccessCriteria()
    assert (c.min_profit_factor, c.min_trades, c.max_mc_drawdown_pct) == (
        1.2,
        100,
        20.0,
    )
    assert c.min_positive_instruments_pct == 60.0
    assert c.min_expectancy_ci_low == 0.0
