from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

from src.backtest_engine import BacktestEngine
from src.backtest_metrics import BacktestMetricsCalculator
from src.backtest_models import (
    EXCURSION_POLICY_VERSION,
    BacktestConfig,
    BacktestValidationError,
    ExecutionTraceStatus,
    Position,
    SignalEvent,
    TradeExitReason,
)


def _observability_run(bars, *, tp=2.0, sl=1.0, holding=5, slippage=0.0):
    """Synthetic OHLC fixtures only; not a claim about real intrabar paths."""
    times = pd.date_range("2024-01-01", periods=len(bars), freq="1h", tz="UTC")
    df = pd.DataFrame(
        [
            {
                "timestamp": time,
                "open": opened,
                "high": high,
                "low": low,
                "close": closed,
                "volume": 1000.0,
            }
            for time, (opened, high, low, closed) in zip(times, bars, strict=True)
        ]
    )
    cfg = BacktestConfig(
        slippage_pct=slippage,
        taker_fee_pct=0.0,
        tp_atr_multiple=tp,
        sl_atr_multiple=sl,
        max_holding_bars=holding,
    )
    signal = make_test_signal(timestamp=str(times[0]), atr=2.0)
    trades, _ = BacktestEngine(cfg).run(df, [signal])
    assert len(trades) == 1
    assert trades[0].excursion_policy_version == EXCURSION_POLICY_VERSION
    return trades[0]


@pytest.mark.parametrize(
    ("last_bar", "reason"),
    [
        ((100.0, 105.0, 99.0, 103.0), "TAKE_PROFIT"),
        ((100.0, 101.0, 97.0, 98.0), "STOP_LOSS"),
        ((100.0, 105.0, 97.0, 99.0), "STOP_LOSS"),
    ],
)
def test_intrabar_excursions_are_bounds_not_fabricated_path(last_bar, reason):
    trade = _observability_run([(100, 101, 99, 100), last_bar])
    assert trade.exit_reason == reason
    assert trade.mfe_observability == "BOUNDED_OHLC"
    assert trade.mae_observability == "BOUNDED_OHLC"
    assert trade.mfe_exact_pct is None and trade.mae_exact_pct is None
    assert trade.mfe_lower_bound_pct == trade.mae_lower_bound_pct == 0.0
    assert trade.mfe_upper_bound_pct >= trade.mfe_lower_bound_pct
    assert trade.mae_upper_bound_pct >= trade.mae_lower_bound_pct


def test_horizon_and_same_bar_exit_use_full_surviving_candle():
    trade = _observability_run(
        [(100, 101, 99, 100), (100, 101, 99, 100)],
        tp=10.0,
        sl=5.0,
        holding=1,
    )
    assert trade.exit_reason == "TIME_HORIZON"
    assert trade.entry_timestamp == trade.exit_timestamp
    assert trade.mfe_observability == trade.mae_observability == "EXACT_OHLC"
    assert trade.mfe_exact_pct == trade.mae_exact_pct == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("exit_bar", "reason", "expected_mfe", "expected_mae"),
    [
        ((112, 120, 111, 115), "TAKE_PROFIT", 12.0, 1.0),
        ((95, 99, 90, 93), "STOP_LOSS", 5.0, 5.0),
    ],
)
def test_open_exit_observes_only_open_and_previous_candles(
    exit_bar, reason, expected_mfe, expected_mae
):
    trade = _observability_run(
        [(100, 101, 99, 100), (100, 105, 99, 103), exit_bar],
        tp=5.0,
        sl=2.0,
    )
    assert trade.exit_reason == reason
    assert trade.mfe_observability == trade.mae_observability == "EXACT_OHLC"
    assert trade.mfe_exact_pct == pytest.approx(expected_mfe)
    assert trade.mae_exact_pct == pytest.approx(expected_mae)


def test_prior_favorable_extreme_can_be_exact_while_adverse_is_bounded():
    trade = _observability_run(
        [(100, 101, 99, 100), (100, 110, 99, 105), (100, 109, 95, 98)],
        tp=10.0,
        sl=2.0,
    )
    assert trade.exit_reason == "STOP_LOSS"
    assert trade.mfe_observability == "EXACT_OHLC"
    assert trade.mfe_exact_pct == pytest.approx(10.0)
    assert trade.mae_observability == "BOUNDED_OHLC"
    assert trade.mae_lower_bound_pct == pytest.approx(1.0)
    assert trade.mae_upper_bound_pct == pytest.approx(5.0)


def test_prior_adverse_extreme_can_be_exact_while_favorable_is_bounded():
    trade = _observability_run(
        [(100, 101, 99, 100), (100, 101, 97, 100), (100, 121, 98, 120)],
        tp=10.0,
        sl=2.0,
    )
    assert trade.exit_reason == "TAKE_PROFIT"
    assert trade.mae_observability == "EXACT_OHLC"
    assert trade.mae_exact_pct == pytest.approx(3.0)
    assert trade.mfe_observability == "BOUNDED_OHLC"
    assert trade.mfe_lower_bound_pct == pytest.approx(1.0)
    assert trade.mfe_upper_bound_pct == pytest.approx(21.0)


def test_incoherent_ohlc_is_indeterminate_without_changing_cash_or_exit():
    trade = _observability_run(
        [(100, 101, 99, 100), (100, 99, 98, 100)],
        tp=10.0,
        sl=5.0,
        holding=1,
    )
    assert trade.exit_reason == "TIME_HORIZON"
    assert trade.mfe_observability == trade.mae_observability == "UNDETERMINED"
    assert trade.mfe_exact_pct is None and trade.mae_exact_pct is None
    assert trade.mfe_lower_bound_pct is None and trade.mae_upper_bound_pct is None


def test_slippage_fill_is_not_an_observed_market_extreme():
    trade = _observability_run(
        [(100, 101, 99, 100), (100, 105, 99, 103)],
        slippage=0.001,
    )
    assert trade.entry_price == pytest.approx(100.1)
    assert trade.mfe_observability == "BOUNDED_OHLC"
    assert trade.mfe_lower_bound_pct == 0.0
    assert trade.mae_lower_bound_pct > 0.0  # observed Open is below the slipped fill


def make_test_signal(
    timestamp: str = "2024-01-01 00:00:00",
    price: float = 100.0,
    atr: float = 2.0,
    quant_score: float = 80.0,
    decision: str = "FAVORABLE",
) -> SignalEvent:
    return SignalEvent(
        signal_id="sig-test-1",
        symbol="BTCUSDT",
        timeframe="1h",
        candle_timestamp=pd.to_datetime(timestamp, utc=True),
        price_at_signal=price,
        signal_state="BULLISH",
        confidence=85.0,
        decision=decision,
        quant_score=quant_score,
        risk_level="BAJO",
        atr=atr,
        poc=99.0,
        vah=102.0,
        val=98.0,
        direction="LONG",
    )


def test_backtest_engine_empty_and_missing_columns():
    engine = BacktestEngine()
    trades, eq = engine.run(pd.DataFrame())
    assert trades == []
    assert eq == []

    invalid_df = pd.DataFrame({"timestamp": [1], "close": [100]})
    with pytest.raises(ValueError, match="columnas"):
        engine.run(invalid_df)


def test_backtest_engine_entry_on_next_bar_with_slippage_and_fee(
    make_synthetic_candles,
):
    # 5 bars:
    # bar 0: 100.0 (signal emitted at close)
    # bar 1: open 100.0 -> entry price = 100.0 * 1.001 (0.1% slippage)
    df = make_synthetic_candles(
        start="2024-01-01 00:00:00", periods=10, freq="1h", base_price=100.0
    )

    cfg = BacktestConfig(
        initial_capital=10_000.0,
        slippage_pct=0.001,  # 0.1%
        taker_fee_pct=0.0005,  # 0.05%
        tp_atr_multiple=10.0,  # Far away so it doesn't trigger TP immediately
        sl_atr_multiple=10.0,
        max_holding_bars=3,
    )
    engine = BacktestEngine(config=cfg)

    sig = make_test_signal(
        timestamp="2024-01-01 00:00:00", price=float(df.iloc[0]["close"])
    )
    trades, eq = engine.run(df, signals=[sig])

    assert len(trades) == 1
    trade = trades[0]

    # Signal on bar 0 (00:00:00), Entry on bar 1 (01:00:00)
    assert trade.signal_timestamp == pd.to_datetime("2024-01-01 00:00:00", utc=True)
    assert trade.entry_timestamp == pd.to_datetime("2024-01-01 01:00:00", utc=True)

    expected_entry_price = float(df.iloc[1]["open"]) * 1.001
    assert trade.entry_price == pytest.approx(expected_entry_price)
    assert trade.fee_entry > 0
    assert trade.fee_exit > 0
    assert trade.net_pnl < trade.gross_pnl  # Net PnL accounts for fees


def test_backtest_engine_take_profit_hit():
    # 3 bars:
    # bar 0: Signal at close (P=100, ATR=2). TP = 100 + (2 * 2) = 104. SL = 100 - (1 * 2) = 98.
    # bar 1: Entry at open 100. High reaches 106.0 -> TP hit!
    timestamps = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0, 100.0, 105.0],
            "high": [101.0, 106.0, 107.0],
            "low": [99.0, 99.5, 104.0],
            "close": [100.0, 105.0, 106.0],
            "volume": [1000.0, 1000.0, 1000.0],
        }
    )

    cfg = BacktestConfig(
        slippage_pct=0.0,
        taker_fee_pct=0.0,
        tp_atr_multiple=2.0,
        sl_atr_multiple=1.0,
    )
    engine = BacktestEngine(config=cfg)
    sig = make_test_signal("2024-01-01 00:00:00", price=100.0, atr=2.0)

    trades, eq = engine.run(df, signals=[sig])

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_reason == TradeExitReason.TAKE_PROFIT.value
    assert trade.exit_price == pytest.approx(104.0)
    assert trade.is_win is True
    assert trade.r_multiple == pytest.approx(2.0)
    assert trade.net_r_multiple == pytest.approx(2.0)
    assert trade.initial_stop_price == pytest.approx(98.0)
    assert trade.initial_risk_per_unit == pytest.approx(2.0)
    assert trade.initial_risk_amount == pytest.approx(trade.size_units * 2.0)


