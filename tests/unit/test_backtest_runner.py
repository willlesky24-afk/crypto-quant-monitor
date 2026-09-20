from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.backtest_models import BacktestConfig
from src.backtest_runner import BacktestRunner
from src.dataset_manager import HistoricalDatasetManager
from src.parquet_store import ParquetStore


def test_backtest_runner_empty_and_insufficient_warmup(tmp_path: Path):
    store = ParquetStore(base_dir=tmp_path / "historical")
    manager = HistoricalDatasetManager(store=store)
    runner = BacktestRunner(dataset_manager=manager)

    # Empty
    rep_empty = runner.run_backtest("BTCUSDT", "1h", df=pd.DataFrame())
    assert rep_empty.total_candles == 0
    assert rep_empty.total_trades == 0
    assert rep_empty.win_rate_pct == 0.0

    # Insufficient warmup (< 200 bars)
    df_short = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=50, freq="1h", tz="UTC"),
            "open": [100.0] * 50,
            "high": [101.0] * 50,
            "low": [99.0] * 50,
            "close": [100.0] * 50,
            "volume": [1000.0] * 50,
        }
    )
    rep_short = runner.run_backtest("BTCUSDT", "1h", df=df_short, warmup_bars=200)
    assert rep_short.total_candles == 50
    assert rep_short.total_trades == 0


def test_backtest_runner_with_synthetic_dataset(make_synthetic_candles):
    # Generate 300 synthetic bars (enough for 200 warm-up + 100 active bars)
    df = make_synthetic_candles(start="2024-01-01", periods=300, freq="1h", base_price=100.0)

    cfg = BacktestConfig(
        initial_capital=10_000.0,
        position_size_pct=1.0,
        min_quant_score=40.0,  # Lower threshold to capture synthetic triggers
        require_favorable_decision=False,
        tp_atr_multiple=2.0,
        sl_atr_multiple=1.0,
    )
    runner = BacktestRunner(config=cfg)

    report = runner.run_backtest("BTCUSDT", "1h", df=df, warmup_bars=200)

    assert report.total_candles == 300
    assert report.symbol == "BTCUSDT"
    assert report.timeframe == "1h"
    assert report.config.initial_capital == 10_000.0
    assert len(report.equity_curve) > 0
    assert report.to_dict()["symbol"] == "BTCUSDT"


def test_backtest_runner_loads_from_dataset_manager(tmp_path: Path, make_synthetic_candles):
    store = ParquetStore(base_dir=tmp_path / "historical")
    df = make_synthetic_candles(start="2024-01-01", periods=250, freq="1h")
    store.write_dataset(df, "ETHUSDT", "1h")

    manager = HistoricalDatasetManager(store=store)
    runner = BacktestRunner(dataset_manager=manager)

    report = runner.run_backtest("ETHUSDT", "1h", warmup_bars=200)

    assert report.total_candles == 250
    assert report.symbol == "ETHUSDT"
    assert report.timeframe == "1h"
    assert len(report.equity_curve) == 250
