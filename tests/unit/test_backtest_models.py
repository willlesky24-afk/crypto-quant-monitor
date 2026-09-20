from __future__ import annotations

from dataclasses import FrozenInstanceError

import pandas as pd
import pytest

from src.backtest_models import (
    BacktestConfig,
    BacktestReport,
    EquityPoint,
    Position,
    SignalEvent,
    TradeDirection,
    TradeExitReason,
    TradeResult,
)


def test_signal_event_creation_and_immutability():
    ts = pd.to_datetime("2024-01-01 12:00:00", utc=True)
    signal = SignalEvent(
        signal_id="sig-1",
        symbol="BTCUSDT",
        timeframe="1h",
        candle_timestamp=ts,
        price_at_signal=42000.0,
        signal_state="BULLISH",
        confidence=85.0,
        decision="FAVORABLE",
        quant_score=80.0,
        risk_level="BAJO",
        atr=500.0,
        poc=41800.0,
        vah=42200.0,
        val=41500.0,
    )

    assert signal.signal_id == "sig-1"
    assert signal.direction == TradeDirection.LONG.value
    assert signal.atr == 500.0

    d = signal.to_dict()
    assert d["symbol"] == "BTCUSDT"
    assert d["candle_timestamp"] == "2024-01-01 12:00:00+00:00"

    with pytest.raises(FrozenInstanceError):
        signal.confidence = 90.0


def test_backtest_config_defaults_and_custom():
    default_cfg = BacktestConfig()
    assert default_cfg.initial_capital == 10_000.0
    assert default_cfg.direction == "LONG"
    assert default_cfg.market_type == "SPOT"
    assert default_cfg.funding_rate_8h == 0.0001
    assert default_cfg.leverage == 1.0
    assert default_cfg.tp_atr_multiple == 2.0
    assert default_cfg.sl_atr_multiple == 1.0
    assert default_cfg.taker_fee_pct == 0.0005
    assert default_cfg.slippage_pct == 0.0005

    custom_cfg = BacktestConfig(
        initial_capital=50_000.0,
        direction="SHORT",
        market_type="PERP",
        funding_rate_8h=0.0002,
        leverage=2.0,
        tp_atr_multiple=3.0,
        sl_atr_multiple=1.5,
        max_holding_bars=48,
    )
    assert custom_cfg.initial_capital == 50_000.0
    assert custom_cfg.direction == "SHORT"
    assert custom_cfg.market_type == "PERP"
    assert custom_cfg.funding_rate_8h == 0.0002
    assert custom_cfg.leverage == 2.0
    assert custom_cfg.tp_atr_multiple == 3.0
    assert custom_cfg.sl_atr_multiple == 1.5
    assert custom_cfg.max_holding_bars == 48
    assert "initial_capital" in custom_cfg.to_dict()
    assert custom_cfg.to_dict()["market_type"] == "PERP"


def test_position_tracking_and_excursions():
    ts = pd.to_datetime("2024-01-01 12:00:00", utc=True)
    signal = SignalEvent(
        signal_id="sig-1",
        symbol="BTCUSDT",
        timeframe="1h",
        candle_timestamp=ts,
        price_at_signal=42000.0,
        signal_state="BULLISH",
        confidence=85.0,
        decision="FAVORABLE",
        quant_score=80.0,
        risk_level="BAJO",
        atr=500.0,
        poc=41800.0,
        vah=42200.0,
        val=41500.0,
    )

    entry_ts = pd.to_datetime("2024-01-01 13:00:00", utc=True)
    pos = Position(
        position_id="pos-1",
        signal=signal,
        entry_timestamp=entry_ts,
        entry_price=42021.0,
        size_units=0.2379,
        notional_entry=10000.0,
        tp_price=43021.0,
        sl_price=41521.0,
        fee_entry=5.0,
    )

    assert pos.highest_price == 42021.0
    assert pos.lowest_price == 42021.0
    assert pos.bars_held == 0
    assert pos.is_active is True

    # Update excursions on new bar
    pos.update_excursions(high=42500.0, low=41900.0)
    assert pos.highest_price == 42500.0
    assert pos.lowest_price == 41900.0

    # Next bar higher high
    pos.update_excursions(high=42800.0, low=42100.0)
    assert pos.highest_price == 42800.0
    assert pos.lowest_price == 41900.0


