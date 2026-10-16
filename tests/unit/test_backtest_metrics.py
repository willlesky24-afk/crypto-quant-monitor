from __future__ import annotations

import math

import pandas as pd
import pytest

from src.backtest_metrics import CRYPTO_24_7_PERIODS, BacktestMetricsCalculator
from src.backtest_models import EquityPoint, TradeResult


def create_sample_trade(
    trade_id: str,
    net_pnl: float,
    r_multiple: float = 1.0,
    mfe_pct: float = 2.0,
    mae_pct: float = 1.0,
    bars_held: int = 5,
    gross_pnl: float | None = None,
    fee_entry: float = 5.0,
    fee_exit: float = 5.0,
) -> TradeResult:
    ts = pd.to_datetime("2024-01-01", utc=True)
    if gross_pnl is None:
        gross_pnl = net_pnl + fee_entry + fee_exit

    return TradeResult(
        trade_id=trade_id,
        symbol="BTCUSDT",
        timeframe="1h",
        direction="LONG",
        signal_timestamp=ts,
        entry_timestamp=ts,
        exit_timestamp=ts + pd.Timedelta(hours=bars_held),
        entry_price=100.0,
        exit_price=100.0 + net_pnl,
        size_units=1.0,
        notional_entry=100.0,
        notional_exit=100.0 + net_pnl,
        gross_pnl=gross_pnl,
        fee_entry=fee_entry,
        fee_exit=fee_exit,
        net_pnl=net_pnl,
        net_return_pct=(net_pnl / 100.0) * 100.0,
        r_multiple=r_multiple,
        bars_held=bars_held,
        exit_reason="TAKE_PROFIT" if net_pnl > 0 else "STOP_LOSS",
        mfe_pct=mfe_pct,
        mae_pct=mae_pct,
        is_win=net_pnl > 0,
    )


def test_metrics_empty_trades():
    metrics = BacktestMetricsCalculator.calculate_metrics([], [], initial_capital=10_000.0)
    assert metrics["total_trades"] == 0
    assert metrics["win_rate_pct"] == 0.0
    assert metrics["profit_factor"] == 0.0
    assert metrics["expectancy"] == 0.0
    assert metrics["max_drawdown_pct"] == 0.0
    assert metrics["sharpe_ratio"] is None
    assert metrics["calmar_ratio"] is None


def test_metrics_all_winning_trades():
    trades = [
        create_sample_trade("t1", 200.0, r_multiple=2.0, mfe_pct=3.0, mae_pct=0.5),
        create_sample_trade("t2", 100.0, r_multiple=1.0, mfe_pct=2.0, mae_pct=0.2),
    ]
    eq = [
        EquityPoint(pd.to_datetime("2024-01-01", utc=True), 10000.0, 10000.0, 0.0),
        EquityPoint(pd.to_datetime("2024-01-02", utc=True), 10200.0, 10200.0, 0.0),
        EquityPoint(pd.to_datetime("2024-01-03", utc=True), 10300.0, 10300.0, 0.0),
    ]
    metrics = BacktestMetricsCalculator.calculate_metrics(trades, eq, initial_capital=10_000.0)

    assert metrics["total_trades"] == 2
    assert metrics["winning_trades"] == 2
    assert metrics["losing_trades"] == 0
    assert metrics["win_rate_pct"] == 100.0
    assert metrics["profit_factor"] == math.inf
    assert metrics["payoff_ratio"] == math.inf
    assert metrics["expectancy"] == 150.0
    assert metrics["expectancy_r"] == 1.5
    assert metrics["total_net_pnl"] == 300.0
    assert metrics["return_on_capital_pct"] == 3.0


def test_metrics_all_losing_trades():
    trades = [
        create_sample_trade("t1", -100.0, r_multiple=-1.0, mfe_pct=0.5, mae_pct=1.5),
        create_sample_trade("t2", -50.0, r_multiple=-0.5, mfe_pct=0.2, mae_pct=1.0),
    ]
    eq = [
        EquityPoint(pd.to_datetime("2024-01-01", utc=True), 10000.0, 10000.0, 0.0),
        EquityPoint(pd.to_datetime("2024-01-02", utc=True), 9900.0, 9900.0, 1.0),
        EquityPoint(pd.to_datetime("2024-01-03", utc=True), 9850.0, 9850.0, 1.5),
    ]
    metrics = BacktestMetricsCalculator.calculate_metrics(trades, eq, initial_capital=10_000.0)

    assert metrics["total_trades"] == 2
    assert metrics["winning_trades"] == 0
    assert metrics["losing_trades"] == 2
    assert metrics["win_rate_pct"] == 0.0
    assert metrics["profit_factor"] == 0.0
    assert metrics["payoff_ratio"] == 0.0
    assert metrics["expectancy"] == -75.0
    assert metrics["expectancy_r"] == -0.75
    assert metrics["total_net_pnl"] == -150.0


