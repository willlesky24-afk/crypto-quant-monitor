from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest

from src.backtest_metrics import BacktestMetricsCalculator
from src.backtest_models import (
    EXCURSION_POLICY_VERSION,
    BacktestConfig,
    BacktestValidationError,
    DatasetProvenance,
    OptimizationUnavailableError,
)
from src.backtest_runner import BacktestRunner
from src.dataset_manager import HistoricalDatasetManager
from src.historical_data_loader import HistoricalDataLoader
from src.parquet_store import ParquetStore
from src.regime_classifier import MarketRegime
from src.strategy_optimizer import OptimizedParameters


def _verified_calibration_for_all_regimes():
    return {
        regime.value: OptimizedParameters(
            regime=regime.value,
            volatility_state="NORMAL",
            atr_tp_multiplier=3.0,
            atr_sl_multiplier=1.5,
            expected_rr=2.0,
            sample_size=20,
            confidence=0.8,
            validation_period={},
            calibration_state="AVAILABLE",
            excursion_policy_version=EXCURSION_POLICY_VERSION,
        )
        for regime in MarketRegime
    }


def test_runner_calibration_intent_is_explicit_and_fails_closed(make_synthetic_candles):
    runner = BacktestRunner(predictive_mode=True)
    candles = make_synthetic_candles(periods=220, freq="1h", base_price=100.0)
    for unavailable in (None, {}):
        with pytest.raises(OptimizationUnavailableError, match="no hay parámetros"):
            runner.run_backtest(
                df=candles,
                predictive_mode=True,
                calibrated_params=unavailable,
                calibration_required=True,
            )
    plain = runner.run_backtest(df=candles, predictive_mode=True, calibrated_params={})
    assert plain.calibration_state == "NOT_REQUESTED"
    exact = _verified_calibration_for_all_regimes()
    report = runner.run_backtest(
        df=candles,
        predictive_mode=True,
        calibrated_params=exact,
        calibration_required=True,
    )
    assert report.calibration_state == "AVAILABLE"
    assert report.metrics["calibration_state"] == "AVAILABLE"
    with pytest.raises(OptimizationUnavailableError, match="faltan parámetros"):
        runner.run_backtest(
            df=candles,
            predictive_mode=True,
            calibrated_params={"UNSEEN": next(iter(exact.values()))},
            calibration_required=True,
        )


def test_ui_clears_previous_report_when_requested_calibration_is_rejected(
    make_synthetic_candles,
):
    helper = _load_ui_backtest_helper()
    state = {"backtest_report": object()}
    candles = make_synthetic_candles(periods=220, freq="1h", base_price=100.0)
    with pytest.raises(OptimizationUnavailableError):
        helper(
            BacktestConfig(),
            candles,
            "BTCUSDT",
            "1h",
            state,
            calibrated_params={},
            calibration_required=True,
        )
    assert "backtest_report" not in state


def test_backtest_runner_empty_and_insufficient_warmup(tmp_path: Path):
    store = ParquetStore(base_dir=tmp_path / "historical")
    manager = HistoricalDatasetManager(store=store)
    runner = BacktestRunner(dataset_manager=manager)

    # Empty
    rep_empty = runner.run_backtest("BTCUSDT", "1h", df=pd.DataFrame())
    assert rep_empty.total_candles == 0
    assert rep_empty.total_trades == 0
    assert rep_empty.win_rate_pct == 0.0
    assert rep_empty.gross_expectancy_r is None
    assert rep_empty.net_expectancy_r is None
    assert rep_empty.r_coverage_status == "NO_TRADES"
    assert rep_empty.metrics["r_verified_trades"] == 0

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
    assert rep_short.r_coverage_status == "NO_TRADES"


def test_backtest_runner_with_synthetic_dataset(make_synthetic_candles):
    # Generate 300 synthetic bars (enough for 200 warm-up + 100 active bars)
    df = make_synthetic_candles(
        start="2024-01-01", periods=300, freq="1h", base_price=100.0
    )

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
    assert report.r_verified_trades + report.r_excluded_trades == report.total_trades
    assert report.metrics["gross_expectancy_r"] == report.gross_expectancy_r
    assert report.to_dict()["net_expectancy_r"] == report.net_expectancy_r