def test_backtest_engine_stop_loss_hit():
    # bar 0: Signal at close (P=100, ATR=2). SL = 98.0
    # bar 1: Entry at open 100. Low drops to 97.0 -> SL hit!
    timestamps = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0, 100.0, 97.0],
            "high": [101.0, 100.5, 98.0],
            "low": [99.0, 97.0, 96.0],
            "close": [100.0, 97.5, 96.5],
            "volume": [1000.0, 1000.0, 1000.0],
        }
    )

    cfg = BacktestConfig(
        slippage_pct=0.0,
        taker_fee_pct=0.0,
        tp_atr_multiple=2.0,
        sl_atr_multiple=1.0,
    )
    engine = BacktestEngine(config=cfg)
    sig = make_test_signal("2024-01-01 00:00:00", price=100.0, atr=2.0)

    trades, eq = engine.run(df, signals=[sig])

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_reason == TradeExitReason.STOP_LOSS.value
    assert trade.exit_price == pytest.approx(98.0)
    assert trade.is_win is False
    assert trade.r_multiple == pytest.approx(-1.0)
    assert trade.net_r_multiple == pytest.approx(-1.0)
    assert trade.initial_stop_price == pytest.approx(98.0)


def test_backtest_engine_worst_case_intrabar_conflict():
    # bar 1: Low reaches 95.0 (below SL 98) and High reaches 106.0 (above TP 104)
    # Conservative execution rule: Must trigger STOP_LOSS!
    timestamps = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0, 100.0, 100.0],
            "high": [101.0, 108.0, 102.0],
            "low": [99.0, 95.0, 99.0],
            "close": [100.0, 102.0, 100.0],
            "volume": [1000.0, 1000.0, 1000.0],
        }
    )

    cfg = BacktestConfig(
        slippage_pct=0.0,
        taker_fee_pct=0.0,
        tp_atr_multiple=2.0,
        sl_atr_multiple=1.0,
    )
    engine = BacktestEngine(config=cfg)
    sig = make_test_signal("2024-01-01 00:00:00", price=100.0, atr=2.0)

    trades, eq = engine.run(df, signals=[sig])

    assert len(trades) == 1
    assert trades[0].exit_reason == TradeExitReason.STOP_LOSS.value
    assert trades[0].is_win is False


def test_backtest_engine_trailing_stop_break_even():
    # bar 0: Signal at 100, ATR=2. SL=98, Risk=2. Target for BE is +1R = 102.0
    # bar 1: High reaches 103.0 -> Trailing stop moves SL to 100.0!
    # bar 2: Price drops to 99.0 -> Triggers SL at 100.0 instead of 98.0
    timestamps = pd.date_range("2024-01-01", periods=4, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0, 100.0, 101.0, 99.0],
            "high": [101.0, 103.0, 101.5, 100.0],
            "low": [99.0, 100.0, 99.0, 98.0],
            "close": [100.0, 102.0, 99.5, 98.5],
            "volume": [1000.0, 1000.0, 1000.0, 1000.0],
        }
    )

    cfg = BacktestConfig(
        slippage_pct=0.0,
        taker_fee_pct=0.0,
        enable_trailing_stop=True,
        trailing_stop_activation_r=1.0,
        tp_atr_multiple=5.0,  # Far TP
        sl_atr_multiple=1.0,
    )
    engine = BacktestEngine(config=cfg)
    sig = make_test_signal("2024-01-01 00:00:00", price=100.0, atr=2.0)

    trades, eq = engine.run(df, signals=[sig])

    assert len(trades) == 1
    assert trades[0].exit_price == pytest.approx(100.0)  # Exited at Break-Even!
    assert trades[0].sl_price == pytest.approx(100.0)
    assert trades[0].initial_stop_price == pytest.approx(98.0)
    assert trades[0].initial_risk_per_unit == pytest.approx(2.0)
    assert trades[0].r_multiple == pytest.approx(0.0)


def test_backtest_engine_signal_filtering():
    timestamps = pd.date_range("2024-01-01", periods=5, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0] * 5,
            "high": [101.0] * 5,
            "low": [99.0] * 5,
            "close": [100.0] * 5,
            "volume": [1000.0] * 5,
        }
    )

    # Sig 1: low quant score (< 60)
    sig1 = make_test_signal(
        "2024-01-01 00:00:00", quant_score=45.0, decision="FAVORABLE"
    )
    # Sig 2: unfavorable decision
    sig2 = make_test_signal(
        "2024-01-01 01:00:00", quant_score=80.0, decision="WAIT_CONFIRMATION"
    )
    # Sig 3: wrong direction (SHORT)
    sig3 = SignalEvent(
        signal_id="sig-3",
        symbol="BTCUSDT",
        timeframe="1h",
        candle_timestamp=pd.to_datetime("2024-01-01 02:00:00", utc=True),
        price_at_signal=100.0,
        signal_state="BEARISH",
        confidence=80.0,
        decision="FAVORABLE",
        quant_score=80.0,
        risk_level="BAJO",
        atr=2.0,
        poc=99.0,
        vah=102.0,
        val=98.0,
        direction="SHORT",
    )

    engine = BacktestEngine(
        config=BacktestConfig(
            min_quant_score=60.0, require_favorable_decision=True, direction="LONG"
        )
    )
    trades, eq = engine.run(df, signals=[sig1, sig2, sig3])

    assert len(trades) == 0  # All signals filtered out


def test_backtest_engine_short_take_profit_hit():
    # bar 0: Signal at close (P=100, ATR=2, direction=SHORT). TP = 100 - (2 * 2) = 96.0. SL = 100 + (1 * 2) = 102.0.
    # bar 1: Entry at open 100. Low drops to 95.0 -> TP hit!
    timestamps = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0, 100.0, 95.0],
            "high": [101.0, 100.5, 96.0],
            "low": [99.0, 95.0, 94.0],
            "close": [100.0, 95.5, 95.0],
            "volume": [1000.0, 1000.0, 1000.0],
        }
    )

    cfg = BacktestConfig(
        slippage_pct=0.0,
        taker_fee_pct=0.0,
        direction="SHORT",
        tp_atr_multiple=2.0,
        sl_atr_multiple=1.0,
    )
    engine = BacktestEngine(config=cfg)
    sig = SignalEvent(
        signal_id="sig-short-1",
        symbol="BTCUSDT",
        timeframe="1h",
        candle_timestamp=pd.to_datetime("2024-01-01 00:00:00", utc=True),
        price_at_signal=100.0,
        signal_state="BEARISH",
        confidence=85.0,
        decision="FAVORABLE",
        quant_score=80.0,
        risk_level="BAJO",
        atr=2.0,
        poc=99.0,
        vah=102.0,
        val=98.0,
        direction="SHORT",
    )

    # Former SPOT SHORT execution assertion: now explicitly unsupported.
    with pytest.raises(BacktestValidationError, match="SHORT"):
        engine.run(df, signals=[sig])


def test_backtest_engine_short_stop_loss_hit():
    # bar 0: Signal at close (P=100, ATR=2, direction=SHORT). SL = 100 + (1 * 2) = 102.0.
    # bar 1: Entry at open 100. High rises to 103.0 -> SL hit!
    timestamps = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0, 100.0, 103.0],
            "high": [101.0, 103.5, 104.0],
            "low": [99.0, 99.5, 102.0],
            "close": [100.0, 103.0, 103.5],
            "volume": [1000.0, 1000.0, 1000.0],
        }
    )

    cfg = BacktestConfig(
        slippage_pct=0.0,
        taker_fee_pct=0.0,
        direction="SHORT",
        tp_atr_multiple=2.0,
        sl_atr_multiple=1.0,
    )
    engine = BacktestEngine(config=cfg)
    sig = SignalEvent(
        signal_id="sig-short-2",
        symbol="BTCUSDT",
        timeframe="1h",
        candle_timestamp=pd.to_datetime("2024-01-01 00:00:00", utc=True),
        price_at_signal=100.0,
        signal_state="BEARISH",
        confidence=85.0,
        decision="FAVORABLE",
        quant_score=80.0,
        risk_level="BAJO",
        atr=2.0,
        poc=99.0,
        vah=102.0,
        val=98.0,
        direction="SHORT",
    )

    # Former SPOT SHORT execution assertion: now explicitly unsupported.
    with pytest.raises(BacktestValidationError, match="SHORT"):
        engine.run(df, signals=[sig])


def test_backtest_engine_short_worst_case_intrabar_conflict():
    # bar 1: High reaches 103.0 (above SL 102) and Low reaches 95.0 (below TP 96)
    # Conservative execution rule: Must trigger STOP_LOSS!
    timestamps = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0, 100.0, 100.0],
            "high": [101.0, 104.0, 102.0],
            "low": [99.0, 94.0, 99.0],
            "close": [100.0, 100.0, 100.0],
            "volume": [1000.0, 1000.0, 1000.0],
        }
    )

    cfg = BacktestConfig(
        slippage_pct=0.0,
        taker_fee_pct=0.0,
        direction="SHORT",
        tp_atr_multiple=2.0,
        sl_atr_multiple=1.0,
    )
    engine = BacktestEngine(config=cfg)
    sig = SignalEvent(
        signal_id="sig-short-3",
        symbol="BTCUSDT",
        timeframe="1h",
        candle_timestamp=pd.to_datetime("2024-01-01 00:00:00", utc=True),
        price_at_signal=100.0,
        signal_state="BEARISH",
        confidence=85.0,
        decision="FAVORABLE",
        quant_score=80.0,
        risk_level="BAJO",
        atr=2.0,
        poc=99.0,
        vah=102.0,
        val=98.0,
        direction="SHORT",
    )

    # SHORT intrabar execution is deferred until its instrument ledger is validated.
    with pytest.raises(BacktestValidationError, match="SHORT"):
        engine.run(df, signals=[sig])


def test_backtest_engine_perp_funding_fees_applied_every_8h():
    # 24 hours of 1h candles: from 2024-01-01 00:00 to 2024-01-01 23:00 UTC
    # Signal at 00:00, Entry at 01:00 UTC.
    # Settlement hours reached: 08:00 UTC and 16:00 UTC (2 settlement cycles).
    timestamps = pd.date_range("2024-01-01 00:00:00", periods=24, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0] * 24,
            "high": [101.0] * 24,
            "low": [99.0] * 24,
            "close": [100.0] * 24,
            "volume": [1000.0] * 24,
        }
    )

    cfg_perp = BacktestConfig(
        initial_capital=10_000.0,
        slippage_pct=0.0,
        taker_fee_pct=0.0,
        market_type="PERP",
        funding_rate_8h=0.001,  # 0.1% per 8h cycle
        tp_atr_multiple=10.0,  # Far TP
        sl_atr_multiple=10.0,  # Far SL
        max_holding_bars=24,
    )
    engine = BacktestEngine(config=cfg_perp)
    sig = make_test_signal("2024-01-01 00:00:00", price=100.0, atr=1.0)

    # Former simplified PERP funding assertion: execution is now blocked.
    with pytest.raises(BacktestValidationError, match="PERP"):
        engine.run(df, signals=[sig])


