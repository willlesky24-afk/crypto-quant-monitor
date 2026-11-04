from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.backtest_engine import BacktestEngine
from src.backtest_metrics import BacktestMetricsCalculator
from src.backtest_models import (
    BacktestConfig,
    BacktestValidationError,
    SignalEvent,
    TradeExitReason,
)
from src.backtest_runner import BacktestRunner
from src.dataset_manager import HistoricalDatasetManager
from src.parquet_store import ParquetStore


def test_full_multi_year_backtest_pipeline_e2e(tmp_path: Path, make_synthetic_candles):
    """End-to-end multi-year backtest integration test:

    1. Generate multi-year synthetic OHLCV dataset spanning 2023, 2024, and 2025.
    2. Store columnar partitions in ParquetStore with manifest tracking.
    3. Load via HistoricalDatasetManager.
    4. Execute backtest simulation through BacktestRunner.
    5. Validate causal signal generation, entry execution on T+1, MFE/MAE excursion tracking,
       drawdown calculations, and JSON serialization.
    """
    # 1. Multi-year dataset (600 closed hourly candles across 2023, 2024, 2025)
    candles_2023 = make_synthetic_candles(
        start="2023-11-15", periods=200, freq="1h", base_price=30000.0
    )
    candles_2024 = make_synthetic_candles(
        start="2024-01-01", periods=200, freq="1h", base_price=42000.0
    )
    candles_2025 = make_synthetic_candles(
        start="2025-01-01", periods=200, freq="1h", base_price=60000.0
    )
    full_df = pd.concat([candles_2023, candles_2024, candles_2025], ignore_index=True)

    # 2. Persist in Parquet store
    store = ParquetStore(base_dir=tmp_path / "historical_bt_e2e")
    store.write_dataset(full_df, "BTCUSDT", "1h")

    # Verify Parquet partitioning on disk
    dataset_dir = store.get_dataset_dir("BTCUSDT", "1h")
    parquet_files = sorted([f.name for f in dataset_dir.glob("*.parquet")])
    assert "2023.parquet" in parquet_files
    assert "2024.parquet" in parquet_files
    assert "2025.parquet" in parquet_files

    # 3. Initialize HistoricalDatasetManager and BacktestRunner
    manager = HistoricalDatasetManager(store=store)
    cfg = BacktestConfig(
        initial_capital=10_000.0,
        position_size_pct=1.0,
        slippage_pct=0.0005,  # 0.05%
        taker_fee_pct=0.0005,  # 0.05%
        min_quant_score=40.0,  # Strategy filter
        require_favorable_decision=False,
        tp_atr_multiple=2.5,
        sl_atr_multiple=1.2,
        max_holding_bars=24,
    )
    runner = BacktestRunner(config=cfg, dataset_manager=manager)

    # 4. Execute full backtest
    report = runner.run_backtest(
        symbol="BTCUSDT",
        interval="1h",
        warmup_bars=200,
    )

    # 5. Core Pipeline Validations
    assert report.symbol == "BTCUSDT"
    assert report.timeframe == "1h"
    assert report.total_candles == 600
    assert len(report.equity_curve) == 600

    # Verify initial equity point
    assert report.equity_curve[0].equity == 10_000.0
    assert report.equity_curve[0].drawdown_pct == 0.0
    expected_dd, expected_max_pct, expected_max_usd, expected_duration = (
        BacktestMetricsCalculator.calculate_drawdown_series(
            [point.equity for point in report.equity_curve],
            initial_equity=cfg.initial_capital,
        )
    )
    assert [point.drawdown_pct for point in report.equity_curve] == pytest.approx(
        expected_dd
    )
    assert report.max_drawdown_pct == round(expected_max_pct, 2)
    assert report.max_drawdown_usd == round(expected_max_usd, 2)
    assert report.max_drawdown_duration_bars == expected_duration

    # Verify trades and strict execution rules
    assert report.total_trades > 0
    assert report.total_trades == (
        report.winning_trades
        + report.losing_trades
        + (report.total_trades - report.winning_trades - report.losing_trades)
    )

    for trade in report.trades:
        # Strict T -> T+1 entry
        assert trade.entry_timestamp > trade.signal_timestamp
        assert trade.exit_timestamp >= trade.entry_timestamp
        assert trade.bars_held >= 1
        assert trade.fee_entry > 0
        assert trade.fee_exit > 0
        assert trade.net_pnl == pytest.approx(
            trade.gross_pnl - trade.fee_entry - trade.fee_exit
        )
        assert trade.r_multiple == pytest.approx(
            trade.gross_pnl / trade.initial_risk_amount
        )
        assert trade.net_r_multiple == pytest.approx(
            trade.net_pnl / trade.initial_risk_amount
        )
        assert trade.mfe_pct >= 0.0
        assert trade.mae_pct >= 0.0
        assert trade.execution_trace_status is not None
        assert trade.execution_policy_version == "SPOT_LONG_C1_OPEN_PRIORITY_TP_LIMIT"

    assert report.r_coverage_status == "COMPLETE"
    assert report.r_verified_trades == report.total_trades
    assert report.r_excluded_trades == 0
    assert report.gross_expectancy_r == pytest.approx(
        sum(t.gross_pnl / t.initial_risk_amount for t in report.trades)
        / report.total_trades
    )
    assert report.net_expectancy_r == pytest.approx(
        sum(t.net_pnl / t.initial_risk_amount for t in report.trades)
        / report.total_trades
    )
    assert report.total_net_pnl == pytest.approx(
        sum(t.net_pnl for t in report.trades), abs=0.01
    )
    assert report.data_provenance.status == "UNKNOWN"
    assert report.sharpe_ratio is None

    # 6. JSON Serialization Roundtrip
    report_dict = report.to_dict()
    serialized_json = json.dumps(report_dict, indent=2)
    deserialized = json.loads(serialized_json)

    assert deserialized["symbol"] == "BTCUSDT"
    assert deserialized["total_candles"] == 600
    assert deserialized["config"]["initial_capital"] == 10_000.0
    assert len(deserialized["trades"]) == report.total_trades
    assert all(
        row["execution_trace_status"] is not None for row in deserialized["trades"]
    )
    assert all(
        row["execution_policy_version"] == "SPOT_LONG_C1_OPEN_PRIORITY_TP_LIMIT"
        for row in deserialized["trades"]
    )
    assert len(deserialized["equity_curve"]) == 600
    assert deserialized["r_coverage_status"] == "COMPLETE"
    assert deserialized["gross_expectancy_r"] == pytest.approx(
        report.gross_expectancy_r
    )
    assert deserialized["net_expectancy_r"] == pytest.approx(report.net_expectancy_r)


