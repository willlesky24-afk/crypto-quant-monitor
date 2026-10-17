from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pandas as pd
import pytest

from src.backtest_models import (
    BacktestConfig,
    BacktestReport,
    BacktestValidationError,
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


def test_backtest_validation_error_is_specific_value_error():
    assert issubclass(BacktestValidationError, ValueError)


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
    assert d["initial_stop_price"] is None  # Legacy records remain unknown.
    assert d["initial_risk_amount"] is None
    assert d["net_r_multiple"] is None

    with pytest.raises(FrozenInstanceError):
        trade.net_pnl = 300.0


def test_trade_result_serializes_effective_risk_without_reinterpreting_final_stop():
    ts = pd.to_datetime("2024-01-01", utc=True)
    trade = TradeResult(
        trade_id="tr-risk", symbol="BTCUSDT", timeframe="1h", direction="LONG",
        signal_timestamp=ts, entry_timestamp=ts, exit_timestamp=ts,
        entry_price=100.0, exit_price=104.0, size_units=9.99,
        notional_entry=1000.0, notional_exit=1038.96,
        gross_pnl=39.96, fee_entry=1.0, fee_exit=1.03896,
        net_pnl=37.92104, net_return_pct=3.792104,
        r_multiple=2.0, net_r_multiple=37.92104 / 19.98,
        bars_held=2, exit_reason=TradeExitReason.TAKE_PROFIT.value,
        mfe_pct=4.0, mae_pct=0.0, is_win=True,
        sl_price=100.0, initial_stop_price=98.0,
        initial_risk_per_unit=2.0, initial_risk_amount=19.98,
    )
    data = trade.to_dict()
    assert data["sl_price"] == 100.0
    assert data["initial_stop_price"] == 98.0
    assert data["initial_risk_per_unit"] == 2.0
    assert data["initial_risk_amount"] == 19.98
    assert data["net_r_multiple"] == pytest.approx(37.92104 / 19.98)


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

    # Test report.metrics property
    metrics = report.metrics
    assert isinstance(metrics, dict)
    assert metrics["total_trades"] == 10
    assert metrics["win_rate"] == 0.60
    assert metrics["profit_factor"] == 1.85
    assert metrics["max_drawdown_pct"] == 4.2
    assert metrics["net_pnl"] == 1200.0
    assert metrics["sharpe_ratio"] == 1.95
    assert metrics["gross_expectancy_r"] is None
    assert metrics["net_expectancy_r"] is None
    assert metrics["r_coverage_status"] == "UNKNOWN"

    verified = replace(
        report, gross_expectancy_r=2 / 3, net_expectancy_r=1 / 3,
        r_verified_trades=8, r_excluded_trades=2, r_coverage_status="PARTIAL",
        r_unavailable_reason="Promedio solo del subconjunto verificable (8 de 10 operaciones).",
    )
    assert verified.metrics["expectancy_r"] == report.expectancy_r == 0.65
    assert verified.metrics["gross_expectancy_r"] == 2 / 3
    assert verified.metrics["net_expectancy_r"] == 1 / 3
    assert verified.metrics["r_verified_trades"] == 8
    assert verified.metrics["r_excluded_trades"] == 2
    assert verified.to_dict()["r_coverage_status"] == "PARTIAL"
    assert verified.to_dict()["gross_expectancy_r"] == 2 / 3
    assert list(BacktestReport.__dataclass_fields__).index("gross_expectancy_r") > (
        list(BacktestReport.__dataclass_fields__).index("equity_curve")
    )


def test_report_preserves_unavailable_sharpe_as_none():
    ts = pd.Timestamp("2024-01-01", tz="UTC")
    report = BacktestReport(
        config=BacktestConfig(), symbol="BTCUSDT", timeframe="1h",
        start_time=str(ts), end_time=str(ts), total_candles=0,
        total_trades=0, winning_trades=0, losing_trades=0,
        win_rate_pct=0.0, profit_factor=0.0, expectancy=0.0, expectancy_r=0.0,
        max_drawdown_pct=0.0, max_drawdown_usd=0.0, max_drawdown_duration_bars=0,
        avg_mfe_pct=0.0, avg_mae_pct=0.0, avg_bars_held=0.0,
        total_gross_pnl=0.0, total_fees_paid=0.0, total_net_pnl=0.0,
        return_on_capital_pct=0.0, sharpe_unavailable_reason="Calendario desconocido.",
    )
    assert report.metrics["sharpe_ratio"] is None
    assert report.metrics["sharpe_unavailable_reason"] == "Calendario desconocido."
    assert report.to_dict()["sharpe_ratio"] is None
    assert report.to_dict()["data_provenance"]["status"] == "UNKNOWN"


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