def test_backtest_engine_spot_market_ignores_funding():
    # Same dataset as above, but with market_type="SPOT"
    timestamps = pd.date_range("2024-01-01 00:00:00", periods=24, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0] * 24,
            "high": [101.0] * 24,
            "low": [99.0] * 24,
            "close": [100.0] * 24,
            "volume": [1000.0] * 24,
        }
    )

    cfg_spot = BacktestConfig(
        initial_capital=10_000.0,
        slippage_pct=0.0,
        taker_fee_pct=0.0,
        market_type="SPOT",
        funding_rate_8h=0.001,
        tp_atr_multiple=10.0,
        sl_atr_multiple=10.0,
        max_holding_bars=24,
    )
    engine = BacktestEngine(config=cfg_spot)
    sig = make_test_signal("2024-01-01 00:00:00", price=100.0, atr=1.0)

    trades, eq = engine.run(df, signals=[sig])

    assert len(trades) == 1
    assert trades[0].funding_fees == 0.0
    assert trades[0].net_pnl == 0.0
    assert eq[-1].equity == 10_000.0


def test_backtest_engine_short_trailing_stop():
    # bar 0: Signal at 100, ATR=2. SL=102, Risk=2. Target for BE is -1R = 98.0
    # bar 1: Low reaches 97.0 -> Trailing stop moves SL to 100.0!
    # bar 2: Price rises to 101.0 -> Triggers SL at 100.0 instead of 102.0
    timestamps = pd.date_range("2024-01-01", periods=4, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0, 100.0, 99.0, 101.0],
            "high": [101.0, 100.0, 101.0, 102.0],
            "low": [99.0, 97.0, 98.5, 100.0],
            "close": [100.0, 98.0, 100.5, 101.5],
            "volume": [1000.0, 1000.0, 1000.0, 1000.0],
        }
    )

    cfg = BacktestConfig(
        slippage_pct=0.0,
        taker_fee_pct=0.0,
        direction="SHORT",
        enable_trailing_stop=True,
        trailing_stop_activation_r=1.0,
        tp_atr_multiple=5.0,  # Far TP
        sl_atr_multiple=1.0,
    )
    engine = BacktestEngine(config=cfg)
    sig = SignalEvent(
        signal_id="sig-short-ts",
        symbol="BTCUSDT",
        timeframe="1h",
        candle_timestamp=pd.to_datetime("2024-01-01 00:00:00", utc=True),
        price_at_signal=100.0,
        signal_state="BEARISH",
        confidence=85.0,
        decision="FAVORABLE",
        quant_score=80.0,
        risk_level="BAJO",
        atr=2.0,
        poc=99.0,
        vah=102.0,
        val=98.0,
        direction="SHORT",
    )

    # Former SPOT SHORT trailing assertion: execution is now blocked.
    with pytest.raises(BacktestValidationError, match="SHORT"):
        engine.run(df, signals=[sig])


def test_backtest_engine_short_time_horizon_exit():
    timestamps = pd.date_range("2024-01-01", periods=4, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0, 100.0, 99.0, 98.0],
            "high": [101.0, 100.5, 99.5, 98.5],
            "low": [99.0, 99.0, 98.5, 97.5],
            "close": [100.0, 99.5, 99.0, 98.0],
            "volume": [1000.0] * 4,
        }
    )

    cfg = BacktestConfig(
        slippage_pct=0.0,
        taker_fee_pct=0.0,
        direction="SHORT",
        tp_atr_multiple=10.0,
        sl_atr_multiple=10.0,
        max_holding_bars=2,
    )
    engine = BacktestEngine(config=cfg)
    sig = SignalEvent(
        signal_id="sig-short-th",
        symbol="BTCUSDT",
        timeframe="1h",
        candle_timestamp=pd.to_datetime("2024-01-01 00:00:00", utc=True),
        price_at_signal=100.0,
        signal_state="BEARISH",
        confidence=85.0,
        decision="FAVORABLE",
        quant_score=80.0,
        risk_level="BAJO",
        atr=2.0,
        poc=99.0,
        vah=102.0,
        val=98.0,
        direction="SHORT",
    )

    # Former SPOT SHORT time-horizon assertion: execution is now blocked.
    with pytest.raises(BacktestValidationError, match="SHORT"):
        engine.run(df, signals=[sig])


def test_backtest_engine_short_perp_funding_fee():
    timestamps = pd.date_range("2024-01-01 00:00:00", periods=24, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0] * 24,
            "high": [101.0] * 24,
            "low": [99.0] * 24,
            "close": [100.0] * 24,
            "volume": [1000.0] * 24,
        }
    )

    cfg = BacktestConfig(
        initial_capital=10_000.0,
        slippage_pct=0.0,
        taker_fee_pct=0.0,
        direction="SHORT",
        market_type="PERP",
        funding_rate_8h=0.001,
        tp_atr_multiple=10.0,
        sl_atr_multiple=10.0,
        max_holding_bars=24,
    )
    engine = BacktestEngine(config=cfg)
    sig = SignalEvent(
        signal_id="sig-short-funding",
        symbol="BTCUSDT",
        timeframe="1h",
        candle_timestamp=pd.to_datetime("2024-01-01 00:00:00", utc=True),
        price_at_signal=100.0,
        signal_state="BEARISH",
        confidence=85.0,
        decision="FAVORABLE",
        quant_score=80.0,
        risk_level="BAJO",
        atr=1.0,
        poc=99.0,
        vah=102.0,
        val=98.0,
        direction="SHORT",
    )

    # Former simplified PERP funding assertion: execution is now blocked.
    with pytest.raises(BacktestValidationError, match="PERP"):
        engine.run(df, signals=[sig])


def test_backtest_engine_direction_both():
    timestamps = pd.date_range("2024-01-01", periods=6, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0] * 6,
            "high": [105.0, 105.0, 95.0, 95.0, 100.0, 100.0],
            "low": [95.0, 95.0, 90.0, 90.0, 100.0, 100.0],
            "close": [100.0] * 6,
            "volume": [1000.0] * 6,
        }
    )

    sig_long = make_test_signal("2024-01-01 00:00:00", price=100.0, atr=2.0)
    sig_short = SignalEvent(
        signal_id="sig-short-both",
        symbol="BTCUSDT",
        timeframe="1h",
        candle_timestamp=pd.to_datetime("2024-01-01 02:00:00", utc=True),
        price_at_signal=100.0,
        signal_state="BEARISH",
        confidence=85.0,
        decision="FAVORABLE",
        quant_score=80.0,
        risk_level="BAJO",
        atr=2.0,
        poc=99.0,
        vah=102.0,
        val=98.0,
        direction="SHORT",
    )

    cfg = BacktestConfig(direction="BOTH", tp_atr_multiple=2.0, sl_atr_multiple=1.0)
    engine = BacktestEngine(config=cfg)
    # BOTH can create unsupported SHORT fills on SPOT.
    with pytest.raises(BacktestValidationError, match="BOTH"):
        engine.run(df, signals=[sig_long, sig_short])


def test_backtest_engine_zero_initial_risk_rejected():
    timestamps = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0] * 3,
            "high": [101.0] * 3,
            "low": [99.0] * 3,
            "close": [100.0] * 3,
            "volume": [1000.0] * 3,
        }
    )

    sig = make_test_signal("2024-01-01 00:00:00", price=100.0, atr=0.0)
    cfg = BacktestConfig(sl_atr_multiple=0.0, max_holding_bars=1)
    engine = BacktestEngine(config=cfg)
    with pytest.raises(BacktestValidationError, match="Stop inicial"):
        engine.run(df, signals=[sig])


def _flat_spot_bars(exit_price: float = 100.0, count: int = 3) -> pd.DataFrame:
    prices = [100.0] * (count - 1) + [exit_price]
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(
                "2024-01-01", periods=count, freq="1h", tz="UTC"
            ),
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": [1000.0] * count,
        }
    )


def test_effective_r_reconciles_gross_net_and_fees_at_take_profit():
    cfg = BacktestConfig(
        initial_capital=1000.0,
        taker_fee_pct=0.001,
        slippage_pct=0.0,
        tp_atr_multiple=2.0,
        sl_atr_multiple=1.0,
    )
    trades, equity = BacktestEngine(cfg).run(
        _flat_spot_bars(104.0), signals=[make_test_signal(atr=2.0)]
    )
    trade = trades[0]
    assert trade.entry_price == pytest.approx(100.0)
    assert trade.initial_stop_price == pytest.approx(98.0)
    assert trade.size_units == pytest.approx(9.99)
    assert trade.initial_risk_amount == pytest.approx(19.98)
    assert trade.gross_pnl == pytest.approx(39.96)
    assert trade.fee_entry == pytest.approx(1.0)
    assert trade.fee_exit == pytest.approx(1.03896)
    assert trade.net_pnl == pytest.approx(37.92104)
    assert trade.r_multiple == pytest.approx(2.0)
    assert trade.net_r_multiple == pytest.approx(37.92104 / 19.98)
    assert equity[-1].equity - cfg.initial_capital == pytest.approx(trade.net_pnl)


def test_signal_specific_stop_sets_effective_r_not_generic_config():
    cfg = BacktestConfig(
        initial_capital=1000.0,
        taker_fee_pct=0.001,
        slippage_pct=0.0,
        tp_atr_multiple=2.0,
        sl_atr_multiple=1.0,
    )
    signal = replace(make_test_signal(atr=2.0), sl_atr_multiple=2.0)
    trades, _ = BacktestEngine(cfg).run(_flat_spot_bars(104.0), signals=[signal])
    trade = trades[0]
    assert trade.initial_stop_price == pytest.approx(96.0)
    assert trade.initial_risk_per_unit == pytest.approx(4.0)
    assert trade.initial_risk_amount == pytest.approx(39.96)
    assert trade.r_multiple == pytest.approx(1.0)
    assert trade.net_r_multiple == pytest.approx(trade.net_pnl / 39.96)


def test_trailing_stop_does_not_rewrite_initial_risk_denominator():
    cfg = BacktestConfig(
        initial_capital=1000.0,
        taker_fee_pct=0.0,
        slippage_pct=0.0,
        tp_atr_multiple=2.0,
        sl_atr_multiple=1.0,
        enable_trailing_stop=True,
    )
    signal = replace(make_test_signal(atr=2.0), sl_atr_multiple=2.0)
    trades, _ = BacktestEngine(cfg).run(_flat_spot_bars(104.0), signals=[signal])
    trade = trades[0]
    assert trade.exit_reason == TradeExitReason.TAKE_PROFIT.value
    # TP closed the trade on its activation candle; no later stop update occurs.
    assert trade.sl_price == pytest.approx(96.0)
    assert trade.initial_stop_price == pytest.approx(96.0)
    assert trade.initial_risk_amount == pytest.approx(40.0)
    assert trade.r_multiple == pytest.approx(1.0)
    assert trade.net_r_multiple == pytest.approx(1.0)


