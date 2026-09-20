from __future__ import annotations

import pandas as pd
import pytest

from src.backtest_engine import BacktestEngine
from src.backtest_models import BacktestConfig, SignalEvent, TradeExitReason


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