def test_backtest_pipeline_determinism_and_no_lookahead_bias(
    tmp_path: Path, make_synthetic_candles
):
    """Verifies that:

    1. Two successive runs over the exact same historical dataset produce bit-identical results.
    2. Causal integrity: Truncating the dataset at any given bar T yields the exact same signal
       and analysis as was observed in the full multi-year run at bar T (absolute zero look-ahead bias).
    """
    store = ParquetStore(base_dir=tmp_path / "historical_determinism")
    df = make_synthetic_candles(
        start="2024-01-01", periods=300, freq="1h", base_price=50000.0
    )
    store.write_dataset(df, "ETHUSDT", "1h")

    manager = HistoricalDatasetManager(store=store)
    cfg = BacktestConfig(
        initial_capital=20_000.0,
        min_quant_score=40.0,
        require_favorable_decision=False,
    )
    runner = BacktestRunner(config=cfg, dataset_manager=manager)

    # Run 1 & Run 2
    report1 = runner.run_backtest("ETHUSDT", "1h", warmup_bars=200)
    report2 = runner.run_backtest("ETHUSDT", "1h", warmup_bars=200)

    assert report1.to_dict() == report2.to_dict()
    assert report1.total_trades == report2.total_trades
    assert report1.total_net_pnl == report2.total_net_pnl
    assert report1.win_rate_pct == report2.win_rate_pct
    assert report1.max_drawdown_pct == report2.max_drawdown_pct

    # Causal / Look-ahead Bias Test at bar 250
    test_bar_idx = 250
    full_enriched = runner.indicators.calculate_all(df.copy())
    full_sub = full_enriched.iloc[: test_bar_idx + 1]
    full_profile = runner.volume_profile.calculate(full_sub)
    full_analysis = runner.market_engine.analyze(full_sub, full_profile)
    full_signal = runner.signal_engine.evaluate(full_analysis, full_profile)
    full_risk = runner.risk_engine.evaluate(full_analysis, full_profile)
    full_score = runner.quant_score.calculate(full_analysis, full_signal, full_risk)

    # Now simulate an observer only having data up to bar 250
    isolated_df = df.iloc[: test_bar_idx + 1].copy()
    isolated_enriched = runner.indicators.calculate_all(isolated_df)
    isolated_profile = runner.volume_profile.calculate(isolated_enriched)
    isolated_analysis = runner.market_engine.analyze(
        isolated_enriched, isolated_profile
    )
    isolated_signal = runner.signal_engine.evaluate(isolated_analysis, isolated_profile)
    isolated_risk = runner.risk_engine.evaluate(isolated_analysis, isolated_profile)
    isolated_score = runner.quant_score.calculate(
        isolated_analysis, isolated_signal, isolated_risk
    )

    # Assert exact match
    assert full_analysis["score"] == isolated_analysis["score"]
    assert full_analysis["trend"] == isolated_analysis["trend"]
    assert full_signal["score"] == isolated_signal["score"]
    assert full_signal["state"] == isolated_signal["state"]
    assert full_score["score"] == isolated_score["score"]
    assert full_risk["level"] == isolated_risk["level"]