def _trailing_spot_bars(
    *subsequent_bars: tuple[float, float, float, float],
) -> pd.DataFrame:
    candles = [(100.0, 101.0, 99.0, 100.0), (100.0, 101.0, 99.0, 100.0)]
    candles.extend(subsequent_bars)
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(
                "2024-01-01", periods=len(candles), freq="1h", tz="UTC"
            ),
            "open": [bar[0] for bar in candles],
            "high": [bar[1] for bar in candles],
            "low": [bar[2] for bar in candles],
            "close": [bar[3] for bar in candles],
        }
    )


def _trailing_spot_config(**changes) -> BacktestConfig:
    params = dict(
        initial_capital=1000.0,
        taker_fee_pct=0.0,
        slippage_pct=0.0,
        sl_atr_multiple=1.0,
        tp_atr_multiple=5.0,
        enable_trailing_stop=True,
        trailing_stop_activation_r=1.0,
    )
    params.update(changes)
    return BacktestConfig(**params)


def test_trailing_high_cannot_retroactively_replace_stop_touched_same_bar():
    # T opens above the old stop (98), reaches activation (103), but also touches 97.
    bars = _trailing_spot_bars((99.0, 103.0, 97.0, 101.0))
    trades, equity = BacktestEngine(_trailing_spot_config()).run(
        bars, [make_test_signal(atr=2.0)]
    )
    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_reason == TradeExitReason.STOP_LOSS.value
    assert trade.exit_timestamp == bars.iloc[2]["timestamp"]
    assert trade.exit_price == pytest.approx(98.0)
    assert trade.sl_price == trade.initial_stop_price == pytest.approx(98.0)
    assert trade.r_multiple == trade.net_r_multiple == pytest.approx(-1.0)
    assert equity[-1].cash == equity[-1].equity == pytest.approx(980.0)


def test_surviving_trailing_activates_after_t_and_executes_from_t_plus_one(monkeypatch):
    bars = _trailing_spot_bars(
        (100.0, 103.0, 99.0, 101.0),
        (101.0, 101.5, 99.0, 100.0),
    )
    stops_at_bar_start = []
    original_update = Position.update_excursions

    def record_stop_before_exit(self, high, low):
        stops_at_bar_start.append(self.sl_price)
        return original_update(self, high, low)

    monkeypatch.setattr(Position, "update_excursions", record_stop_before_exit)
    cfg = _trailing_spot_config(taker_fee_pct=0.001)
    trades, equity = BacktestEngine(cfg).run(bars, [make_test_signal(atr=2.0)])

    assert stops_at_bar_start == pytest.approx([98.0, 98.0, 100.0])
    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_timestamp == bars.iloc[3]["timestamp"]
    assert trade.exit_reason == TradeExitReason.STOP_LOSS.value
    assert trade.exit_price == trade.sl_price == pytest.approx(100.0)
    assert trade.initial_stop_price == pytest.approx(98.0)
    assert trade.initial_risk_amount == pytest.approx(19.98)
    assert trade.fee_entry == pytest.approx(1.0)
    assert trade.fee_exit == pytest.approx(0.999)
    assert trade.r_multiple == pytest.approx(0.0)
    assert trade.net_r_multiple == pytest.approx(-1.999 / 19.98)
    assert equity[-1].cash == equity[-1].equity == pytest.approx(998.001)
    assert equity[-1].equity - cfg.initial_capital == pytest.approx(trade.net_pnl)


@pytest.mark.parametrize(
    ("bar", "reason", "exit_price"),
    [
        ((100.0, 101.0, 99.0, 100.0), TradeExitReason.TIME_HORIZON.value, 100.0),
        ((100.0, 110.0, 99.0, 109.0), TradeExitReason.TAKE_PROFIT.value, 110.0),
        ((100.0, 110.0, 97.0, 101.0), TradeExitReason.STOP_LOSS.value, 98.0),
    ],
)
def test_trailing_does_not_change_stop_after_no_activation_or_same_bar_exit(
    bar, reason, exit_price
):
    trades, _ = BacktestEngine(_trailing_spot_config()).run(
        _trailing_spot_bars(bar), [make_test_signal(atr=2.0)]
    )
    assert len(trades) == 1
    assert trades[0].exit_reason == reason
    assert trades[0].exit_price == pytest.approx(exit_price)
    assert trades[0].sl_price == trades[0].initial_stop_price == pytest.approx(98.0)


def test_signal_specific_risk_controls_trailing_activation_without_changing_r():
    signal = replace(make_test_signal(atr=2.0), sl_atr_multiple=2.0)
    bars = _trailing_spot_bars(
        (100.0, 103.0, 99.0, 102.0),  # Below the signal-specific +1R = 104.
        (102.0, 105.0, 99.0, 103.0),  # Activation occurs after this bar.
        (102.0, 103.0, 99.0, 100.0),
    )
    trades, equity = BacktestEngine(_trailing_spot_config()).run(bars, [signal])
    trade = trades[0]
    assert trade.exit_timestamp == bars.iloc[4]["timestamp"]
    assert trade.sl_price == pytest.approx(100.0)
    assert trade.initial_stop_price == pytest.approx(96.0)
    assert trade.initial_risk_amount == pytest.approx(40.0)
    assert trade.r_multiple == trade.net_r_multiple == pytest.approx(0.0)
    assert equity[-1].equity == pytest.approx(1000.0)


def test_final_candle_time_exit_does_not_apply_trailing_after_close():
    bars = _trailing_spot_bars((100.0, 103.0, 99.0, 101.0))
    trades, equity = BacktestEngine(_trailing_spot_config()).run(
        bars, [make_test_signal(atr=2.0)]
    )
    assert trades[0].exit_reason == TradeExitReason.TIME_HORIZON.value
    assert trades[0].sl_price == pytest.approx(98.0)
    assert trades[0].initial_stop_price == pytest.approx(98.0)
    assert equity[-1].equity == pytest.approx(1010.0)


@pytest.mark.parametrize(
    ("exit_bar", "status", "reason", "fill"),
    [
        ((100.0, 105.0, 97.0, 101.0), "INTRABAR_SL_FIRST", "STOP_LOSS", 98.0),
        ((97.0, 105.0, 96.0, 101.0), "OPENING_LEVEL_REVIEW", "STOP_LOSS", 97.0),
        ((105.0, 106.0, 97.0, 101.0), "OPENING_LEVEL_REVIEW", "TAKE_PROFIT", 104.0),
        ((97.0, 101.0, 96.0, 100.0), "OPENING_LEVEL_REVIEW", "STOP_LOSS", 97.0),
        ((105.0, 106.0, 99.0, 105.0), "OPENING_LEVEL_REVIEW", "TAKE_PROFIT", 104.0),
        ((98.0, 105.0, 97.0, 101.0), "OPENING_LEVEL_REVIEW", "STOP_LOSS", 98.0),
        ((100.0, 101.0, 97.0, 100.0), "NO_IDENTIFIED_CONFLICT", "STOP_LOSS", 98.0),
        ((100.0, 105.0, 99.0, 104.0), "NO_IDENTIFIED_CONFLICT", "TAKE_PROFIT", 104.0),
        ((100.0, 101.0, 99.0, 100.0), "NO_IDENTIFIED_CONFLICT", "TIME_HORIZON", 100.0),
    ],
)
def test_exit_trace_distinguishes_intrabar_conflict_opening_level_and_clean_checks(
    exit_bar, status, reason, fill
):
    bars = _trailing_spot_bars(exit_bar)
    cfg = BacktestConfig(
        initial_capital=1000.0,
        taker_fee_pct=0.001,
        slippage_pct=0.0,
        sl_atr_multiple=1.0,
        tp_atr_multiple=2.0,
    )
    trades, equity = BacktestEngine(cfg).run(bars, [make_test_signal(atr=2.0)])
    assert len(trades) == 1
    trade = trades[0]
    assert trade.execution_trace_status == status
    assert trade.exit_reason == reason
    assert trade.exit_price == pytest.approx(fill)
    assert trade.initial_stop_price == trade.sl_price == pytest.approx(98.0)
    assert trade.r_multiple == pytest.approx(
        trade.gross_pnl / trade.initial_risk_amount
    )
    assert trade.net_r_multiple == pytest.approx(
        trade.net_pnl / trade.initial_risk_amount
    )
    assert equity[-1].cash == equity[-1].equity == pytest.approx(1000.0 + trade.net_pnl)
    assert trade.fee_entry == pytest.approx(1.0)
    assert trade.fee_exit == pytest.approx(trade.notional_exit * 0.001)


def test_entry_bar_conflict_is_intrabar_not_a_gap_before_position_existed():
    bars = _trailing_spot_bars()
    bars.loc[1, ["high", "low"]] = [105.0, 97.0]
    cfg = BacktestConfig(
        initial_capital=1000.0,
        taker_fee_pct=0.0,
        slippage_pct=0.0,
        sl_atr_multiple=1.0,
        tp_atr_multiple=2.0,
    )
    trades, _ = BacktestEngine(cfg).run(bars, [make_test_signal(atr=2.0)])
    assert (
        trades[0].entry_timestamp
        == trades[0].exit_timestamp
        == bars.iloc[1]["timestamp"]
    )
    assert (
        trades[0].execution_trace_status == ExecutionTraceStatus.INTRABAR_SL_FIRST.value
    )
    assert trades[0].exit_price == pytest.approx(98.0)


def test_break_even_stop_is_the_active_level_for_conflict_trace():
    bars = _trailing_spot_bars(
        (100.0, 103.0, 99.0, 101.0),
        (101.0, 110.0, 99.0, 101.0),
    )
    trades, _ = BacktestEngine(_trailing_spot_config()).run(
        bars, [make_test_signal(atr=2.0)]
    )
    trade = trades[0]
    assert trade.sl_price == pytest.approx(100.0)
    assert trade.initial_stop_price == pytest.approx(98.0)
    assert trade.execution_trace_status == ExecutionTraceStatus.INTRABAR_SL_FIRST.value
    assert trade.exit_reason == TradeExitReason.STOP_LOSS.value
    assert trade.exit_price == pytest.approx(100.0)
    assert trade.r_multiple == trade.net_r_multiple == pytest.approx(0.0)