def test_metrics_mixed_trades_expectancy_and_ratios():
    # 3 wins (+200, +100, +300), 2 losses (-100, -100)
    # Total wins = 600, total losses = 200
    # Win rate = 60%, Loss rate = 40%
    # Avg win = 200, Avg loss = 100
    # Profit factor = 600 / 200 = 3.0
    # Payoff ratio = 200 / 100 = 2.0
    # Expectancy = (0.6 * 200) - (0.4 * 100) = 120 - 40 = 80.0
    trades = [
        create_sample_trade("t1", 200.0, r_multiple=2.0, mfe_pct=3.0, mae_pct=0.5, bars_held=4),
        create_sample_trade("t2", -100.0, r_multiple=-1.0, mfe_pct=0.5, mae_pct=1.2, bars_held=2),
        create_sample_trade("t3", 100.0, r_multiple=1.0, mfe_pct=1.8, mae_pct=0.3, bars_held=3),
        create_sample_trade("t4", -100.0, r_multiple=-1.0, mfe_pct=0.2, mae_pct=1.5, bars_held=2),
        create_sample_trade("t5", 300.0, r_multiple=3.0, mfe_pct=4.0, mae_pct=0.6, bars_held=5),
    ]

    eq = [
        EquityPoint(pd.to_datetime("2024-01-01", utc=True), 10000.0, 10000.0, 0.0),
        EquityPoint(pd.to_datetime("2024-01-02", utc=True), 10200.0, 10200.0, 0.0),
        EquityPoint(pd.to_datetime("2024-01-03", utc=True), 10100.0, 10100.0, 0.98),
        EquityPoint(pd.to_datetime("2024-01-04", utc=True), 10200.0, 10200.0, 0.0),
        EquityPoint(pd.to_datetime("2024-01-05", utc=True), 10100.0, 10100.0, 0.98),
        EquityPoint(pd.to_datetime("2024-01-06", utc=True), 10400.0, 10400.0, 0.0),
    ]

    metrics = BacktestMetricsCalculator.calculate_metrics(
        trades, eq, initial_capital=10_000.0,
        periods_per_year=365, expected_interval=pd.Timedelta(days=1),
    )

    assert metrics["total_trades"] == 5
    assert metrics["winning_trades"] == 3
    assert metrics["losing_trades"] == 2
    assert metrics["win_rate_pct"] == 60.0
    assert metrics["profit_factor"] == 3.0
    assert metrics["payoff_ratio"] == 2.0
    assert metrics["expectancy"] == 80.0
    assert metrics["expectancy_r"] == 0.8
    assert metrics["avg_bars_held"] == 3.2
    assert metrics["avg_mfe_pct"] == pytest.approx(1.9, rel=1e-2)
    assert metrics["avg_mae_pct"] == pytest.approx(0.82, rel=1e-2)
    assert metrics["total_net_pnl"] == 400.0
    assert metrics["return_on_capital_pct"] == 4.0
    assert metrics["sharpe_ratio"] is not None
    assert metrics["calmar_ratio"] is not None


def test_drawdown_series_calculation():
    # Peak at 100, drops to 80 (20% DD, 20 USD), recovers to 110, drops to 99 (10% DD, 11 USD)
    equity = [100.0, 95.0, 80.0, 90.0, 110.0, 99.0, 115.0]
    dd_series, max_dd_pct, max_dd_usd, max_dur = BacktestMetricsCalculator.calculate_drawdown_series(equity)

    assert max_dd_pct == 20.0
    assert max_dd_usd == 20.0
    assert max_dur == 3  # index 1, 2, 3 before reaching 110 at index 4
    assert len(dd_series) == len(equity)
    assert dd_series[0] == 0.0
    assert dd_series[2] == 20.0
    assert dd_series[4] == 0.0


def test_drawdown_series_empty():
    dd_series, max_dd_pct, max_dd_usd, max_dur = BacktestMetricsCalculator.calculate_drawdown_series([])
    assert dd_series == []
    assert max_dd_pct == 0.0
    assert max_dd_usd == 0.0
    assert max_dur == 0


