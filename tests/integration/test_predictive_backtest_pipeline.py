from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.backtest_models import BacktestConfig, TradeDirection
from src.backtest_runner import BacktestRunner
from src.dataset_manager import HistoricalDatasetManager
from src.parquet_store import ParquetStore
from src.predictive_engine import PredictiveEngine
from src.regime_classifier import RegimeClassifier
from src.strategy_optimizer import StrategyOptimizer


def test_predictive_backtest_pipeline_e2e(tmp_path: Path, make_synthetic_candles):
    """Full End-to-End integration test for Fase 4 Predictive Backtest Pipeline.

    Pipeline validated:
    Historical Data (2023-2025)
            ↓
       ParquetStore
            ↓
    HistoricalDatasetManager
            ↓
       RegimeClassifier
            ↓
       PredictiveEngine
            ↓
       StrategyOptimizer
            ↓
    Enhanced DecisionEngine
            ↓
       BacktestRunner
            ↓
       BacktestReport
    """
    # -------------------------------------------------------------------------
    # 1. Multi-Year Dataset (2023, 2024, 2025)
    # -------------------------------------------------------------------------
    candles_2023 = make_synthetic_candles(start="2023-06-01", periods=150, freq="1h", base_price=28000.0)
    candles_2024 = make_synthetic_candles(start="2024-01-01", periods=150, freq="1h", base_price=42000.0)
    candles_2025 = make_synthetic_candles(start="2025-01-01", periods=150, freq="1h", base_price=65000.0)
    full_df = pd.concat([candles_2023, candles_2024, candles_2025], ignore_index=True)

    # Persist in Parquet store
    store = ParquetStore(base_dir=tmp_path / "predictive_bt_e2e")
    store.write_dataset(full_df, "BTCUSDT", "1h")

    # Verify Parquet partitioning
    dataset_dir = store.get_dataset_dir("BTCUSDT", "1h")
    parquet_files = sorted([f.name for f in dataset_dir.glob("*.parquet")])
    assert "2023.parquet" in parquet_files
    assert "2024.parquet" in parquet_files
    assert "2025.parquet" in parquet_files

    # -------------------------------------------------------------------------
    # 2. Historical Calibration with StrategyOptimizer (Walk-Forward Split)
    # -------------------------------------------------------------------------
    manager = HistoricalDatasetManager(store=store)
    regime_classifier = RegimeClassifier()
    predictive_engine = PredictiveEngine()
    optimizer = StrategyOptimizer(train_end="2025-01-01 00:00:00+00:00")

    # Run initial baseline run on TRAIN period to seed StrategyOptimizer
    raw_train_df = manager.load_dataset("BTCUSDT", "1h", end_time="2024-12-31 23:59:59+00:00")
    baseline_cfg = BacktestConfig(
        initial_capital=10_000.0,
        position_size_pct=1.0,
        min_quant_score=40.0,
        require_favorable_decision=False,
        direction=TradeDirection.BOTH.value,
    )
    baseline_runner = BacktestRunner(config=baseline_cfg, dataset_manager=manager)
    train_report = baseline_runner.run_backtest(
        symbol="BTCUSDT",
        interval="1h",
        warmup_bars=100,
        df=raw_train_df,
    )

    # Calibrate parameters by regime using MFE/MAE
    calibrated_params = optimizer.optimize_from_report(
        train_report,
        candles=raw_train_df,
        train_end=pd.Timestamp("2025-01-01 00:00:00+00:00"),
    )
    assert isinstance(calibrated_params, dict)
    assert len(calibrated_params) > 0

    # -------------------------------------------------------------------------
    # 3. Execution: Legacy Mode vs. Predictive-Enhanced Mode
    # -------------------------------------------------------------------------
    runner = BacktestRunner(
        config=baseline_cfg,
        dataset_manager=manager,
        regime_classifier=regime_classifier,
        predictive_engine=predictive_engine,
        strategy_optimizer=optimizer,
    )

    # Run Legacy Mode (v1.8 bit-for-bit behavior)
    legacy_report = runner.run_backtest(
        symbol="BTCUSDT",
        interval="1h",
        warmup_bars=100,
        predictive_mode=False,
    )

    # Run Predictive-Enhanced Mode
    enhanced_report = runner.run_backtest(
        symbol="BTCUSDT",
        interval="1h",
        warmup_bars=100,
        predictive_mode=True,
        calibrated_params=calibrated_params,
    )

    # -------------------------------------------------------------------------
    # 4. Descriptive Comparison Validations
    # -------------------------------------------------------------------------
    assert legacy_report.total_candles == 450
    assert enhanced_report.total_candles == 450

    # Collect descriptive metrics
    metrics_comparison = {
        "legacy": {
            "total_trades": legacy_report.total_trades,
            "win_rate_pct": legacy_report.win_rate_pct,
            "profit_factor": legacy_report.profit_factor,
            "expectancy": legacy_report.expectancy,
            "total_net_pnl": legacy_report.total_net_pnl,
            "max_drawdown_pct": legacy_report.max_drawdown_pct,
            "long_trades": sum(1 for t in legacy_report.trades if t.side == "LONG"),
            "short_trades": sum(1 for t in legacy_report.trades if t.side == "SHORT"),
        },
        "enhanced": {
            "total_trades": enhanced_report.total_trades,
            "win_rate_pct": enhanced_report.win_rate_pct,
            "profit_factor": enhanced_report.profit_factor,
            "expectancy": enhanced_report.expectancy,
            "total_net_pnl": enhanced_report.total_net_pnl,
            "max_drawdown_pct": enhanced_report.max_drawdown_pct,
            "long_trades": sum(1 for t in enhanced_report.trades if t.side == "LONG"),
            "short_trades": sum(1 for t in enhanced_report.trades if t.side == "SHORT"),
        },
    }

    # Verify both reports executed cleanly
    assert metrics_comparison["legacy"]["total_trades"] >= 0
    assert metrics_comparison["enhanced"]["total_trades"] >= 0

    # -------------------------------------------------------------------------
    # 5. Determinism Validation
    # -------------------------------------------------------------------------
    enhanced_report_run2 = runner.run_backtest(
        symbol="BTCUSDT",
        interval="1h",
        warmup_bars=100,
        predictive_mode=True,
        calibrated_params=calibrated_params,
    )

    assert enhanced_report.total_trades == enhanced_report_run2.total_trades
    assert enhanced_report.total_net_pnl == pytest.approx(enhanced_report_run2.total_net_pnl)
    assert enhanced_report.win_rate_pct == pytest.approx(enhanced_report_run2.win_rate_pct)
    assert enhanced_report.max_drawdown_pct == pytest.approx(enhanced_report_run2.max_drawdown_pct)
    assert [t.trade_id for t in enhanced_report.trades] == [t.trade_id for t in enhanced_report_run2.trades]

    # -------------------------------------------------------------------------
    # 6. Strict Causal Integrity (No Look-Ahead Bias at Candle K)
    # -------------------------------------------------------------------------
    # Check candle K in 2024 and candle K in 2025
    enriched_full = runner.indicators.calculate_all(full_df.copy())
    for k in [180, 320]:
        sub_k = enriched_full.iloc[: k + 1]

        # Evaluate on truncated series vs point K
        reg_full = regime_classifier.classify(sub_k)
        pred_full = predictive_engine.evaluate(sub_k)

        # Truncate raw candles to K and enrich
        raw_trunc = full_df.iloc[: k + 1].copy()
        enriched_trunc = runner.indicators.calculate_all(raw_trunc)
        reg_trunc = regime_classifier.classify(enriched_trunc)
        pred_trunc = predictive_engine.evaluate(enriched_trunc)

        assert reg_full.regime == reg_trunc.regime
        assert reg_full.confidence == pytest.approx(reg_trunc.confidence)
        assert pred_full.predictive_score == pytest.approx(pred_trunc.predictive_score)
        assert pred_full.direction_bias == pred_trunc.direction_bias

    # -------------------------------------------------------------------------
    # 7. Report Serialization Roundtrip
    # -------------------------------------------------------------------------
    report_dict = enhanced_report.to_dict()
    assert isinstance(report_dict, dict)
    assert "trades" in report_dict
    assert "equity_curve" in report_dict

    json_str = json.dumps(report_dict)
    assert isinstance(json_str, str)
    reloaded_dict = json.loads(json_str)
    assert reloaded_dict["symbol"] == "BTCUSDT"
    assert reloaded_dict["total_trades"] == enhanced_report.total_trades