def test_exit_trace_does_not_change_financial_aggregates():
    bars = _trailing_spot_bars((100.0, 105.0, 97.0, 101.0))
    cfg = BacktestConfig(
        initial_capital=1000.0,
        taker_fee_pct=0.001,
        slippage_pct=0.0,
        sl_atr_multiple=1.0,
        tp_atr_multiple=2.0,
    )
    trades, equity = BacktestEngine(cfg).run(bars, [make_test_signal(atr=2.0)])
    current = BacktestMetricsCalculator.calculate_metrics(trades, equity, 1000.0)
    without_trace = BacktestMetricsCalculator.calculate_metrics(
        [replace(trades[0], execution_trace_status=None)], equity, 1000.0
    )
    assert current == without_trace


def test_atr_floor_and_entry_slippage_are_in_initial_risk():
    cfg = BacktestConfig(
        initial_capital=1000.0,
        taker_fee_pct=0.001,
        slippage_pct=0.01,
        tp_atr_multiple=10.0,
        sl_atr_multiple=2.0,
        max_holding_bars=2,
    )
    trades, _ = BacktestEngine(cfg).run(
        _flat_spot_bars(), signals=[make_test_signal(atr=0.0)]
    )
    trade = trades[0]
    assert trade.entry_price == pytest.approx(101.0)
    assert trade.initial_stop_price == pytest.approx(99.99)
    assert trade.initial_risk_per_unit == pytest.approx(1.01)
    assert trade.initial_risk_amount == pytest.approx(trade.size_units * 1.01)
    assert trade.r_multiple == pytest.approx(
        trade.gross_pnl / trade.initial_risk_amount
    )
    assert trade.net_r_multiple == pytest.approx(
        trade.net_pnl / trade.initial_risk_amount
    )


def test_time_exit_without_price_move_has_negative_net_r_from_fees():
    cfg = BacktestConfig(
        initial_capital=1000.0,
        taker_fee_pct=0.001,
        slippage_pct=0.0,
        tp_atr_multiple=10.0,
        sl_atr_multiple=1.0,
        max_holding_bars=2,
    )
    trades, equity = BacktestEngine(cfg).run(
        _flat_spot_bars(), signals=[make_test_signal(atr=2.0)]
    )
    trade = trades[0]
    assert trade.exit_reason == TradeExitReason.TIME_HORIZON.value
    assert trade.r_multiple == pytest.approx(0.0)
    assert trade.net_r_multiple == pytest.approx(-1.999 / 19.98)
    assert trade.net_r_multiple < 0
    assert equity[-1].equity - 1000.0 == pytest.approx(trade.net_pnl)


@pytest.mark.parametrize("sl_multiplier", [0.0, -1.0, 50.0, 51.0])
def test_invalid_initial_stop_rejected_before_position_open(sl_multiplier):
    cfg = BacktestConfig(sl_atr_multiple=sl_multiplier, slippage_pct=0.0)
    with pytest.raises(BacktestValidationError, match="Stop inicial"):
        BacktestEngine(cfg).run(_flat_spot_bars(), signals=[make_test_signal(atr=2.0)])


@pytest.mark.parametrize("sl_multiplier", [float("nan"), float("inf"), 1e308])
def test_nonfinite_initial_stop_or_risk_rejected(sl_multiplier):
    cfg = BacktestConfig(sl_atr_multiple=sl_multiplier)
    with pytest.raises(BacktestValidationError, match="no finitos"):
        BacktestEngine(cfg).run(_flat_spot_bars(), signals=[make_test_signal(atr=2.0)])


@pytest.mark.parametrize(
    ("exit_price", "fee_rate", "fraction"),
    [
        (100.0, 0.0, 1.0),
        (100.0, 0.001, 1.0),
        (110.0, 0.001, 1.0),
        (90.0, 0.001, 1.0),
        (100.0, 0.001, 0.25),
        (100.0, 0.001, 0.50),
    ],
)
def test_spot_long_cash_equity_and_pnl_reconcile(exit_price, fee_rate, fraction):
    capital = 1000.0
    allocation = capital * fraction
    cfg = BacktestConfig(
        initial_capital=capital,
        position_size_pct=fraction,
        taker_fee_pct=fee_rate,
        slippage_pct=0.0,
        max_holding_bars=2,
        tp_atr_multiple=50.0,
        sl_atr_multiple=50.0,
    )
    signal = make_test_signal(atr=1.0)
    trades, equity = BacktestEngine(cfg).run(
        _flat_spot_bars(exit_price), signals=[signal]
    )

    assert len(trades) == 1
    trade = trades[0]
    fee_entry = allocation * fee_rate
    units = (allocation - fee_entry) / 100.0
    gross_pnl = units * (exit_price - 100.0)
    fee_exit = units * exit_price * fee_rate
    net_pnl = gross_pnl - fee_entry - fee_exit
    assert trade.entry_price == pytest.approx(100.0)
    assert trade.exit_price == pytest.approx(exit_price)
    assert trade.notional_entry == pytest.approx(allocation)
    assert trade.size_units == pytest.approx(units)
    assert trade.fee_entry == pytest.approx(fee_entry)
    assert trade.fee_exit == pytest.approx(fee_exit)
    assert trade.gross_pnl == pytest.approx(gross_pnl)
    assert trade.net_pnl == pytest.approx(net_pnl)
    assert trade.initial_stop_price == pytest.approx(50.0)
    assert trade.initial_risk_amount == pytest.approx(units * 50.0)
    assert trade.r_multiple == pytest.approx(gross_pnl / (units * 50.0))
    assert trade.net_r_multiple == pytest.approx(net_pnl / (units * 50.0))
    assert equity[1].cash == pytest.approx(capital - allocation)
    assert equity[1].equity == pytest.approx(capital - allocation + units * 100.0)
    assert equity[-1].cash == pytest.approx(
        capital - allocation + units * exit_price - fee_exit
    )
    assert equity[-1].equity == pytest.approx(equity[-1].cash)
    assert equity[-1].equity - capital == pytest.approx(trade.net_pnl, abs=1e-8)
    assert all(point.cash >= 0 for point in equity)


def test_engine_equity_drawdown_matches_metrics_and_preserves_r_accounting():
    cfg = BacktestConfig(
        initial_capital=1000.0,
        taker_fee_pct=0.0,
        slippage_pct=0.0,
        tp_atr_multiple=50.0,
        sl_atr_multiple=50.0,
        max_holding_bars=2,
    )
    trades, equity = BacktestEngine(cfg).run(
        _flat_spot_bars(90.0), signals=[make_test_signal(atr=1.0)]
    )
    trade = trades[0]
    metrics = BacktestMetricsCalculator.calculate_metrics(
        trades, equity, initial_capital=cfg.initial_capital
    )
    assert [point.drawdown_pct for point in equity] == pytest.approx([0.0, 0.0, 10.0])
    assert metrics["max_drawdown_pct"] == 10.0
    assert metrics["max_drawdown_usd"] == 100.0
    assert trade.initial_risk_amount == pytest.approx(500.0)
    assert trade.r_multiple == pytest.approx(-0.2)
    assert trade.net_r_multiple == pytest.approx(-0.2)
    assert equity[-1].cash == pytest.approx(900.0)
    assert equity[-1].equity - cfg.initial_capital == pytest.approx(trade.net_pnl)


def test_spot_long_entry_slippage_and_fees_are_each_charged_once():
    cfg = BacktestConfig(
        initial_capital=1000.0,
        taker_fee_pct=0.001,
        slippage_pct=0.01,
        max_holding_bars=2,
        tp_atr_multiple=50.0,
        sl_atr_multiple=50.0,
    )
    trades, equity = BacktestEngine(cfg).run(
        _flat_spot_bars(), signals=[make_test_signal(atr=1.0)]
    )
    trade = trades[0]
    assert trade.entry_price == pytest.approx(101.0)
    assert trade.exit_price == pytest.approx(99.0)
    assert trade.size_units == pytest.approx(999.0 / 101.0)
    assert equity[1].equity == pytest.approx(trade.size_units * 100.0)
    assert equity[-1].equity - 1000.0 == pytest.approx(trade.net_pnl, abs=1e-8)


def test_two_spot_round_trips_do_not_create_capital():
    cfg = BacktestConfig(
        initial_capital=1000.0,
        taker_fee_pct=0.001,
        slippage_pct=0.0,
        max_holding_bars=2,
        tp_atr_multiple=50.0,
        sl_atr_multiple=50.0,
    )
    bars = _flat_spot_bars(count=6)
    signals = [
        make_test_signal("2024-01-01 00:00:00", atr=1.0),
        make_test_signal("2024-01-01 03:00:00", atr=1.0),
    ]
    trades, equity = BacktestEngine(cfg).run(bars, signals=signals)
    assert len(trades) == 2
    assert equity[-1].equity == pytest.approx(1000.0 * (1 - 0.001) ** 4)
    assert equity[-1].equity - 1000.0 == pytest.approx(
        sum(trade.net_pnl for trade in trades), abs=1e-8
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"direction": "SHORT"}, "SHORT"),
        ({"direction": "BOTH"}, "BOTH"),
        ({"leverage": 2.0}, "leverage"),
        ({"market_type": "PERP"}, "PERP"),
        ({"market_type": "PERP", "leverage": 3.0}, "PERP"),
        ({"initial_capital": float("nan")}, "initial_capital"),
        ({"position_size_pct": float("inf")}, "position_size_pct"),
        ({"taker_fee_pct": float("nan")}, "taker_fee_pct"),
        ({"slippage_pct": float("inf")}, "slippage_pct"),
    ],
)
def test_unsupported_or_nonfinite_backtest_config_rejected(changes, message):
    cfg = BacktestConfig(**changes)
    with pytest.raises(BacktestValidationError, match=message):
        BacktestEngine(cfg).run(_flat_spot_bars(), signals=[make_test_signal()])


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), -1.0])
def test_nonfinite_or_negative_market_price_rejected(bad_value):
    bars = _flat_spot_bars()
    bars.loc[1, "open"] = bad_value
    with pytest.raises(BacktestValidationError, match="open"):
        BacktestEngine().run(bars, signals=[make_test_signal()])


def test_nonfinite_signal_atr_rejected_before_entry():
    signal = replace(make_test_signal(), atr=float("nan"))
    with pytest.raises(BacktestValidationError, match="ATR"):
        BacktestEngine().run(_flat_spot_bars(), signals=[signal])