def test_backtest_runner_loads_from_dataset_manager(
    tmp_path: Path, make_synthetic_candles
):
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


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (BacktestConfig(direction="SHORT"), "SHORT"),
        (BacktestConfig(direction="BOTH"), "BOTH"),
        (BacktestConfig(leverage=2.0), "leverage"),
        (BacktestConfig(market_type="PERP"), "PERP"),
        (BacktestConfig(market_type="PERP", leverage=3.0), "PERP"),
    ],
)
def test_runner_rejects_unsupported_config_before_empty_dataset(config, message):
    runner = BacktestRunner(config=config)
    with pytest.raises(BacktestValidationError, match=message):
        runner.run_backtest("BTCUSDT", "1h", df=pd.DataFrame())


def _load_ui_backtest_helper():
    # app.py executes Streamlit on import; compile only its actual backtest helper.
    app_path = Path(__file__).parents[2] / "src" / "app.py"
    module = ast.parse(app_path.read_text(encoding="utf-8"), filename=str(app_path))
    helper = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_run_backtest_for_ui"
    )
    namespace = {"BacktestRunner": BacktestRunner}
    exec(
        compile(ast.Module(body=[helper], type_ignores=[]), str(app_path), "exec"),
        namespace,
    )
    return namespace[helper.name]


def test_ui_backtest_helper_runs_supported_spot_and_replaces_report(
    make_synthetic_candles,
):
    helper = _load_ui_backtest_helper()
    state = {"backtest_report": object()}
    candles = make_synthetic_candles(periods=250, freq="1h", base_price=100.0)
    report = helper(BacktestConfig(), candles, "BTCUSDT", "1h", state)
    assert report.total_candles == 250
    assert state["backtest_report"] is report


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (BacktestConfig(direction="BOTH"), "BOTH"),
        (BacktestConfig(leverage=2.0), "leverage"),
        (BacktestConfig(market_type="PERP"), "PERP"),
    ],
)
def test_ui_backtest_helper_rejection_discards_previous_metrics(config, message):
    helper = _load_ui_backtest_helper()
    state = {"backtest_report": object()}
    with pytest.raises(BacktestValidationError, match=message):
        helper(config, pd.DataFrame(), "BTCUSDT", "1h", state)
    assert "backtest_report" not in state


def test_ui_sharpe_formatter_distinguishes_na_from_real_zero():
    app_path = Path(__file__).parents[2] / "src" / "app.py"
    module = ast.parse(app_path.read_text(encoding="utf-8"), filename=str(app_path))
    helper = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "_format_sharpe_for_ui"
    )
    namespace = {}
    exec(
        compile(ast.Module(body=[helper], type_ignores=[]), str(app_path), "exec"),
        namespace,
    )
    assert namespace[helper.name](None) == "N/A"
    assert namespace[helper.name](0.0) == "0.00"


def test_runner_direct_dataframe_remains_unknown_and_sharpe_na(make_synthetic_candles):
    candles = make_synthetic_candles(periods=250, freq="1h")
    candles.attrs["_controlled_provenance"] = DatasetProvenance(
        status="CONTROLLED_INGESTION",
        provider="BINANCE_PUBLIC_SPOT_REST",
        instrument_type="CRYPTO_SPOT",
        calendar="24_7",
        interval="1h",
        temporal_validation="VALID",
        content_sha256="arbitrary",
    )
    report = BacktestRunner().run_backtest("BTCUSDT", "1h", df=candles, warmup_bars=200)
    assert report.data_provenance.status == "UNKNOWN"
    assert report.sharpe_ratio is None
    assert report.metrics["sharpe_ratio"] is None