@pytest.mark.parametrize(
    ("equity", "expected_series", "max_pct", "max_amount", "duration"),
    [
        ([950.0], [5.0], 5.0, 50.0, 1),
        ([1000.0, 950.0, 1100.0, 990.0], [0.0, 5.0, 0.0, 10.0], 10.0, 110.0, 1),
        ([1000.0, 1050.0, 1100.0], [0.0, 0.0, 0.0], 0.0, 0.0, 0),
        ([1000.0, 1000.0, 1000.0], [0.0, 0.0, 0.0], 0.0, 0.0, 0),
        ([1000.0, 0.0], [0.0, 100.0], 100.0, 1000.0, 1),
        ([1050.0, 1029.0], [0.0, 2.0], 2.0, 21.0, 1),
        ([1000.0, 950.0, 900.0, 1000.0], [0.0, 5.0, 10.0, 0.0], 10.0, 100.0, 2),
        ([1000.0, 800.0, 2000.0, 1700.0], [0.0, 20.0, 0.0, 15.0], 20.0, 300.0, 1),
    ],
)
def test_drawdown_uses_initial_capital_and_separate_maxima(
    equity, expected_series, max_pct, max_amount, duration
):
    actual = BacktestMetricsCalculator.calculate_drawdown_series(
        equity, initial_equity=1000.0
    )
    assert actual[0] == pytest.approx(expected_series)
    assert actual[1:] == pytest.approx((max_pct, max_amount, duration))


def test_drawdown_legacy_reference_and_empty_series_contract():
    assert BacktestMetricsCalculator.calculate_drawdown_series([950.0, 1000.0])[0] == [0.0, 0.0]
    assert BacktestMetricsCalculator.calculate_drawdown_series(
        [950.0, 1000.0], initial_equity=1000.0
    )[0] == [5.0, 0.0]
    assert BacktestMetricsCalculator.calculate_drawdown_series(
        [], initial_equity=1000.0
    ) == ([], 0.0, 0.0, 0)


@pytest.mark.parametrize("initial_equity", [0.0, -1.0, float("nan"), float("inf")])
def test_drawdown_rejects_invalid_initial_equity_even_for_empty_series(initial_equity):
    with pytest.raises(ValueError, match="capital inicial"):
        BacktestMetricsCalculator.calculate_drawdown_series([], initial_equity)


@pytest.mark.parametrize("bad_equity", [float("nan"), float("inf"), -1.0])
def test_drawdown_rejects_invalid_equity_instead_of_masking_it(bad_equity):
    with pytest.raises(ValueError, match="equity"):
        BacktestMetricsCalculator.calculate_drawdown_series(
            [1000.0, bad_equity], initial_equity=1000.0
        )


def test_zero_first_equity_requires_explicit_positive_reference():
    with pytest.raises(ValueError, match="capital inicial"):
        BacktestMetricsCalculator.calculate_drawdown_series([0.0])
    assert BacktestMetricsCalculator.calculate_drawdown_series(
        [0.0], initial_equity=1000.0
    )[0] == [100.0]


def test_metrics_without_trades_still_reports_nonflat_curve_drawdown():
    ts = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
    equity = [950.0, 1100.0, 990.0]
    points = [EquityPoint(time, amount, amount, 0.0) for time, amount in zip(ts, equity)]
    metrics = BacktestMetricsCalculator.calculate_metrics(
        [], points, initial_capital=1000.0
    )
    assert metrics["total_trades"] == 0
    assert metrics["max_drawdown_pct"] == 10.0
    assert metrics["max_drawdown_usd"] == 110.0
    assert metrics["max_drawdown_duration_bars"] == 1
    assert metrics["total_net_pnl"] == 0.0
    assert metrics["sharpe_ratio"] is None


def test_metrics_without_trades_and_constant_equity_has_zero_drawdown():
    ts = pd.date_range("2024-01-01", periods=2, freq="1h", tz="UTC")
    points = [EquityPoint(time, 1000.0, 1000.0, 0.0) for time in ts]
    metrics = BacktestMetricsCalculator.calculate_metrics(
        [], points, initial_capital=1000.0
    )
    assert metrics["max_drawdown_pct"] == 0.0
    assert metrics["max_drawdown_usd"] == 0.0