def test_extreme_finite_price_cannot_create_infinite_units():
    bars = _flat_spot_bars()
    for column in ("open", "high", "low", "close"):
        bars.loc[1, column] = 5e-324
    with pytest.raises(BacktestValidationError, match="Unidades SPOT"):
        BacktestEngine().run(bars, signals=[make_test_signal()])


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda bars: bars.iloc[::-1].reset_index(drop=True), "desordenado"),
        (lambda bars: bars.iloc[[0, 2, 1, 3]].reset_index(drop=True), "desordenado"),
        (
            lambda bars: bars.assign(
                timestamp=lambda frame: frame["timestamp"].where(
                    frame.index != 2, frame.loc[1, "timestamp"]
                )
            ),
            "duplicado",
        ),
        (
            lambda bars: bars.assign(
                timestamp=lambda frame: frame["timestamp"].where(
                    frame.index != 2, pd.NaT
                )
            ),
            "nulos",
        ),
        (lambda bars: bars.assign(timestamp=[0, 1, 2, 3]), "ambiguo"),
        (lambda bars: bars.assign(timestamp=["01/02/2024"] * 4), "ambiguo"),
    ],
)
def test_engine_rejects_invalid_chronology_before_financial_execution(
    change, message, monkeypatch
):
    bars = change(_flat_spot_bars(count=4))
    original = bars.copy(deep=True)
    engine = BacktestEngine()

    def execution_must_not_start(*_args, **_kwargs):
        pytest.fail("El motor comenzó a filtrar señales antes del rechazo temporal")

    monkeypatch.setattr(engine, "_passes_signal_filters", execution_must_not_start)
    with pytest.raises(BacktestValidationError, match=message):
        engine.run(bars, signals=[make_test_signal()])
    pd.testing.assert_frame_equal(bars, original)


def test_engine_accepts_utc_normalization_and_keeps_next_bar_entry():
    bars = _flat_spot_bars(count=4)
    bars["timestamp"] = [
        "2024-01-01T01:00:00+01:00",
        "2024-01-01T00:00:00-01:00",
        "2024-01-01 02:00:00",
        "2024-01-01T03:00:00Z",
    ]
    trades, equity = BacktestEngine().run(bars, signals=[make_test_signal()])
    assert len(trades) == 1
    assert trades[0].entry_timestamp > trades[0].signal_timestamp
    assert [point.timestamp for point in equity] == list(
        pd.date_range("2024-01-01", periods=4, freq="1h", tz="UTC")
    )


def test_engine_does_not_treat_rows_without_columns_as_empty():
    with pytest.raises(ValueError, match="columnas"):
        BacktestEngine().run(pd.DataFrame(index=range(3)))


# -----------------------------------------------------------------------------
# P0-003C-C1: Casos Numéricos Obligatorios (Casos A a L)
# -----------------------------------------------------------------------------


def _make_c1_bars(exit_bar: tuple[float, float, float, float]) -> pd.DataFrame:
    """Prepara 3 velas: señal (C=100, ATR=2), entrada (O=100) y vela de salida."""
    candles = [
        (100.0, 101.0, 99.0, 100.0),
        (100.0, 101.0, 99.0, 100.0),
        exit_bar,
    ]
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(
                "2024-01-01", periods=len(candles), freq="1h", tz="UTC"
            ),
            "open": [b[0] for b in candles],
            "high": [b[1] for b in candles],
            "low": [b[2] for b in candles],
            "close": [b[3] for b in candles],
            "volume": [1000.0] * len(candles),
        }
    )


def _c1_config(**kwargs) -> BacktestConfig:
    params = dict(
        initial_capital=1000.0,
        position_size_pct=1.0,
        taker_fee_pct=0.0,
        slippage_pct=0.0,
        tp_atr_multiple=2.0,
        sl_atr_multiple=1.0,
        max_holding_bars=10,
    )
    params.update(kwargs)
    return BacktestConfig(**params)


def test_p0_003c_c1_case_a_adverse_gap():
    """CASO A — Gap desfavorable: Open=95 <= SL=98. High posterior (105) no afecta."""
    bars = _make_c1_bars((95.0, 105.0, 94.0, 101.0))
    trades, equity = BacktestEngine(_c1_config()).run(bars, [make_test_signal(atr=2.0)])
    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_price == pytest.approx(95.0)
    assert trade.exit_reason == TradeExitReason.STOP_LOSS.value
    assert trade.gross_pnl == pytest.approx(-50.0)
    assert trade.r_multiple == pytest.approx(-2.5)
    assert (
        trade.execution_trace_status == ExecutionTraceStatus.OPENING_LEVEL_REVIEW.value
    )
    assert equity[-1].equity == pytest.approx(950.0)


def test_p0_003c_c1_case_b_favorable_gap():
    """CASO B — Gap favorable: Open=106 >= TP=104. Low posterior (97) no convierte a SL."""
    bars = _make_c1_bars((106.0, 107.0, 97.0, 100.0))
    trades, equity = BacktestEngine(_c1_config()).run(bars, [make_test_signal(atr=2.0)])
    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_price == pytest.approx(104.0)  # TP limit fill sin gap improvement
    assert trade.exit_reason == TradeExitReason.TAKE_PROFIT.value
    assert trade.gross_pnl == pytest.approx(40.0)
    assert trade.r_multiple == pytest.approx(2.0)
    assert (
        trade.execution_trace_status == ExecutionTraceStatus.OPENING_LEVEL_REVIEW.value
    )
    assert equity[-1].equity == pytest.approx(1040.0)


def test_p0_003c_c1_case_c_opening_between_levels_intrabar_conflict():
    """CASO C — Apertura entre niveles: Open=100. High=105 y Low=95. SL primero."""
    bars = _make_c1_bars((100.0, 105.0, 95.0, 101.0))
    trades, equity = BacktestEngine(_c1_config()).run(bars, [make_test_signal(atr=2.0)])
    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_price == pytest.approx(98.0)
    assert trade.exit_reason == TradeExitReason.STOP_LOSS.value
    assert trade.gross_pnl == pytest.approx(-20.0)
    assert trade.r_multiple == pytest.approx(-1.0)
    assert trade.execution_trace_status == ExecutionTraceStatus.INTRABAR_SL_FIRST.value


def test_p0_003c_c1_case_d_only_sl_intrabar():
    """CASO D — Solo SL: Open=100. Low=97 <= 98, High=101 < 104."""
    bars = _make_c1_bars((100.0, 101.0, 97.0, 100.0))
    trades, _ = BacktestEngine(_c1_config()).run(bars, [make_test_signal(atr=2.0)])
    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_price == pytest.approx(98.0)
    assert trade.exit_reason == TradeExitReason.STOP_LOSS.value
    assert trade.gross_pnl == pytest.approx(-20.0)
    assert trade.r_multiple == pytest.approx(-1.0)
    assert (
        trade.execution_trace_status
        == ExecutionTraceStatus.NO_IDENTIFIED_CONFLICT.value
    )


def test_p0_003c_c1_case_e_only_tp_intrabar():
    """CASO E — Solo TP: Open=100. High=105 >= 104, Low=99 > 98."""
    bars = _make_c1_bars((100.0, 105.0, 99.0, 104.0))
    trades, _ = BacktestEngine(_c1_config()).run(bars, [make_test_signal(atr=2.0)])
    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_price == pytest.approx(104.0)
    assert trade.exit_reason == TradeExitReason.TAKE_PROFIT.value
    assert trade.gross_pnl == pytest.approx(40.0)
    assert trade.r_multiple == pytest.approx(2.0)
    assert (
        trade.execution_trace_status
        == ExecutionTraceStatus.NO_IDENTIFIED_CONFLICT.value
    )


def test_p0_003c_c1_ordinary_tp_limit_ignores_adverse_exit_slippage():
    """A touched SPOT LONG TP limit cannot fill below its own limit price."""
    bars = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC"),
            "open": [100.0, 100.0, 102.0],
            "high": [101.0, 102.0, 106.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.0, 101.0, 105.0],
        }
    )
    cfg = _c1_config(slippage_pct=0.01, taker_fee_pct=0.001)
    trades, equity = BacktestEngine(cfg).run(bars, [make_test_signal(atr=2.0)])
    trade = trades[0]
    assert trade.entry_price == pytest.approx(101.0)
    assert trade.tp_price == pytest.approx(105.0)
    assert trade.exit_price == pytest.approx(trade.tp_price)
    assert trade.exit_reason == TradeExitReason.TAKE_PROFIT.value
    assert trade.fee_entry == pytest.approx(1.0)
    assert trade.fee_exit == pytest.approx(trade.size_units * trade.tp_price * 0.001)
    assert trade.net_pnl == pytest.approx(
        trade.gross_pnl - trade.fee_entry - trade.fee_exit
    )
    assert trade.r_multiple == pytest.approx(
        trade.gross_pnl / trade.initial_risk_amount
    )
    assert trade.net_r_multiple == pytest.approx(
        trade.net_pnl / trade.initial_risk_amount
    )
    assert trade.execution_policy_version == "SPOT_LONG_C1_OPEN_PRIORITY_TP_LIMIT"
    assert equity[-1].cash == equity[-1].equity == pytest.approx(1000.0 + trade.net_pnl)


def test_p0_003c_c1_case_f_opening_exactly_at_sl():
    """CASO F — Apertura exactamente en SL: Open=98 == SL."""
    bars = _make_c1_bars((98.0, 105.0, 97.0, 101.0))
    trades, _ = BacktestEngine(_c1_config()).run(bars, [make_test_signal(atr=2.0)])
    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_price == pytest.approx(98.0)
    assert trade.exit_reason == TradeExitReason.STOP_LOSS.value
    assert (
        trade.execution_trace_status == ExecutionTraceStatus.OPENING_LEVEL_REVIEW.value
    )


def test_p0_003c_c1_case_g_opening_exactly_at_tp():
    """CASO G — Apertura exactamente en TP: Open=104 == TP."""
    bars = _make_c1_bars((104.0, 105.0, 97.0, 101.0))
    trades, _ = BacktestEngine(_c1_config()).run(bars, [make_test_signal(atr=2.0)])
    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_price == pytest.approx(104.0)
    assert trade.exit_reason == TradeExitReason.TAKE_PROFIT.value
    assert (
        trade.execution_trace_status == ExecutionTraceStatus.OPENING_LEVEL_REVIEW.value
    )