def test_backtest_pipeline_date_slicing(tmp_path: Path, make_synthetic_candles):
    """Verifies that time range filtering loads only the requested slice and runs properly."""
    store = ParquetStore(base_dir=tmp_path / "historical_slice")
    df = make_synthetic_candles(start="2024-01-01", periods=500, freq="1h")
    store.write_dataset(df, "SOLUSDT", "1h")

    manager = HistoricalDatasetManager(store=store)
    runner = BacktestRunner(dataset_manager=manager)

    # Slice 250 candles from 2024-01-01 to 2024-01-11
    sliced_report = runner.run_backtest(
        symbol="SOLUSDT",
        interval="1h",
        start_time="2024-01-01 00:00:00",
        end_time="2024-01-11 09:00:00",
        warmup_bars=200,
    )

    assert sliced_report.total_candles == 250
    assert sliced_report.symbol == "SOLUSDT"
    assert len(sliced_report.equity_curve) == 250


def test_ordered_direct_and_stored_candles_keep_the_same_execution(
    tmp_path: Path, make_synthetic_candles
):
    candles = make_synthetic_candles(periods=250, freq="1h", base_price=100.0)
    store = ParquetStore(base_dir=tmp_path / "ordered_parity")
    store.write_dataset(candles, "BTCUSDT", "1h")
    manager = HistoricalDatasetManager(store=store)
    cfg = BacktestConfig(min_quant_score=40.0)
    runner = BacktestRunner(config=cfg, dataset_manager=manager)

    direct = runner.run_backtest("BTCUSDT", "1h", df=candles, warmup_bars=200)
    stored = runner.run_backtest("BTCUSDT", "1h", warmup_bars=200)

    assert direct.total_candles == stored.total_candles == 250
    assert direct.trades == stored.trades
    assert direct.equity_curve == stored.equity_curve
    assert direct.total_net_pnl == pytest.approx(stored.total_net_pnl)
    assert direct.data_provenance.status == "UNKNOWN"
    assert stored.data_provenance.status == "UNKNOWN"


