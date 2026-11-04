"""v2.3 D1/D2/D4: MARGIN_1X (forex/metals CFD-style, no leverage) with SHORT.

Every expected value is computed by hand in the comments from the stated
prices; none comes from a previous engine run.
Base case: signal price 100, ATR 2, TP = 2 x ATR, SL = 1 x ATR, capital 10_000.
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

from src.backtest_engine import BacktestEngine
from src.backtest_metrics import BacktestMetricsCalculator
from src.backtest_models import (
    BacktestConfig,
    BacktestValidationError,
    SignalEvent,
)


def _signal(direction="SHORT", ts="2026-11-03 00:00", atr=2.0):
    return SignalEvent(
        signal_id="sig-margin-1",
        symbol="EURUSD=X",
        timeframe="1h",
        candle_timestamp=pd.Timestamp(ts, tz="UTC"),
        price_at_signal=100.0,
        signal_state="BEARISH" if direction == "SHORT" else "BULLISH",
        confidence=85.0,
        decision="FAVORABLE",
        quant_score=80.0,
        risk_level="BAJO",
        atr=atr,
        poc=100.0,
        vah=101.0,
        val=99.0,
        direction=direction,
    )


def _bars(rows, start="2026-11-03 00:00", spread=None):
    """rows: list of (open, high, low, close). Tuesday 2026-11-03, no closure."""
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    df.insert(
        0, "timestamp", pd.date_range(start, periods=len(rows), freq="1h", tz="UTC")
    )
    df["volume"] = 100.0
    if spread is not None:
        df["spread"] = spread
    return df


def _cfg(**kw):
    base = dict(
        market_type="MARGIN_1X",
        direction="BOTH",
        initial_capital=10_000.0,
        taker_fee_pct=0.0,
        slippage_pct=0.0,
        tp_atr_multiple=2.0,
        sl_atr_multiple=1.0,
        max_holding_bars=24,
    )
    base.update(kw)
    return BacktestConfig(**base)


SIGNAL_BAR = (100.0, 100.5, 99.5, 100.0)


# --- Configuration ------------------------------------------------------------


def test_spot_still_rejects_short():
    with pytest.raises(BacktestValidationError, match="SPOT"):
        BacktestEngine(_cfg(market_type="SPOT", direction="SHORT")).run(
            _bars([SIGNAL_BAR]), signals=[]
        )


def test_margin_rejects_leverage():
    with pytest.raises(BacktestValidationError, match="leverage"):
        BacktestEngine(_cfg(leverage=2.0)).run(_bars([SIGNAL_BAR]), signals=[])


def test_perp_still_rejected():
    with pytest.raises(BacktestValidationError, match="PERP"):
        BacktestEngine(_cfg(market_type="PERP")).run(_bars([SIGNAL_BAR]), signals=[])


# --- SHORT exits (entry Open(T+1) = 100, TP 96, SL 102, units 100) -------------


def test_short_take_profit_intrabar_is_limit_fill():
    # low 95 <= 96 -> TP limit at 96; gross = 100 x (100 - 96) = 400; R = 400/200 = 2
    trades, equity = BacktestEngine(_cfg()).run(
        _bars([SIGNAL_BAR, (100.0, 101.0, 95.0, 97.0)]), signals=[_signal()]
    )
    t = trades[0]
    assert (t.side, t.exit_reason) == ("SHORT", "TAKE_PROFIT")
    assert t.entry_price == pytest.approx(100.0)
    assert t.tp_price == pytest.approx(96.0) and t.sl_price == pytest.approx(102.0)
    assert t.exit_price == pytest.approx(96.0)
    assert t.gross_pnl == pytest.approx(400.0)
    assert t.r_multiple == pytest.approx(2.0)
    assert t.initial_risk_amount == pytest.approx(200.0)
    assert equity[-1].cash == pytest.approx(10_400.0)


def test_short_stop_loss_intrabar():
    # high 103 >= 102 -> SL at 102; gross = 100 x (100 - 102) = -200; R = -1
    trades, _ = BacktestEngine(_cfg()).run(
        _bars([SIGNAL_BAR, (100.0, 103.0, 99.0, 101.0)]), signals=[_signal()]
    )
    t = trades[0]
    assert t.exit_reason == "STOP_LOSS"
    assert t.exit_price == pytest.approx(102.0)
    assert t.gross_pnl == pytest.approx(-200.0)
    assert t.r_multiple == pytest.approx(-1.0)


def test_short_conflict_is_stop_first():
    trades, _ = BacktestEngine(_cfg()).run(
        _bars([SIGNAL_BAR, (100.0, 103.0, 95.0, 100.0)]), signals=[_signal()]
    )
    assert trades[0].exit_reason == "STOP_LOSS"
    assert trades[0].exit_price == pytest.approx(102.0)
    assert trades[0].execution_trace_status == "INTRABAR_SL_FIRST"


def test_short_adverse_gap_exits_at_open():
    # bar T1 survives; T2 opens 105 >= SL 102 -> stop-market at Open 105; gross -500
    trades, _ = BacktestEngine(_cfg()).run(
        _bars([SIGNAL_BAR, (100.0, 101.0, 99.0, 100.0), (105.0, 106.0, 104.0, 105.0)]),
        signals=[_signal()],
    )
    t = trades[0]
    assert t.exit_reason == "STOP_LOSS"
    assert t.exit_price == pytest.approx(105.0)
    assert t.gross_pnl == pytest.approx(-500.0)
    assert t.execution_trace_status == "OPENING_LEVEL_REVIEW"


def test_short_favorable_gap_fills_limit_not_open():
    # T2 opens 94 <= TP 96 -> limit fill at 96 (no gap improvement)
    trades, _ = BacktestEngine(_cfg()).run(
        _bars([SIGNAL_BAR, (100.0, 101.0, 99.0, 100.0), (94.0, 95.0, 93.0, 94.0)]),
        signals=[_signal()],
    )
    assert trades[0].exit_reason == "TAKE_PROFIT"
    assert trades[0].exit_price == pytest.approx(96.0)


def test_short_time_horizon_and_exact_excursions():
    # max_holding 2: T1 survives (H 101, L 98); T2 closes at 99 -> horizon exit 99.
    # Observed extrema over both bars: max 101.5, min 98.
    # MFE = (100 - 98)/100 = 2%; MAE = (101.5 - 100)/100 = 1.5%; gross = 100 x 1 = 100
    trades, _ = BacktestEngine(_cfg(max_holding_bars=2)).run(
        _bars([SIGNAL_BAR, (100.0, 101.0, 98.0, 99.5), (99.5, 101.5, 98.5, 99.0)]),
        signals=[_signal()],
    )
    t = trades[0]
    assert t.exit_reason == "TIME_HORIZON"
    assert t.exit_price == pytest.approx(99.0)
    assert t.gross_pnl == pytest.approx(100.0)
    assert t.mfe_observability == "EXACT_OHLC" and t.mae_observability == "EXACT_OHLC"
    assert t.mfe_exact_pct == pytest.approx(2.0)
    assert t.mae_exact_pct == pytest.approx(1.5)
    assert t.mfe_pct == pytest.approx(2.0) and t.mae_pct == pytest.approx(1.5)


def test_short_intrabar_tp_bounds_mfe_and_keeps_mae_exact():
    # T1 survives (H 101, L 99); T2: open 99, H 100, L 95 -> TP intrabar at 96.
    # MFE lower = (100 - min(99, 99))/100 = 1%, upper = (100 - 95)/100 = 5% -> BOUNDED
    # MAE: prior max 101 dominates T2 high 100 -> exact 1%
    trades, _ = BacktestEngine(_cfg()).run(
        _bars([SIGNAL_BAR, (100.0, 101.0, 99.0, 99.0), (99.0, 100.0, 95.0, 96.0)]),
        signals=[_signal()],
    )
    t = trades[0]
    assert t.mfe_observability == "BOUNDED_OHLC"
    assert t.mfe_lower_bound_pct == pytest.approx(1.0)
    assert t.mfe_upper_bound_pct == pytest.approx(5.0)
    assert t.mae_observability == "EXACT_OHLC"
    assert t.mae_exact_pct == pytest.approx(1.0)


def test_short_slippage_moves_entry_down_and_exits_up():
    # slip 1%: entry = 100 x 0.99 = 99; SL = 99 + 2 = 101; exit = 101 x 1.01 = 102.01
    trades, _ = BacktestEngine(_cfg(slippage_pct=0.01)).run(
        _bars([SIGNAL_BAR, (100.0, 103.0, 99.0, 101.0)]), signals=[_signal()]
    )
    t = trades[0]
    assert t.entry_price == pytest.approx(99.0)
    assert t.sl_price == pytest.approx(101.0)
    assert t.exit_price == pytest.approx(102.01)


def test_short_fees_reconcile_cash():
    # fee 0.1%: fee_entry = 10; units = 9990/100 = 99.9; TP 96:
    # gross = 99.9 x 4 = 399.6; fee_exit = 99.9 x 96 x 0.001 = 9.5904
    # net = 399.6 - 10 - 9.5904 = 380.0096 -> cash 10_380.0096
    trades, equity = BacktestEngine(_cfg(taker_fee_pct=0.001)).run(
        _bars([SIGNAL_BAR, (100.0, 101.0, 95.0, 97.0)]), signals=[_signal()]
    )
    t = trades[0]
    assert t.size_units == pytest.approx(99.9)
    assert t.fee_exit == pytest.approx(9.5904)
    assert t.net_pnl == pytest.approx(380.0096)
    assert equity[-1].cash == pytest.approx(10_380.0096)


def test_short_open_position_is_marked_to_market():
    # Survivor bar closes at 97: equity = 10_000 + 100 x (100 - 97) = 10_300
    _, equity = BacktestEngine(_cfg(max_holding_bars=5)).run(
        _bars([SIGNAL_BAR, (100.0, 101.0, 97.5, 97.0), (97.0, 98.0, 96.5, 97.0)]),
        signals=[_signal()],
    )
    assert equity[1].equity == pytest.approx(10_300.0)


def test_short_trailing_moves_stop_to_break_even_from_next_bar():
    # +1R for SHORT = 100 - 2 = 98. T1 low 97.9 -> stop -> 100 effective from T2.
    # T2 high 100.5 >= 100 -> exit at 100, gross 0.
    trades, _ = BacktestEngine(_cfg(enable_trailing_stop=True)).run(
        _bars([SIGNAL_BAR, (100.0, 100.4, 97.9, 98.5), (98.5, 100.5, 98.0, 100.2)]),
        signals=[_signal()],
    )
    assert trades[0].exit_reason == "STOP_LOSS"
    assert trades[0].exit_price == pytest.approx(100.0)
    assert trades[0].gross_pnl == pytest.approx(0.0)


def test_short_r_is_verified_by_metrics():
    trades, equity = BacktestEngine(_cfg()).run(
        _bars([SIGNAL_BAR, (100.0, 101.0, 95.0, 97.0)]), signals=[_signal()]
    )
    m = BacktestMetricsCalculator.calculate_metrics(trades, equity, 10_000.0)
    assert m["r_coverage_status"] == "COMPLETE"
    assert m["r_verified_trades"] == 1


def test_margin_long_matches_spot_long_exactly():
    rows = [SIGNAL_BAR, (100.0, 101.0, 99.0, 100.5), (100.5, 104.5, 100.0, 104.0)]
    kw = dict(taker_fee_pct=0.0005, slippage_pct=0.0005, direction="LONG")
    spot, _ = BacktestEngine(_cfg(market_type="SPOT", **kw)).run(
        _bars(rows), signals=[_signal("LONG")]
    )
    margin, _ = BacktestEngine(_cfg(**kw)).run(_bars(rows), signals=[_signal("LONG")])
    for field in (
        "entry_price",
        "exit_price",
        "size_units",
        "gross_pnl",
        "net_pnl",
        "r_multiple",
        "net_r_multiple",
        "exit_reason",
    ):
        assert getattr(margin[0], field) == getattr(spot[0], field), field


def test_direction_filter_long_only_ignores_short_signal():
    trades, _ = BacktestEngine(_cfg(direction="LONG")).run(
        _bars([SIGNAL_BAR, (100.0, 101.0, 95.0, 97.0)]), signals=[_signal()]
    )
    assert trades == []


def test_short_loss_beyond_margin_is_explicit():
    # Gap to 250 would lose 150 per unit > 100 margin per unit: not modelled.
    with pytest.raises(BacktestValidationError, match="margen"):
        BacktestEngine(_cfg()).run(
            _bars(
                [SIGNAL_BAR, (100.0, 101.0, 99.0, 100.0), (250.0, 251.0, 249.0, 250.0)]
            ),
            signals=[_signal()],
        )


# --- D4: weekly closure ----------------------------------------------------------


def test_margin_rejects_candles_inside_weekly_closure():
    # 2026-10-31 is a Saturday.
    with pytest.raises(BacktestValidationError, match="cierre semanal"):
        BacktestEngine(_cfg()).run(
            _bars([SIGNAL_BAR] * 3, start="2026-10-31 00:00"), signals=[]
        )


# --- D2: per-candle bid/ask spread ------------------------------------------------


def test_spread_short_sells_bid_and_buys_back_ask():
    # spread 0.2: entry SHORT at bid open = 100 - 0.1 = 99.9; TP = 95.9; SL = 101.9.
    # T1 low 95.85: ask low = 95.95 > 95.9 -> no TP. T2 low 95.7: ask low 95.8 -> TP 95.9.
    # gross = 100.1001... units = 10_000 / 99.9; gross = units x (99.9 - 95.9) = units x 4
    trades, _ = BacktestEngine(_cfg()).run(
        _bars(
            [SIGNAL_BAR, (100.0, 100.5, 95.85, 96.5), (96.5, 97.0, 95.7, 96.0)],
            spread=0.2,
        ),
        signals=[_signal()],
    )
    t = trades[0]
    assert t.entry_price == pytest.approx(99.9)
    assert t.exit_reason == "TAKE_PROFIT"
    assert t.exit_price == pytest.approx(95.9)
    assert t.exit_timestamp == pd.Timestamp("2026-11-03 02:00", tz="UTC")
    assert t.gross_pnl == pytest.approx(10_000 / 99.9 * 4.0)


def test_spread_long_buys_ask_and_sells_bid():
    # spread 0.2: entry LONG at ask = 100.1; TP = 104.1. Bid high = 104.15 - 0.1 = 104.05
    # < 104.1 -> no TP; horizon exit (max 1 bar) at bid close = 104.0 - 0.1 = 103.9
    trades, _ = BacktestEngine(_cfg(max_holding_bars=1)).run(
        _bars([SIGNAL_BAR, (100.0, 104.15, 99.9, 104.0)], spread=0.2),
        signals=[_signal("LONG")],
    )
    t = trades[0]
    assert t.entry_price == pytest.approx(100.1)
    assert t.exit_reason == "TIME_HORIZON"
    assert t.exit_price == pytest.approx(103.9)


def test_round_trip_spread_cost_with_flat_prices():
    # Flat mid 100, spread 0.2: buy 100.1, sell 99.9 -> loss = units x 0.2
    trades, _ = BacktestEngine(_cfg(max_holding_bars=1)).run(
        _bars([SIGNAL_BAR, (100.0, 100.0, 100.0, 100.0)], spread=0.2),
        signals=[_signal("LONG")],
    )
    assert trades[0].gross_pnl == pytest.approx(-(10_000 / 100.1) * 0.2)


@pytest.mark.parametrize("bad", [-0.1, float("nan"), float("inf")])
def test_invalid_spread_is_rejected(bad):
    with pytest.raises(BacktestValidationError, match="spread"):
        BacktestEngine(_cfg()).run(_bars([SIGNAL_BAR] * 2, spread=bad), signals=[])


def test_signal_direction_replace_helper_is_frozen_safe():
    s = replace(_signal(), direction="LONG")
    assert s.direction == "LONG"
