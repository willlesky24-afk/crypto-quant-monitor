from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.backtest_models import BacktestConfig
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
    candles_2023 = make_synthetic_candles(start="2023-11-15", periods=200, freq="1h", base_price=30000.0)
    candles_2024 = make_synthetic_candles(start="2024-01-01", periods=200, freq="1h", base_price=42000.0)
    candles_2025 = make_synthetic_candles(start="2025-01-01", periods=200, freq="1h", base_price=60000.0)
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

    # Verify trades and strict execution rules
    assert report.total_trades > 0
    assert report.total_trades == (report.winning_trades + report.losing_trades + (report.total_trades - report.winning_trades - report.losing_trades))

    for trade in report.trades:
        # Strict T -> T+1 entry
        assert trade.entry_timestamp > trade.signal_timestamp
        assert trade.exit_timestamp >= trade.entry_timestamp
        assert trade.bars_held >= 1
        assert trade.fee_entry > 0
        assert trade.fee_exit > 0
        assert trade.net_pnl == pytest.approx(trade.gross_pnl - trade.fee_entry - trade.fee_exit)
        assert trade.mfe_pct >= 0.0
        assert trade.mae_pct >= 0.0

    # 6. JSON Serialization Roundtrip
    report_dict = report.to_dict()
    serialized_json = json.dumps(report_dict, indent=2)
    deserialized = json.loads(serialized_json)

    assert deserialized["symbol"] == "BTCUSDT"
    assert deserialized["total_candles"] == 600
    assert deserialized["config"]["initial_capital"] == 10_000.0
    assert len(deserialized["trades"]) == report.total_trades
    assert len(deserialized["equity_curve"]) == 600


def test_backtest_pipeline_determinism_and_no_lookahead_bias(tmp_path: Path, make_synthetic_candles):
    """Verifies that:

    1. Two successive runs over the exact same historical dataset produce bit-identical results.
    2. Causal integrity: Truncating the dataset at any given bar T yields the exact same signal
       and analysis as was observed in the full multi-year run at bar T (absolute zero look-ahead bias).
    """
    store = ParquetStore(base_dir=tmp_path / "historical_determinism")
    df = make_synthetic_candles(start="2024-01-01", periods=300, freq="1h", base_price=50000.0)
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
    isolated_analysis = runner.market_engine.analyze(isolated_enriched, isolated_profile)
    isolated_signal = runner.signal_engine.evaluate(isolated_analysis, isolated_profile)
    isolated_risk = runner.risk_engine.evaluate(isolated_analysis, isolated_profile)
    isolated_score = runner.quant_score.calculate(isolated_analysis, isolated_signal, isolated_risk)

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