def test_400_candle_prefix_keeps_indicators_signals_and_initial_risk_at_800(
    tmp_path: Path, make_synthetic_candles, monkeypatch
):
    full = make_synthetic_candles(periods=800, base_price=100.0)
    prefix = full.iloc[:400].copy()
    store = ParquetStore(base_dir=tmp_path / "warmup_extension")
    runner = BacktestRunner(
        config=BacktestConfig(min_quant_score=0.0),
        dataset_manager=HistoricalDatasetManager(store=store),
    )
    captured = []
    execute = runner.engine.run

    def capture_execution(df, signals):
        trades, equity = execute(df, signals)
        captured.append((df.copy(), list(signals), trades))
        return trades, equity

    monkeypatch.setattr(runner.engine, "run", capture_execution)
    runner.run_backtest("BTCUSDT", "1h", df=prefix)
    runner.run_backtest("BTCUSDT", "1h", df=full)

    short_df, short_signals, short_trades = captured[0]
    long_df, long_signals, long_trades = captured[1]
    assert len(short_signals) == 201
    assert len(long_signals) == 601
    assert short_signals[0].candle_timestamp == prefix.iloc[199]["timestamp"]
    assert [signal.to_dict() for signal in short_signals] == [
        signal.to_dict() for signal in long_signals[: len(short_signals)]
    ]
    columns = ["rsi", "atr", "volume_average", "ema_50", "ema_200"]
    pd.testing.assert_frame_equal(
        short_df[columns], long_df.iloc[:400][columns].reset_index(drop=True)
    )
    previous_risk = {trade.signal_timestamp: trade for trade in short_trades}
    extended_risk = {trade.signal_timestamp: trade for trade in long_trades}
    shared = previous_risk.keys() & extended_risk.keys()
    assert shared
    for timestamp in shared:
        before, after = previous_risk[timestamp], extended_risk[timestamp]
        assert before.entry_price == pytest.approx(after.entry_price)
        assert before.initial_stop_price == pytest.approx(after.initial_stop_price)
        assert before.tp_price == pytest.approx(after.tp_price)
        assert before.initial_risk_amount == pytest.approx(after.initial_risk_amount)


def test_extending_horizon_can_change_only_forced_final_liquidation():
    timestamps = pd.date_range("2024-01-01", periods=800, freq="1h", tz="UTC")
    prices = [100.0] * 400 + [105.0] * 400
    candles = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": [1000.0] * 800,
        }
    )
    signal = SignalEvent(
        signal_id="warmup-end",
        symbol="BTCUSDT",
        timeframe="1h",
        candle_timestamp=timestamps[199],
        price_at_signal=100.0,
        signal_state="BULLISH",
        confidence=80.0,
        decision="FAVORABLE",
        quant_score=100.0,
        risk_level="BAJO",
        atr=2.0,
        poc=100.0,
        vah=101.0,
        val=99.0,
    )
    engine = BacktestEngine(
        BacktestConfig(
            taker_fee_pct=0.0,
            slippage_pct=0.0,
            max_holding_bars=1000,
            tp_atr_multiple=10.0,
        )
    )

    short_trades, _ = engine.run(candles.iloc[:400], [signal])
    long_trades, _ = engine.run(candles, [signal])

    assert len(short_trades) == len(long_trades) == 1
    before, after = short_trades[0], long_trades[0]
    assert before.entry_timestamp == after.entry_timestamp == timestamps[200]
    assert before.initial_stop_price == after.initial_stop_price
    assert before.exit_reason == after.exit_reason == TradeExitReason.TIME_HORIZON.value
    assert before.exit_timestamp == timestamps[399]
    assert after.exit_timestamp == timestamps[799]
    assert before.net_pnl < after.net_pnl