def test_runner_uses_verified_persisted_calendar_for_annualization(
    tmp_path, monkeypatch, make_synthetic_candles
):
    candles = make_synthetic_candles(periods=250, freq="1h", base_price=100.0)
    raw = []
    for _, row in candles.iterrows():
        opened = int(row["timestamp"].value // 1_000_000)
        raw.append(
            [
                opened,
                str(row["open"]),
                str(row["high"]),
                str(row["low"]),
                str(row["close"]),
                str(row["volume"]),
                opened + 3_600_000 - 1,
                "0",
                1,
                "0",
                "0",
                "0",
            ]
        )
    loader = HistoricalDataLoader(request_delay=0.0)
    monkeypatch.setattr(loader, "_fetch_chunk_with_retry", lambda **kwargs: raw)
    store = ParquetStore(base_dir=tmp_path / "verified")
    manager = HistoricalDatasetManager(store=store, data_loader=loader)
    start_ms = raw[0][0]
    manager.sync_dataset("BTCUSDT", "1h", start_time=start_ms, end_time=raw[-1][0])

    observed_periods = []
    original = BacktestMetricsCalculator.calculate_metrics

    def capture_metrics(*args, **kwargs):
        observed_periods.append(kwargs.get("periods_per_year"))
        return original(*args, **kwargs)

    monkeypatch.setattr(
        BacktestMetricsCalculator, "calculate_metrics", staticmethod(capture_metrics)
    )
    report = BacktestRunner(
        config=BacktestConfig(min_quant_score=40.0), dataset_manager=manager
    ).run_backtest("BTCUSDT", "1h", warmup_bars=200)
    assert report.data_provenance.status == "CONTROLLED_INGESTION"
    assert report.data_provenance.temporal_validation == "VALID"
    assert observed_periods == [8760]
    assert report.total_candles == 250


@pytest.mark.parametrize("mutation", ["reversed", "swapped", "duplicate", "missing"])
def test_runner_rejects_invalid_timestamps_before_indicators_and_signals(
    tmp_path, make_synthetic_candles, mutation
):
    bars = make_synthetic_candles(periods=50, freq="1h")
    if mutation == "reversed":
        bars = bars.iloc[::-1].reset_index(drop=True)
    elif mutation == "swapped":
        bars = bars.iloc[[0, 2, 1, *range(3, 50)]].reset_index(drop=True)
    elif mutation == "duplicate":
        bars.loc[2, "timestamp"] = bars.loc[1, "timestamp"]
    else:
        bars.loc[2, "timestamp"] = pd.NaT

    source = bars.copy(deep=True)
    store = ParquetStore(base_dir=tmp_path / "invalid_chronology")
    runner = BacktestRunner(dataset_manager=HistoricalDatasetManager(store=store))
    runner.indicators.calculate_all = Mock(
        side_effect=AssertionError("Indicadores ejecutados")
    )
    runner.signal_engine.evaluate = Mock(side_effect=AssertionError("Señal generada"))
    runner.engine.run = Mock(side_effect=AssertionError("Operaciones ejecutadas"))

    with pytest.raises(BacktestValidationError, match="timestamp"):
        runner.run_backtest("BTCUSDT", "1h", df=bars, warmup_bars=200)
    runner.indicators.calculate_all.assert_not_called()
    runner.signal_engine.evaluate.assert_not_called()
    runner.engine.run.assert_not_called()
    pd.testing.assert_frame_equal(bars, source)


def test_runner_rejects_future_row_before_ema_can_be_contaminated(
    tmp_path, make_synthetic_candles
):
    chronological = make_synthetic_candles(periods=80, freq="1h")
    future_first = chronological.iloc[[79, *range(79)]].reset_index(drop=True)
    store = ParquetStore(base_dir=tmp_path / "future_first")
    runner = BacktestRunner(dataset_manager=HistoricalDatasetManager(store=store))
    valid_ema = runner.indicators.calculate_all(chronological.copy()).iloc[40]["ema_50"]
    contaminated_ema = (
        runner.indicators.calculate_all(future_first.copy())
        .sort_values("timestamp")
        .iloc[40]["ema_50"]
    )
    assert valid_ema != pytest.approx(contaminated_ema)
    runner.indicators.calculate_all = Mock(side_effect=AssertionError("EMA calculada"))

    with pytest.raises(BacktestValidationError, match="desordenado"):
        runner.run_backtest("BTCUSDT", "1h", df=future_first)
    runner.indicators.calculate_all.assert_not_called()


def test_ui_backtest_helper_clears_old_report_for_invalid_chronology(
    make_synthetic_candles,
):
    helper = _load_ui_backtest_helper()
    state = {"backtest_report": object()}
    candles = make_synthetic_candles(periods=50, freq="1h").iloc[::-1]
    with pytest.raises(BacktestValidationError, match="desordenado"):
        helper(BacktestConfig(), candles, "BTCUSDT", "1h", state)
    assert "backtest_report" not in state


def test_runner_does_not_report_rows_without_columns_as_zero_trades(tmp_path):
    store = ParquetStore(base_dir=tmp_path / "missing_timestamp")
    runner = BacktestRunner(dataset_manager=HistoricalDatasetManager(store=store))
    with pytest.raises(BacktestValidationError, match="timestamp"):
        runner.run_backtest("BTCUSDT", "1h", df=pd.DataFrame(index=range(3)))


@pytest.mark.parametrize(
    ("count", "expected_signals"),
    [(1, 0), (199, 0), (200, 1), (201, 2)],
)
def test_default_warmup_is_fixed_at_200_closed_candles(
    tmp_path, make_synthetic_candles, count, expected_signals
):
    candles = make_synthetic_candles(periods=201).iloc[:count].copy()
    store = ParquetStore(base_dir=tmp_path / "warmup_boundary")
    runner = BacktestRunner(dataset_manager=HistoricalDatasetManager(store=store))
    original_indicators = runner.indicators.calculate_all
    runner.indicators.calculate_all = Mock(wraps=original_indicators)
    runner.engine.run = Mock(return_value=([], []))

    report = runner.run_backtest("BTCUSDT", "1h", df=candles)

    assert report.total_candles == count
    assert report.total_trades == 0
    if count < 200:
        runner.indicators.calculate_all.assert_not_called()
        runner.engine.run.assert_not_called()
        assert report.equity_curve == []
    else:
        runner.indicators.calculate_all.assert_called_once()
        runner.engine.run.assert_called_once()
        signals = runner.engine.run.call_args.kwargs["signals"]
        assert len(signals) == expected_signals
        assert signals[0].candle_timestamp == candles.iloc[199]["timestamp"]


@pytest.mark.parametrize(
    ("predictive_mode", "expected_first_index"),
    [(False, 19), (True, 34)],
)
def test_requested_short_warmup_respects_component_history(
    tmp_path, make_synthetic_candles, predictive_mode, expected_first_index
):
    candles = make_synthetic_candles(periods=40)
    store = ParquetStore(base_dir=tmp_path / "component_minimum")
    runner = BacktestRunner(dataset_manager=HistoricalDatasetManager(store=store))
    runner.engine.run = Mock(return_value=([], []))

    runner.run_backtest(
        "BTCUSDT",
        "1h",
        df=candles,
        warmup_bars=1,
        predictive_mode=predictive_mode,
    )

    signals = runner.engine.run.call_args.kwargs["signals"]
    assert (
        signals[0].candle_timestamp == candles.iloc[expected_first_index]["timestamp"]
    )
    assert len(signals) == len(candles) - expected_first_index


def test_injected_predictive_history_requirement_is_respected(
    tmp_path, make_synthetic_candles
):
    candles = make_synthetic_candles(periods=46)
    store = ParquetStore(base_dir=tmp_path / "predictive_minimum")
    runner = BacktestRunner(dataset_manager=HistoricalDatasetManager(store=store))
    runner.predictive_engine.min_history_bars = 45
    runner.engine.run = Mock(return_value=([], []))

    runner.run_backtest(
        "BTCUSDT", "1h", df=candles, warmup_bars=1, predictive_mode=True
    )

    signals = runner.engine.run.call_args.kwargs["signals"]
    assert len(signals) == 2
    assert signals[0].candle_timestamp == candles.iloc[44]["timestamp"]


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "20"])
def test_invalid_requested_warmup_is_rejected(value):
    with pytest.raises(BacktestValidationError, match="warmup_bars"):
        BacktestRunner().run_backtest(
            "BTCUSDT", "1h", df=pd.DataFrame(), warmup_bars=value
        )
