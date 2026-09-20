from __future__ import annotations

import math

import pandas as pd
import pytest

from src.backtest_metrics import BacktestMetricsCalculator
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

    metrics = BacktestMetricsCalculator.calculate_metrics(trades, eq, initial_capital=10_000.0)

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