def test_trade_result_immutability_and_serialization():
    sig_ts = pd.to_datetime("2024-01-01 12:00:00", utc=True)
    entry_ts = pd.to_datetime("2024-01-01 13:00:00", utc=True)
    exit_ts = pd.to_datetime("2024-01-01 18:00:00", utc=True)

    trade = TradeResult(
        trade_id="tr-1",
        symbol="BTCUSDT",
        timeframe="1h",
        direction="LONG",
        signal_timestamp=sig_ts,
        entry_timestamp=entry_ts,
        exit_timestamp=exit_ts,
        entry_price=42000.0,
        exit_price=43000.0,
        size_units=0.238,
        notional_entry=10000.0,
        notional_exit=10238.0,
        gross_pnl=238.0,
        fee_entry=5.0,
        fee_exit=5.12,
        net_pnl=227.88,
        net_return_pct=2.2788,
        r_multiple=2.0,
        bars_held=5,
        exit_reason=TradeExitReason.TAKE_PROFIT.value,
        mfe_pct=2.5,
        mae_pct=0.3,
        is_win=True,
    )

    assert trade.is_win is True
    assert trade.exit_reason == "TAKE_PROFIT"

    d = trade.to_dict()
    assert d["trade_id"] == "tr-1"
    assert d["exit_reason"] == "TAKE_PROFIT"
    assert "signal_timestamp" in d

    with pytest.raises(FrozenInstanceError):
        trade.net_pnl = 300.0


def test_equity_point_and_backtest_report_serialization():
    ts = pd.to_datetime("2024-01-01 12:00:00", utc=True)
    eq_pt = EquityPoint(
        timestamp=ts,
        equity=10250.0,
        cash=10250.0,
        drawdown_pct=0.0,
    )

    d_eq = eq_pt.to_dict()
    assert d_eq["equity"] == 10250.0
    assert d_eq["drawdown_pct"] == 0.0

    cfg = BacktestConfig()
    report = BacktestReport(
        config=cfg,
        symbol="BTCUSDT",
        timeframe="1h",
        start_time="2024-01-01",
        end_time="2024-01-10",
        total_candles=240,
        total_trades=10,
        winning_trades=6,
        losing_trades=4,
        win_rate_pct=60.0,
        profit_factor=1.85,
        expectancy=120.0,
        expectancy_r=0.65,
        max_drawdown_pct=4.2,
        max_drawdown_usd=420.0,
        max_drawdown_duration_bars=15,
        avg_mfe_pct=3.1,
        avg_mae_pct=1.2,
        avg_bars_held=6.4,
        total_gross_pnl=1400.0,
        total_fees_paid=200.0,
        total_net_pnl=1200.0,
        return_on_capital_pct=12.0,
        sharpe_ratio=1.95,
        calmar_ratio=2.85,
        trades=[],
        equity_curve=[eq_pt],
    )

    d_rep = report.to_dict()
    assert d_rep["win_rate_pct"] == 60.0
    assert d_rep["profit_factor"] == 1.85
    assert len(d_rep["equity_curve"]) == 1
    assert d_rep["config"]["initial_capital"] == 10_000.0


def test_short_trade_result_and_funding_serialization():
    sig_ts = pd.to_datetime("2024-01-01 12:00:00", utc=True)
    entry_ts = pd.to_datetime("2024-01-01 13:00:00", utc=True)
    exit_ts = pd.to_datetime("2024-01-01 21:00:00", utc=True)

    trade = TradeResult(
        trade_id="tr-short-1",
        symbol="BTCUSDT",
        timeframe="1h",
        direction="SHORT",
        signal_timestamp=sig_ts,
        entry_timestamp=entry_ts,
        exit_timestamp=exit_ts,
        entry_price=42000.0,
        exit_price=40000.0,
        size_units=0.238,
        notional_entry=10000.0,
        notional_exit=9520.0,
        gross_pnl=476.0,
        fee_entry=5.0,
        fee_exit=4.76,
        net_pnl=465.24,
        net_return_pct=4.6524,
        r_multiple=2.0,
        bars_held=8,
        exit_reason=TradeExitReason.TAKE_PROFIT.value,
        mfe_pct=4.8,
        mae_pct=0.5,
        is_win=True,
        side="SHORT",
        funding_fees=1.0,
    )

    assert trade.side == "SHORT"
    assert trade.funding_fees == 1.0
    d = trade.to_dict()
    assert d["side"] == "SHORT"
    assert d["funding_fees"] == 1.0
    assert d["direction"] == "SHORT"

