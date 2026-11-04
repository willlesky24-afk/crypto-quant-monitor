from __future__ import annotations

import math
from dataclasses import replace

import pandas as pd
import pytest

from src.backtest_metrics import CRYPTO_24_7_PERIODS, BacktestMetricsCalculator
from src.backtest_models import EXCURSION_POLICY_VERSION, EquityPoint, TradeResult


def test_exact_excursion_aggregates_are_independent_and_never_use_proxies():
    base = make_verified_spot_trade("a", 40.0, 38.0, 40.0)
    mfe_only = replace(
        base, trade_id="mfe", mfe_pct=999.0, mae_pct=999.0,
        excursion_policy_version=EXCURSION_POLICY_VERSION,
        mfe_observability="EXACT_OHLC", mfe_exact_pct=2.0,
        mae_observability="BOUNDED_OHLC", mae_lower_bound_pct=0.0,
        mae_upper_bound_pct=3.0,
    )
    mae_only = replace(
        base, trade_id="mae", excursion_policy_version=EXCURSION_POLICY_VERSION,
        mfe_observability="BOUNDED_OHLC", mfe_lower_bound_pct=0.0,
        mfe_upper_bound_pct=4.0, mae_observability="EXACT_OHLC", mae_exact_pct=1.0,
    )
    both = replace(
        base, trade_id="both", excursion_policy_version=EXCURSION_POLICY_VERSION,
        mfe_observability="EXACT_OHLC", mfe_exact_pct=4.0,
        mae_observability="EXACT_OHLC", mae_exact_pct=2.0,
    )
    metrics = BacktestMetricsCalculator.calculate_metrics(
        [mfe_only, mae_only, both, base], [], 10_000.0
    )
    assert metrics["mfe_coverage_status"] == metrics["mae_coverage_status"] == "PARTIAL"
    assert metrics["mfe_exact_trades"] == metrics["mae_exact_trades"] == 2
    assert metrics["mfe_exact_denominator"] == metrics["mae_exact_denominator"] == 2
    assert metrics["mfe_total_trades"] == metrics["mae_total_trades"] == 4
    assert metrics["mfe_exact_avg_pct"] == pytest.approx(3.0)
    assert metrics["mae_exact_avg_pct"] == pytest.approx(1.5)
    assert metrics["avg_mfe_pct"] != metrics["mfe_exact_avg_pct"]


def test_exact_excursion_coverage_complete_none_and_no_trades():
    base = make_verified_spot_trade("a", 40.0, 38.0, 40.0)
    both = replace(
        base, excursion_policy_version=EXCURSION_POLICY_VERSION,
        mfe_observability="EXACT_OHLC", mfe_exact_pct=0.0,
        mae_observability="EXACT_OHLC", mae_exact_pct=1.0,
    )
    complete = BacktestMetricsCalculator.calculate_metrics([both], [], 10_000.0)
    none = BacktestMetricsCalculator.calculate_metrics([base], [], 10_000.0)
    empty = BacktestMetricsCalculator.calculate_metrics([], [], 10_000.0)
    assert complete["mfe_coverage_status"] == complete["mae_coverage_status"] == "COMPLETE"
    assert complete["mfe_exact_avg_pct"] == 0.0  # A measured zero is not missing.
    assert none["mfe_coverage_status"] == none["mae_coverage_status"] == "NONE"
    assert none["mfe_exact_avg_pct"] is None and none["mae_exact_avg_pct"] is None
    assert empty["mfe_coverage_status"] == empty["mae_coverage_status"] == "NO_TRADES"
    assert empty["mfe_exact_avg_pct"] is None and empty["mae_exact_avg_pct"] is None


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


