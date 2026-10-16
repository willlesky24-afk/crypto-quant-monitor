from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

from src.backtest_engine import BacktestEngine
from src.backtest_models import (
    BacktestConfig,
    BacktestValidationError,
    SignalEvent,
    TradeExitReason,
)


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


def test_backtest_engine_entry_on_next_bar_with_slippage_and_fee(make_synthetic_candles):
    # 5 bars:
    # bar 0: 100.0 (signal emitted at close)
    # bar 1: open 100.0 -> entry price = 100.0 * 1.001 (0.1% slippage)
    df = make_synthetic_candles(start="2024-01-01 00:00:00", periods=10, freq="1h", base_price=100.0)

    cfg = BacktestConfig(
        initial_capital=10_000.0,
        slippage_pct=0.001,  # 0.1%
        taker_fee_pct=0.0005,  # 0.05%
        tp_atr_multiple=10.0,  # Far away so it doesn't trigger TP immediately
        sl_atr_multiple=10.0,
        max_holding_bars=3,
    )
    engine = BacktestEngine(config=cfg)

    sig = make_test_signal(timestamp="2024-01-01 00:00:00", price=float(df.iloc[0]["close"]))
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
    sig1 = make_test_signal("2024-01-01 00:00:00", quant_score=45.0, decision="FAVORABLE")
    # Sig 2: unfavorable decision
    sig2 = make_test_signal("2024-01-01 01:00:00", quant_score=80.0, decision="WAIT_CONFIRMATION")
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

    engine = BacktestEngine(config=BacktestConfig(min_quant_score=60.0, require_favorable_decision=True, direction="LONG"))
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


def test_backtest_engine_zero_initial_risk_handled():
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
    trades, eq = engine.run(df, signals=[sig])

    assert len(trades) == 1
    assert trades[0].r_multiple == 0.0


def _flat_spot_bars(exit_price: float = 100.0, count: int = 3) -> pd.DataFrame:
    prices = [100.0] * (count - 1) + [exit_price]
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=count, freq="1h", tz="UTC"),
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": [1000.0] * count,
        }
    )


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
    assert equity[1].cash == pytest.approx(capital - allocation)
    assert equity[1].equity == pytest.approx(capital - allocation + units * 100.0)
    assert equity[-1].cash == pytest.approx(
        capital - allocation + units * exit_price - fee_exit
    )
    assert equity[-1].equity == pytest.approx(equity[-1].cash)
    assert equity[-1].equity - capital == pytest.approx(trade.net_pnl, abs=1e-8)
    assert all(point.cash >= 0 for point in equity)


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