def test_metrics_breakeven_trades():
    trades = [
        create_sample_trade("t1", 0.0, r_multiple=0.0, mfe_pct=0.5, mae_pct=0.5),
    ]
    metrics = BacktestMetricsCalculator.calculate_metrics(trades, [], initial_capital=10_000.0)
    assert metrics["total_trades"] == 1
    assert metrics["breakeven_trades"] == 1
    assert metrics["winning_trades"] == 0
    assert metrics["losing_trades"] == 0
    assert metrics["profit_factor"] == 0.0
    assert metrics["max_drawdown_pct"] == 0.0


@pytest.mark.parametrize(
    ("interval", "periods", "frequency"),
    [
        ("1m", 525600, "1min"), ("5m", 105120, "5min"),
        ("15m", 35040, "15min"), ("1h", 8760, "1h"),
        ("4h", 2190, "4h"), ("1d", 365, "1D"),
    ],
)
def test_sharpe_annualization_uses_verified_frequency_factor(interval, periods, frequency):
    assert CRYPTO_24_7_PERIODS[interval] == periods
    values = [1000.0, 1005.0, 995.0, 1010.0, 1000.0]
    timestamps = pd.date_range("2024-01-01", periods=len(values), freq=frequency, tz="UTC")
    curve = [EquityPoint(ts, equity, equity, 0.0) for ts, equity in zip(timestamps, values)]
    metrics = BacktestMetricsCalculator.calculate_metrics(
        [create_sample_trade("one", 0.0)], curve, initial_capital=1000.0,
        periods_per_year=periods, expected_interval=pd.Timedelta(frequency),
    )
    returns = pd.Series(values).pct_change().dropna()
    expected = round(float(returns.mean() / returns.std(ddof=1) * math.sqrt(periods)), 2)
    assert metrics["sharpe_ratio"] == expected
    assert metrics["sharpe_unavailable_reason"] is None


def test_sharpe_annualization_factors_differ_by_timeframe():
    assert CRYPTO_24_7_PERIODS["15m"] == 4 * CRYPTO_24_7_PERIODS["1h"]
    assert CRYPTO_24_7_PERIODS["4h"] == 6 * CRYPTO_24_7_PERIODS["1d"]


@pytest.mark.parametrize("times", [
    ["2024-01-01 00:00", "2024-01-01 01:00", "2024-01-01 01:00", "2024-01-01 03:00"],
    ["2024-01-01 00:00", "2024-01-01 01:00", "2024-01-01 03:00", "2024-01-01 04:00"],
    ["2024-01-01 00:00", "2024-01-01 02:00", "2024-01-01 01:00", "2024-01-01 03:00"],
])
def test_sharpe_rejects_duplicate_missing_or_unordered_timestamps(times):
    values = [1000.0, 1010.0, 990.0, 1005.0]
    curve = [EquityPoint(pd.Timestamp(ts, tz="UTC"), value, value, 0.0)
             for ts, value in zip(times, values)]
    metrics = BacktestMetricsCalculator.calculate_metrics(
        [create_sample_trade("one", 0.0)], curve, initial_capital=1000.0,
        periods_per_year=8760, expected_interval=pd.Timedelta(hours=1),
    )
    assert metrics["sharpe_ratio"] is None
    assert "Timestamps" in metrics["sharpe_unavailable_reason"]


def test_sharpe_unknown_short_zero_variance_and_zero_equity_are_na():
    trade = create_sample_trade("one", 0.0)
    times = pd.date_range("2024-01-01", periods=5, freq="1h", tz="UTC")
    variable = [EquityPoint(ts, v, v, 0.0) for ts, v in zip(times, [1000, 1010, 990, 1010, 1000])]
    assert BacktestMetricsCalculator.calculate_metrics([trade], variable, 1000)["sharpe_ratio"] is None
    short = BacktestMetricsCalculator.calculate_metrics(
        [trade], variable[:3], 1000, 8760, pd.Timedelta(hours=1)
    )
    assert short["sharpe_ratio"] is None
    assert "tres rendimientos" in short["sharpe_unavailable_reason"]
    flat = [EquityPoint(ts, 1000, 1000, 0.0) for ts in times]
    assert BacktestMetricsCalculator.calculate_metrics(
        [trade], flat, 1000, 8760, pd.Timedelta(hours=1)
    )["sharpe_ratio"] is None
    zero = variable.copy()
    zero[2] = EquityPoint(times[2], 0.0, 0.0, 100.0)
    assert BacktestMetricsCalculator.calculate_metrics(
        [trade], zero, 1000, 8760, pd.Timedelta(hours=1)
    )["sharpe_ratio"] is None