def test_p0_003c_c1_case_h_stop_moved_to_break_even():
    """CASO H — Stop movido a break-even en T, ejecutado en T+1."""
    # Bar 0: Señal. Bar 1: Entrada 100, High=103 (+1.5R >= 1.0R) -> activa break-even (100).
    # Bar 2 (T+1): Gap down en apertura a 99.0 <= 100.0.
    bars_gap = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC"),
            "open": [100.0, 100.0, 99.0],
            "high": [101.0, 103.0, 102.0],
            "low": [99.0, 99.5, 98.0],
            "close": [100.0, 102.0, 100.0],
            "volume": [1000.0] * 3,
        }
    )
    cfg = _c1_config(enable_trailing_stop=True, trailing_stop_activation_r=1.0)
    trades_gap, _ = BacktestEngine(cfg).run(bars_gap, [make_test_signal(atr=2.0)])
    assert trades_gap[0].exit_price == pytest.approx(99.0)
    assert trades_gap[0].exit_reason == TradeExitReason.STOP_LOSS.value
    assert trades_gap[0].sl_price == pytest.approx(100.0)
    assert trades_gap[0].initial_stop_price == pytest.approx(98.0)
    assert (
        trades_gap[0].execution_trace_status
        == ExecutionTraceStatus.OPENING_LEVEL_REVIEW.value
    )

    # Sub-caso H2: Apertura en 101 > 100, luego intrabar toca 100.0.
    bars_intrabar = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC"),
            "open": [100.0, 100.0, 101.0],
            "high": [101.0, 103.0, 102.0],
            "low": [99.0, 99.5, 99.0],  # Low cruza 100.0
            "close": [100.0, 102.0, 101.0],
            "volume": [1000.0] * 3,
        }
    )
    trades_intra, _ = BacktestEngine(cfg).run(
        bars_intrabar, [make_test_signal(atr=2.0)]
    )
    assert trades_intra[0].exit_price == pytest.approx(100.0)
    assert trades_intra[0].exit_reason == TradeExitReason.STOP_LOSS.value
    assert (
        trades_intra[0].execution_trace_status
        == ExecutionTraceStatus.NO_IDENTIFIED_CONFLICT.value
    )


def test_p0_003c_c1_case_i_new_entry_on_current_bar_ignores_gap():
    """CASO I — Nueva entrada en apertura actual: no existe orden previa ni gap de salida."""
    bars = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=2, freq="1h", tz="UTC"),
            "open": [100.0, 100.0],
            "high": [101.0, 105.0],
            "low": [99.0, 95.0],
            "close": [100.0, 101.0],
            "volume": [1000.0, 1000.0],
        }
    )
    trades, _ = BacktestEngine(_c1_config()).run(bars, [make_test_signal(atr=2.0)])
    assert len(trades) == 1
    trade = trades[0]
    assert trade.entry_timestamp == trade.exit_timestamp
    assert trade.exit_price == pytest.approx(98.0)
    assert trade.exit_reason == TradeExitReason.STOP_LOSS.value
    assert trade.execution_trace_status == ExecutionTraceStatus.INTRABAR_SL_FIRST.value
    assert trade.mfe_pct == pytest.approx(5.0)
    assert trade.mae_pct == pytest.approx(5.0)


def test_p0_003c_c1_case_j_slippage_effects_on_stop_and_limit():
    """CASO J — Gap y slippage distinto de cero: stop-market sufre slippage, TP limit no."""
    cfg = _c1_config(slippage_pct=0.001)  # 0.1%

    # Sub-caso J1: Gap desfavorable (Open=95). Exit = 95 * (1 - 0.001) = 94.905
    bars_sl = _make_c1_bars((95.0, 105.0, 94.0, 101.0))
    trades_sl, _ = BacktestEngine(cfg).run(bars_sl, [make_test_signal(atr=2.0)])
    assert trades_sl[0].exit_price == pytest.approx(94.905)
    assert trades_sl[0].exit_reason == TradeExitReason.STOP_LOSS.value

    # Sub-caso J2: Gap favorable (Open=106). Exit = TP (104.1 debido a entry slippage), sin slippage adverso por debajo del límite
    bars_tp = _make_c1_bars((106.0, 107.0, 97.0, 100.0))
    trades_tp, _ = BacktestEngine(cfg).run(bars_tp, [make_test_signal(atr=2.0)])
    assert trades_tp[0].entry_price == pytest.approx(100.1)
    assert trades_tp[0].tp_price == pytest.approx(104.1)
    assert trades_tp[0].exit_price == pytest.approx(104.1)
    assert trades_tp[0].exit_reason == TradeExitReason.TAKE_PROFIT.value


def test_p0_003c_c1_case_k_exit_fee_reconciliation():
    """CASO K — Comisión de salida distinta de cero con conciliación contable exacta."""
    cfg = _c1_config(taker_fee_pct=0.001)
    bars = _make_c1_bars((95.0, 105.0, 94.0, 101.0))
    trades, equity = BacktestEngine(cfg).run(bars, [make_test_signal(atr=2.0)])
    trade = trades[0]
    assert trade.fee_entry == pytest.approx(1.0)
    assert trade.fee_exit == pytest.approx(trade.notional_exit * 0.001)
    assert equity[-1].equity - cfg.initial_capital == pytest.approx(
        trade.net_pnl, abs=1e-8
    )
    assert equity[-1].cash == pytest.approx(equity[-1].equity)


def test_p0_003c_c1_case_l_gap_followed_by_both_extremes():
    """CASO L — Gap en apertura seguido por ambos extremos intrabar posteriores."""
    # L1: Gap desfavorable a 95, seguido de High=105 (cruza TP) y Low=94.
    bars_down = _make_c1_bars((95.0, 105.0, 94.0, 101.0))
    trades_down, _ = BacktestEngine(_c1_config()).run(
        bars_down, [make_test_signal(atr=2.0)]
    )
    assert trades_down[0].exit_price == pytest.approx(95.0)
    assert trades_down[0].exit_reason == TradeExitReason.STOP_LOSS.value
    assert (
        trades_down[0].execution_trace_status
        == ExecutionTraceStatus.OPENING_LEVEL_REVIEW.value
    )

    # L2: Gap favorable a 106, seguido de Low=97 (cruza SL) y High=107.
    bars_up = _make_c1_bars((106.0, 107.0, 97.0, 100.0))
    trades_up, _ = BacktestEngine(_c1_config()).run(
        bars_up, [make_test_signal(atr=2.0)]
    )
    assert trades_up[0].exit_price == pytest.approx(104.0)
    assert trades_up[0].exit_reason == TradeExitReason.TAKE_PROFIT.value
    assert (
        trades_up[0].execution_trace_status
        == ExecutionTraceStatus.OPENING_LEVEL_REVIEW.value
    )


def _assert_d1a_rejection_has_no_financial_effect(error, config, entry_timestamp):
    traceback = error.__traceback__
    while traceback is not None and traceback.tb_frame.f_code.co_name != "run":
        traceback = traceback.tb_next
    assert traceback is not None
    state = traceback.tb_frame.f_locals
    assert (
        state["bar_ts"] == entry_timestamp
    )  # Rejection is at Open(T+1), not at signal Close(T).
    assert state["current_cash"] == config.initial_capital
    assert state["active_position"] is None
    assert state["closed_trades"] == []
    assert "fee_entry" not in state
    assert "size_units" not in state
    assert "fee_exit" not in state
    assert "notional_exit" not in state
    return state


@pytest.mark.parametrize(
    ("tp_multiple", "slippage", "expected_entry", "expected_target"),
    [
        (-50.0, 0.0, 100.0, 0.0),
        (-50.5, 0.0, 100.0, -1.0),
        (-0.5, 0.0, 100.0, 99.0),
        (0.0, 0.0, 100.0, 100.0),
        (-0.25, 0.01, 101.0, 100.5),
    ],
)
def test_d1a_invalid_take_profit_rejected_before_position_or_cash_change(
    tp_multiple,
    slippage,
    expected_entry,
    expected_target,
):
    bars = _make_c1_bars((100.0, 101.0, 99.0, 100.0))
    config = _c1_config(
        position_size_pct=0.25, taker_fee_pct=0.001, slippage_pct=slippage
    )
    signal = replace(make_test_signal(atr=2.0), tp_atr_multiple=tp_multiple)

    with pytest.raises(
        BacktestValidationError, match="Take Profit SPOT LONG inválido"
    ) as error:
        BacktestEngine(config).run(bars, [signal])

    state = _assert_d1a_rejection_has_no_financial_effect(
        error.value, config, bars.iloc[1]["timestamp"]
    )
    assert state["entry_price"] == pytest.approx(expected_entry)
    assert state["tp_price"] == pytest.approx(expected_target)


@pytest.mark.parametrize(
    "tp_multiple", [float("nan"), float("inf"), -float("inf"), "invalid", True, 1e308]
)
def test_d1a_nonfinite_or_nonnumeric_take_profit_rejected(tp_multiple):
    bars = _make_c1_bars((100.0, 101.0, 99.0, 100.0))
    config = _c1_config(position_size_pct=0.25, taker_fee_pct=0.001)
    signal = replace(make_test_signal(atr=2.0), tp_atr_multiple=tp_multiple)

    with pytest.raises(BacktestValidationError, match="Take Profit SPOT LONG") as error:
        BacktestEngine(config).run(bars, [signal])

    _assert_d1a_rejection_has_no_financial_effect(
        error.value, config, bars.iloc[1]["timestamp"]
    )


def test_d1a_finite_take_profit_with_overflowing_exit_notional_is_rejected():
    bars = _make_c1_bars((100.0, 101.0, 99.0, 100.0))
    config = _c1_config(position_size_pct=0.25, taker_fee_pct=0.001)
    signal = replace(make_test_signal(atr=2.0), tp_atr_multiple=5e307)

    with pytest.raises(
        BacktestValidationError, match="Take Profit SPOT LONG inválido: notional"
    ) as error:
        BacktestEngine(config).run(bars, [signal])

    traceback = error.value.__traceback__
    while traceback is not None and traceback.tb_frame.f_code.co_name != "run":
        traceback = traceback.tb_next
    assert traceback is not None
    state = traceback.tb_frame.f_locals
    assert state["tp_price"] > state["entry_price"] > 0
    assert state["current_cash"] == config.initial_capital
    assert state["active_position"] is None
    assert state["closed_trades"] == []
    assert "fee_exit" not in state