def test_causal_trailing_execution_reconciles_report_metrics_and_equity():
    timestamps = pd.date_range("2024-01-01", periods=4, freq="1h", tz="UTC")
    candles = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0, 100.0, 100.0, 101.0],
            "high": [101.0, 101.0, 103.0, 101.5],
            "low": [99.0, 99.0, 99.0, 99.0],
            "close": [100.0, 100.0, 101.0, 100.0],
        }
    )
    signal = SignalEvent(
        signal_id="trailing-causal",
        symbol="BTCUSDT",
        timeframe="1h",
        candle_timestamp=timestamps[0],
        price_at_signal=100.0,
        signal_state="BULLISH",
        confidence=80.0,
        decision="FAVORABLE",
        quant_score=100.0,
        risk_level="BAJO",
        atr=2.0,
        poc=100.0,
        vah=101.0,
        val=99.0,
    )
    config = BacktestConfig(
        initial_capital=1000.0,
        taker_fee_pct=0.001,
        slippage_pct=0.0,
        tp_atr_multiple=5.0,
        sl_atr_multiple=1.0,
        enable_trailing_stop=True,
        trailing_stop_activation_r=1.0,
    )

    trades, equity = BacktestEngine(config).run(candles, [signal])
    metrics = BacktestMetricsCalculator.calculate_metrics(
        trades, equity, initial_capital=config.initial_capital
    )

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_timestamp == timestamps[3]
    assert trade.exit_reason == TradeExitReason.STOP_LOSS.value
    assert trade.sl_price == trade.exit_price == pytest.approx(100.0)
    assert trade.initial_stop_price == pytest.approx(98.0)
    assert trade.r_multiple == pytest.approx(0.0)
    assert trade.net_r_multiple == pytest.approx(
        trade.net_pnl / trade.initial_risk_amount
    )
    assert equity[-1].cash == equity[-1].equity == pytest.approx(1000.0 + trade.net_pnl)
    assert metrics["total_net_pnl"] == pytest.approx(trade.net_pnl, abs=0.01)
    assert metrics["gross_expectancy_r"] == pytest.approx(trade.r_multiple)
    assert metrics["net_expectancy_r"] == pytest.approx(trade.net_r_multiple)
    assert metrics["sharpe_ratio"] is None


def test_runner_propagates_invalid_take_profit_instead_of_returning_a_report(
    tmp_path: Path,
    make_synthetic_candles,
):
    candles = make_synthetic_candles(
        start="2024-01-01", periods=205, freq="1h", base_price=100.0
    )
    config = BacktestConfig(
        initial_capital=1000.0,
        min_quant_score=0.0,
        tp_atr_multiple=-1e6,
        sl_atr_multiple=1.0,
    )
    runner = BacktestRunner(
        config=config,
        dataset_manager=HistoricalDatasetManager(base_dir=tmp_path / "d1a_historical"),
    )

    with pytest.raises(BacktestValidationError, match="Take Profit SPOT LONG inválido"):
        runner.run_backtest(
            symbol="BTCUSDT", interval="1h", df=candles, warmup_bars=200
        )


def test_opening_gap_excursions_flow_to_aggregate_metrics_without_changing_pnl():
    timestamps = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
    candles = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0, 100.0, 95.0],
            "high": [101.0, 101.0, 105.0],
            "low": [99.0, 99.0, 94.0],
            "close": [100.0, 100.0, 101.0],
        }
    )
    signal = SignalEvent(
        signal_id="opening-gap-excursions",
        symbol="BTCUSDT",
        timeframe="1h",
        candle_timestamp=timestamps[0],
        price_at_signal=100.0,
        signal_state="BULLISH",
        confidence=80.0,
        decision="FAVORABLE",
        quant_score=100.0,
        risk_level="BAJO",
        atr=2.0,
        poc=100.0,
        vah=101.0,
        val=99.0,
    )
    config = BacktestConfig(
        initial_capital=1000.0, taker_fee_pct=0.001, slippage_pct=0.0
    )

    trades, equity = BacktestEngine(config).run(candles, [signal])
    metrics = BacktestMetricsCalculator.calculate_metrics(
        trades, equity, initial_capital=config.initial_capital
    )

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_reason == TradeExitReason.STOP_LOSS.value
    assert trade.exit_price == pytest.approx(95.0)
    assert trade.mfe_pct == pytest.approx(1.0)
    assert trade.mae_pct == pytest.approx(5.0)
    assert metrics["avg_mfe_pct"] == pytest.approx(1.0)
    assert metrics["avg_mae_pct"] == pytest.approx(5.0)
    assert trade.net_pnl == pytest.approx(
        trade.gross_pnl - trade.fee_entry - trade.fee_exit
    )
    assert trade.r_multiple == pytest.approx(
        trade.gross_pnl / trade.initial_risk_amount
    )
    assert trade.net_r_multiple == pytest.approx(
        trade.net_pnl / trade.initial_risk_amount
    )
    assert metrics["total_net_pnl"] == pytest.approx(round(trade.net_pnl, 2))
    assert (
        equity[-1].cash
        == equity[-1].equity
        == pytest.approx(config.initial_capital + trade.net_pnl)
    )