def make_verified_spot_trade(
    trade_id: str, gross_pnl: float, net_pnl: float, risk: float,
    *, final_stop: float | None = None,
) -> TradeResult:
    """Coherent SPOT LONG 1x fixture; price and cash fields reconcile."""
    entry, units = 100.0, 10.0
    stop = entry - risk / units
    exit_price = entry + gross_pnl / units
    total_fees = gross_pnl - net_pnl
    assert total_fees >= 0
    fee_entry = total_fees / 2
    fee_exit = total_fees - fee_entry
    ts = pd.Timestamp("2024-01-01", tz="UTC")
    return TradeResult(
        trade_id=trade_id, symbol="BTCUSDT", timeframe="1h", direction="LONG",
        signal_timestamp=ts, entry_timestamp=ts + pd.Timedelta(hours=1),
        exit_timestamp=ts + pd.Timedelta(hours=2),
        entry_price=entry, exit_price=exit_price, size_units=units,
        notional_entry=units * entry + fee_entry,
        notional_exit=units * exit_price,
        gross_pnl=gross_pnl, fee_entry=fee_entry, fee_exit=fee_exit,
        net_pnl=net_pnl, net_return_pct=net_pnl / (units * entry + fee_entry) * 100,
        r_multiple=gross_pnl / risk, net_r_multiple=net_pnl / risk,
        bars_held=1, exit_reason="TIME_HORIZON", mfe_pct=0.0, mae_pct=0.0,
        is_win=net_pnl > 0, side="LONG", tp_price=entry + 20.0,
        sl_price=final_stop if final_stop is not None else stop,
        initial_stop_price=stop, initial_risk_per_unit=risk / units,
        initial_risk_amount=risk,
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


def test_verified_gross_and_net_expectancy_use_same_three_trades_without_sign_reclassification():
    trades = [
        make_verified_spot_trade("A", 200.0, 190.0, 100.0),
        make_verified_spot_trade("B", 20.0, -10.0, 50.0),
        make_verified_spot_trade("C", -100.0, -110.0, 200.0),
    ]
    result = BacktestMetricsCalculator.calculate_metrics(trades, [], initial_capital=1000.0)
    assert result["gross_expectancy_r"] == pytest.approx((2.0 + 0.4 - 0.5) / 3)
    assert result["net_expectancy_r"] == pytest.approx((1.9 - 0.2 - 0.55) / 3)
    assert result["expectancy_r"] == 0.37  # Frozen legacy hybrid calculation.
    assert result["r_verified_trades"] == 3
    assert result["r_excluded_trades"] == 0
    assert result["r_coverage_status"] == "COMPLETE"
    assert result["r_unavailable_reason"] is None


def test_verified_r_preserves_real_zero_and_counts_fee_only_loss():
    zero_gross = make_verified_spot_trade("flat-gross", 0.0, -10.0, 100.0)
    zero_net = make_verified_spot_trade("flat-net", 10.0, 0.0, 100.0)
    gross_only = BacktestMetricsCalculator.calculate_metrics([zero_gross], [], 1000.0)
    net_only = BacktestMetricsCalculator.calculate_metrics([zero_net], [], 1000.0)
    assert gross_only["gross_expectancy_r"] == 0.0
    assert gross_only["net_expectancy_r"] == pytest.approx(-0.1)
    assert gross_only["expectancy_r"] == 0.0  # Legacy formula hides fee-only loss.
    assert net_only["gross_expectancy_r"] == pytest.approx(0.1)
    assert net_only["net_expectancy_r"] == 0.0
    assert gross_only["r_coverage_status"] == net_only["r_coverage_status"] == "COMPLETE"


def test_verified_r_uses_immutable_stop_after_trailing_and_signal_specific_risk():
    trailing = make_verified_spot_trade("trailing", 40.0, 38.0, 40.0, final_stop=100.0)
    assert trailing.initial_stop_price == 96.0
    assert trailing.sl_price == 100.0
    result = BacktestMetricsCalculator.calculate_metrics([trailing], [], 1000.0)
    assert result["gross_expectancy_r"] == pytest.approx(1.0)
    assert result["net_expectancy_r"] == pytest.approx(0.95)
    assert result["r_coverage_status"] == "COMPLETE"


def test_verified_r_coverage_distinguishes_no_trades_legacy_and_partial():
    valid = make_verified_spot_trade("valid", 40.0, 38.0, 40.0)
    legacy = replace(valid, trade_id="legacy", initial_stop_price=None,
                     initial_risk_per_unit=None, initial_risk_amount=None,
                     net_r_multiple=None)
    empty = BacktestMetricsCalculator.calculate_metrics([], [], 1000.0)
    none = BacktestMetricsCalculator.calculate_metrics([legacy], [], 1000.0)
    partial = BacktestMetricsCalculator.calculate_metrics([valid, legacy], [], 1000.0)
    assert empty["gross_expectancy_r"] is empty["net_expectancy_r"] is None
    assert empty["r_coverage_status"] == "NO_TRADES"
    assert empty["r_verified_trades"] == empty["r_excluded_trades"] == 0
    assert empty["expectancy_r"] == 0.0
    assert none["gross_expectancy_r"] is none["net_expectancy_r"] is None
    assert none["r_coverage_status"] == "NONE_VERIFIED"
    assert none["r_verified_trades"] == 0 and none["r_excluded_trades"] == 1
    assert partial["gross_expectancy_r"] == pytest.approx(1.0)
    assert partial["net_expectancy_r"] == pytest.approx(0.95)
    assert partial["r_verified_trades"] == partial["r_excluded_trades"] == 1
    assert partial["r_coverage_status"] == "PARTIAL"
    assert "subconjunto" in partial["r_unavailable_reason"]
    assert partial["expectancy_r"] == 1.0  # Existing legacy value is preserved.


@pytest.mark.parametrize(
    ("changes",), [
        ({"initial_stop_price": None},),
        ({"initial_risk_amount": None},),
        ({"net_r_multiple": None},),
        ({"initial_risk_amount": 0.0},),
        ({"initial_risk_amount": -1.0},),
        ({"initial_risk_amount": math.nan},),
        ({"initial_risk_amount": math.inf},),
        ({"entry_price": math.nan},),
        ({"size_units": 0.0},),
        ({"size_units": math.inf},),
        ({"initial_stop_price": 100.0},),
        ({"initial_stop_price": 101.0},),
        ({"initial_risk_amount": 41.0},),
        ({"initial_risk_per_unit": 5.0},),
        ({"gross_pnl": math.inf},),
        ({"net_pnl": math.nan},),
        ({"r_multiple": 2.0},),
        ({"net_r_multiple": 2.0},),
        ({"gross_pnl": 41.0},),
        ({"net_pnl": 39.0},),
        ({"direction": "SHORT"},),
        ({"side": "SHORT"},),
        ({"funding_fees": 1.0},),
    ],
)
def test_unverifiable_trade_is_excluded_without_removing_record(changes):
    trade = replace(make_verified_spot_trade("base", 40.0, 38.0, 40.0), **changes)
    result = BacktestMetricsCalculator.calculate_metrics([trade], [], 1000.0)
    assert result["total_trades"] == 1
    assert result["r_verified_trades"] == 0
    assert result["r_excluded_trades"] == 1
    assert result["gross_expectancy_r"] is result["net_expectancy_r"] is None
    assert result["r_coverage_status"] == "NONE_VERIFIED"