@pytest.mark.parametrize(
    ("tp_multiple", "slippage", "expected_entry", "expected_target"),
    [
        (2.0, 0.0, 100.0, 104.0),
        (1e-9, 0.0, 100.0, 100.000000002),
        (0.1, 0.01, 101.0, 101.2),
    ],
)
def test_d1a_valid_take_profit_preserves_next_bar_entry_and_accounting(
    tp_multiple,
    slippage,
    expected_entry,
    expected_target,
):
    bars = _make_c1_bars((100.0, 105.0, 99.0, 104.0))
    bars.loc[1, ["high", "low", "close"]] = [102.0, 100.0, 101.0]
    config = _c1_config(
        position_size_pct=0.25, taker_fee_pct=0.001, slippage_pct=slippage
    )
    signal = replace(make_test_signal(atr=2.0), tp_atr_multiple=tp_multiple)

    trades, equity = BacktestEngine(config).run(bars, [signal])

    assert len(trades) == 1
    trade = trades[0]
    assert trade.entry_timestamp == bars.iloc[1]["timestamp"]
    assert trade.entry_price == pytest.approx(expected_entry)
    assert trade.tp_price == pytest.approx(expected_target)
    assert trade.tp_price > trade.entry_price
    assert trade.size_units > 0
    assert trade.fee_entry > 0
    assert trade.fee_exit >= 0
    assert trade.initial_risk_amount == pytest.approx(
        trade.size_units * (trade.entry_price - trade.initial_stop_price)
    )
    assert trade.r_multiple == pytest.approx(
        trade.gross_pnl / trade.initial_risk_amount
    )
    assert trade.net_r_multiple == pytest.approx(
        trade.net_pnl / trade.initial_risk_amount
    )
    assert trade.net_pnl == pytest.approx(
        trade.gross_pnl - trade.fee_entry - trade.fee_exit
    )
    assert (
        equity[-1].cash
        == equity[-1].equity
        == pytest.approx(config.initial_capital + trade.net_pnl)
    )


def test_d1a_invalid_take_profit_after_closed_trade_preserves_existing_accounting():
    bars = _make_c1_bars((100.0, 105.0, 99.0, 104.0))
    bars.loc[3] = [
        bars.iloc[2]["timestamp"] + pd.Timedelta(hours=1),
        100.0,
        101.0,
        99.0,
        100.0,
        1000.0,
    ]
    config = _c1_config(taker_fee_pct=0.001)
    first_signal = make_test_signal(atr=2.0)
    invalid_signal = replace(
        make_test_signal(timestamp=str(bars.iloc[2]["timestamp"]), atr=2.0),
        signal_id="sig-invalid-second",
        tp_atr_multiple=-50.0,
    )

    prior_trades, prior_equity = BacktestEngine(config).run(
        bars.iloc[:3], [first_signal]
    )
    assert len(prior_trades) == 1
    assert prior_trades[0].exit_reason == TradeExitReason.TAKE_PROFIT.value
    assert prior_equity[-1].cash > config.initial_capital

    with pytest.raises(
        BacktestValidationError, match="Take Profit SPOT LONG inválido"
    ) as error:
        BacktestEngine(config).run(bars, [first_signal, invalid_signal])

    traceback = error.value.__traceback__
    while traceback is not None and traceback.tb_frame.f_code.co_name != "run":
        traceback = traceback.tb_next
    assert traceback is not None
    state = traceback.tb_frame.f_locals
    assert state["bar_ts"] == bars.iloc[3]["timestamp"]
    assert state["current_cash"] == prior_equity[-1].cash
    assert state["active_position"] is None
    assert state["closed_trades"] == prior_trades
    assert state["fee_entry"] == prior_trades[0].fee_entry
    assert state["fee_exit"] == prior_trades[0].fee_exit
    assert state["size_units"] == prior_trades[0].size_units


@pytest.mark.parametrize(
    ("exit_bar", "exit_reason", "exit_price", "mfe_pct", "mae_pct"),
    [
        ((95.0, 105.0, 94.0, 101.0), TradeExitReason.STOP_LOSS.value, 95.0, 1.0, 5.0),
        (
            (106.0, 107.0, 97.0, 100.0),
            TradeExitReason.TAKE_PROFIT.value,
            104.0,
            6.0,
            1.0,
        ),
    ],
)
def test_d1b1_opening_exit_uses_open_not_later_extremes(
    exit_bar,
    exit_reason,
    exit_price,
    mfe_pct,
    mae_pct,
):
    bars = _make_c1_bars(exit_bar)
    config = _c1_config(taker_fee_pct=0.001)
    trades, equity = BacktestEngine(config).run(bars, [make_test_signal(atr=2.0)])

    assert len(trades) == 1
    trade = trades[0]
    assert trade.entry_timestamp == bars.iloc[1]["timestamp"]
    assert trade.exit_timestamp == bars.iloc[2]["timestamp"]
    assert trade.exit_reason == exit_reason
    assert (
        trade.execution_trace_status == ExecutionTraceStatus.OPENING_LEVEL_REVIEW.value
    )
    assert trade.entry_price == pytest.approx(100.0)
    assert trade.exit_price == pytest.approx(exit_price)
    assert trade.mfe_pct == pytest.approx(mfe_pct)
    assert trade.mae_pct == pytest.approx(mae_pct)
    assert trade.fee_entry == pytest.approx(1.0)
    assert trade.fee_exit == pytest.approx(trade.notional_exit * config.taker_fee_pct)
    assert trade.net_pnl == pytest.approx(
        trade.gross_pnl - trade.fee_entry - trade.fee_exit
    )
    assert trade.r_multiple == pytest.approx(
        trade.gross_pnl / trade.initial_risk_amount
    )
    assert trade.net_r_multiple == pytest.approx(
        trade.net_pnl / trade.initial_risk_amount
    )
    assert (
        equity[-1].cash
        == equity[-1].equity
        == pytest.approx(config.initial_capital + trade.net_pnl)
    )


def test_d1b1_opening_gap_preserves_previous_candle_excursions():
    bars = _make_c1_bars((100.0, 103.0, 98.5, 101.0))
    bars.loc[3] = [
        bars.iloc[2]["timestamp"] + pd.Timedelta(hours=1),
        95.0,
        110.0,
        94.0,
        100.0,
        1000.0,
    ]

    trades, _ = BacktestEngine(_c1_config()).run(bars, [make_test_signal(atr=2.0)])

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_timestamp == bars.iloc[3]["timestamp"]
    assert trade.exit_price == pytest.approx(95.0)
    assert trade.mfe_pct == pytest.approx(3.0)  # High=103 from prior surviving bar.
    assert trade.mae_pct == pytest.approx(5.0)  # Open=95, not later Low=94.


def test_d1b1_stop_gap_slippage_does_not_turn_fill_into_market_excursion():
    bars = _make_c1_bars((95.0, 110.0, 94.0, 101.0))
    bars.loc[1, ["high", "low", "close"]] = [102.0, 100.0, 101.0]
    config = _c1_config(slippage_pct=0.01, taker_fee_pct=0.001)

    trades, equity = BacktestEngine(config).run(bars, [make_test_signal(atr=2.0)])

    trade = trades[0]
    assert trade.entry_price == pytest.approx(101.0)
    assert trade.sl_price == pytest.approx(99.0)
    assert trade.exit_price == pytest.approx(94.05)  # Modelled fill below Open=95.
    assert trade.mfe_pct == pytest.approx((102.0 - 101.0) / 101.0 * 100.0)
    assert trade.mae_pct == pytest.approx((101.0 - 95.0) / 101.0 * 100.0)
    assert (
        equity[-1].cash
        == equity[-1].equity
        == pytest.approx(config.initial_capital + trade.net_pnl)
    )


def test_d1b1_trailing_stop_gap_keeps_initial_risk_and_ignores_later_high():
    bars = _make_c1_bars((99.0, 110.0, 98.0, 100.0))
    bars.loc[1, ["high", "low", "close"]] = [103.0, 99.5, 102.0]
    config = _c1_config(enable_trailing_stop=True, trailing_stop_activation_r=1.0)

    trades, _ = BacktestEngine(config).run(bars, [make_test_signal(atr=2.0)])

    trade = trades[0]
    assert trade.exit_reason == TradeExitReason.STOP_LOSS.value
    assert trade.exit_price == pytest.approx(99.0)
    assert trade.sl_price == pytest.approx(100.0)
    assert trade.initial_stop_price == pytest.approx(98.0)
    assert trade.initial_risk_amount == pytest.approx(20.0)
    assert trade.r_multiple == pytest.approx(-0.5)
    assert trade.mfe_pct == pytest.approx(3.0)
    assert trade.mae_pct == pytest.approx(1.0)


def test_d1b1_surviving_bar_and_horizon_keep_full_ohlc_excursions(monkeypatch):
    bars = _make_c1_bars((100.0, 103.0, 98.5, 101.0))
    bars.loc[3] = [
        bars.iloc[2]["timestamp"] + pd.Timedelta(hours=1),
        100.0,
        102.0,
        99.0,
        101.0,
        1000.0,
    ]
    observed_ranges = []
    original_update = Position.update_excursions

    def record_range(self, high, low):
        observed_ranges.append((high, low))
        return original_update(self, high, low)

    monkeypatch.setattr(Position, "update_excursions", record_range)
    trades, _ = BacktestEngine(_c1_config()).run(bars, [make_test_signal(atr=2.0)])

    assert observed_ranges == [(101.0, 99.0), (103.0, 98.5), (102.0, 99.0)]
    trade = trades[0]
    assert trade.exit_reason == TradeExitReason.TIME_HORIZON.value
    assert trade.exit_timestamp == bars.iloc[3]["timestamp"]
    assert trade.exit_price == pytest.approx(101.0)
    assert trade.mfe_pct == pytest.approx(3.0)
    assert trade.mae_pct == pytest.approx(1.5)


def test_d1b1_intrabar_conflict_retains_existing_sl_first_policy():
    bars = _make_c1_bars((100.0, 105.0, 95.0, 101.0))

    trades, _ = BacktestEngine(_c1_config()).run(bars, [make_test_signal(atr=2.0)])

    trade = trades[0]
    assert trade.exit_reason == TradeExitReason.STOP_LOSS.value
    assert trade.exit_price == pytest.approx(98.0)
    assert trade.execution_trace_status == ExecutionTraceStatus.INTRABAR_SL_FIRST.value
    assert trade.mfe_pct == pytest.approx(5.0)
    assert trade.mae_pct == pytest.approx(5.0)


@pytest.mark.parametrize("opening_price", [95.0, 106.0])
def test_d1b1_opening_exit_updates_excursions_once_with_open_only(
    monkeypatch,
    opening_price,
):
    bars = _make_c1_bars((opening_price, 107.0, 94.0, 100.0))
    observed_ranges = []
    original_update = Position.update_excursions

    def record_range(self, high, low):
        observed_ranges.append((high, low))
        return original_update(self, high, low)

    monkeypatch.setattr(Position, "update_excursions", record_range)
    trades, _ = BacktestEngine(_c1_config()).run(bars, [make_test_signal(atr=2.0)])

    assert len(trades) == 1
    assert trades[0].exit_timestamp == bars.iloc[2]["timestamp"]
    assert observed_ranges == [(101.0, 99.0), (opening_price, opening_price)]
