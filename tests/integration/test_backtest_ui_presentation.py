from __future__ import annotations

import ast
import math
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.backtest_metrics import BacktestMetricsCalculator
from src.backtest_models import (
    EXCURSION_POLICY_VERSION,
    BacktestConfig,
    BacktestReport,
    ExecutionPolicyVersion,
    ExecutionTraceStatus,
)
from src.data_loader import BinanceDataLoader
from tests.unit.test_backtest_metrics import make_verified_spot_trade

APP_PATH = Path(__file__).resolve().parents[2] / "src" / "app.py"
HELPERS = {
    "_format_verified_expectancy_for_ui",
    "_r_coverage_for_ui",
    "_trade_field_for_ui",
    "_positive_finite_for_ui",
    "_supported_spot_long_for_ui",
    "_planned_rr_for_ui",
    "_planned_rr_summary_for_ui",
    "_verified_trade_r_for_ui",
    "_backtest_trade_table_for_ui",
    "_execution_trace_for_ui",
    "_execution_trace_summary_for_ui",
    "_execution_policy_for_ui",
    "_excursion_for_ui",
    "_excursion_coverage_for_ui",
}


def _ui_helpers():
    """app.py executes Streamlit on import; compile its real pure helpers."""
    parsed = ast.parse(APP_PATH.read_text(encoding="utf-8"), filename=str(APP_PATH))
    functions = [
        node
        for node in parsed.body
        if isinstance(node, ast.FunctionDef) and node.name in HELPERS
    ]
    assert {node.name for node in functions} == HELPERS
    namespace = {
        "math": math,
        "pd": pd,
        "BacktestMetricsCalculator": BacktestMetricsCalculator,
        "ExecutionPolicyVersion": ExecutionPolicyVersion,
        "ExecutionTraceStatus": ExecutionTraceStatus,
    }
    namespace["EXCURSION_POLICY_VERSION"] = EXCURSION_POLICY_VERSION
    exec(
        compile(ast.Module(body=functions, type_ignores=[]), str(APP_PATH), "exec"),
        namespace,
    )
    return namespace


@pytest.mark.parametrize(
    ("status", "gross", "net", "expected_gross", "expected_net"),
    [
        ("COMPLETE", 0.0, -0.25, "0.00", "-0.25"),
        ("PARTIAL", 1.125, 0.75, "1.12", "0.75"),
        ("NONE_VERIFIED", None, None, "N/A", "N/A"),
        ("NO_TRADES", None, None, "N/A", "N/A"),
        ("UNKNOWN", 9.0, 8.0, "N/A", "N/A"),
    ],
)
def test_verified_expectancy_display_never_uses_legacy(
    status,
    gross,
    net,
    expected_gross,
    expected_net,
):
    format_value = _ui_helpers()["_format_verified_expectancy_for_ui"]
    metrics = {
        "r_coverage_status": status,
        "gross_expectancy_r": gross,
        "net_expectancy_r": net,
        "expectancy_r": 99.0,
    }
    assert format_value(metrics, "gross_expectancy_r") == expected_gross
    assert format_value(metrics, "net_expectancy_r") == expected_net
    metrics["gross_expectancy_r"] = None
    assert format_value(metrics, "gross_expectancy_r") == "N/A"


def test_excursion_ui_independently_formats_exact_bounds_missing_and_legacy():
    helpers = _ui_helpers()
    fmt = helpers["_excursion_for_ui"]
    coverage = helpers["_excursion_coverage_for_ui"]
    legacy = {"mfe_pct": 99.0, "mae_pct": 88.0}
    assert "proxy heredado" in fmt(legacy, "mfe")
    current = {
        "excursion_policy_version": EXCURSION_POLICY_VERSION,
        "mfe_observability": "EXACT_OHLC",
        "mfe_exact_pct": 0.0,
        "mae_observability": "BOUNDED_OHLC",
        "mae_lower_bound_pct": 1.0,
        "mae_upper_bound_pct": 3.0,
    }
    assert fmt(current, "mfe") == "0.00% (exacta OHLC)"
    assert fmt(current, "mae") == "[1.00%, 3.00%] (cota OHLC)"
    assert "indeterminada" in fmt(
        {**current, "mae_observability": "UNDETERMINED"}, "mae"
    )
    assert "indeterminada" in fmt({**current, "mfe_exact_pct": None}, "mfe")
    assert "2/3" in coverage(
        {
            "mfe_coverage_status": "PARTIAL",
            "mfe_exact_trades": 2,
            "mfe_total_trades": 3,
            "mfe_exact_avg_pct": 1.25,
        },
        "mfe",
    )
    assert "N/A" in coverage(
        {
            "mae_coverage_status": "NONE",
            "mae_exact_trades": 0,
            "mae_total_trades": 3,
            "mae_exact_avg_pct": None,
        },
        "mae",
    )
    assert "UNKNOWN" in coverage({}, "mfe")


def test_r_coverage_describes_partial_complete_missing_and_no_trades():
    coverage = _ui_helpers()["_r_coverage_for_ui"]
    partial = coverage(
        {
            "r_coverage_status": "PARTIAL",
            "r_verified_trades": 2,
            "r_excluded_trades": 1,
            "total_trades": 3,
        }
    )
    assert "2 verificables, 1 excluidas, 3 en total" in partial
    assert "Expectativa calculada únicamente sobre operaciones verificables" in partial
    assert "COMPLETE" in coverage(
        {
            "r_coverage_status": "COMPLETE",
            "r_verified_trades": 3,
            "r_excluded_trades": 0,
            "total_trades": 3,
        }
    )
    assert "N/A" in coverage({"r_coverage_status": "NONE_VERIFIED"})
    assert "N/A" in coverage({"r_coverage_status": "NO_TRADES"})
    assert "UNKNOWN" in coverage({})


def test_planned_rr_uses_executed_entry_initial_stop_and_individual_signal_plan():
    planned = _ui_helpers()["_planned_rr_for_ui"]
    trade = make_verified_spot_trade("trail", 40.0, 38.0, 40.0, final_stop=100.0)
    config = BacktestConfig()
    assert planned(trade, config) == pytest.approx(5.0)  # (120 - 100) / (100 - 96)
    assert planned(replace(trade, sl_price=99.0), config) == pytest.approx(5.0)
    assert planned(
        replace(
            trade,
            initial_stop_price=90.0,
            initial_risk_per_unit=10.0,
            initial_risk_amount=100.0,
        ),
        config,
    ) == pytest.approx(2.0)
    assert planned(replace(trade, tp_price=0.0), config) is None
    assert planned(replace(trade, initial_stop_price=None), config) is None
    assert planned(replace(trade, initial_stop_price=100.0), config) is None
    assert planned(replace(trade, initial_risk_amount=41.0), config) is None
    assert planned(replace(trade, direction="SHORT"), config) is None
    assert planned(replace(trade, size_units=0.0), config) is None
    assert planned(replace(trade, tp_price=math.inf), config) is None
    assert (
        planned({"entry_price": 100, "sl_price": 90, "tp_price": 120}, config) is None
    )
    assert planned(trade, BacktestConfig(market_type="PERP")) is None
    assert planned(trade, BacktestConfig(leverage=2.0)) is None


def test_planned_rr_mean_averages_individual_ratios_without_fallback():
    summary = _ui_helpers()["_planned_rr_summary_for_ui"]
    first = make_verified_spot_trade("first", 40.0, 38.0, 40.0)
    second = replace(
        first,
        trade_id="second",
        initial_stop_price=90.0,
        initial_risk_per_unit=10.0,
        initial_risk_amount=100.0,
    )
    missing = replace(first, trade_id="missing", tp_price=0.0)
    assert summary([first, second, missing], BacktestConfig()) == (3.5, 2)
    assert summary([missing], BacktestConfig()) == (None, 0)


def test_trade_table_separates_initial_and_final_stop_and_excludes_legacy_r():
    table = _ui_helpers()["_backtest_trade_table_for_ui"]
    config = BacktestConfig()
    verified = make_verified_spot_trade("verified", 40.0, 38.0, 40.0, final_stop=100.0)
    old = replace(
        verified,
        trade_id="old",
        initial_stop_price=None,
        initial_risk_per_unit=None,
        initial_risk_amount=None,
        net_r_multiple=None,
        r_multiple=99.0,
    )
    rows = table([verified, old], config)
    assert rows.loc[0, "P. entrada ejecutada"] == "100.00"
    assert rows.loc[0, "SL inicial"] == "96.00"
    assert rows.loc[0, "SL final"] == "100.00"
    assert rows.loc[0, "TP planificado"] == "120.00"
    assert rows.loc[0, "R bruto simulado"] == "1.00"
    assert rows.loc[0, "R neto simulado"] == "0.95"
    assert rows.loc[0, "PnL neto ($)"] == 38.0
    assert rows.loc[1, "SL inicial"] == "N/A"
    assert rows.loc[1, "R bruto simulado"] == rows.loc[1, "R neto simulado"] == "N/A"
    assert rows.loc[1, "Trazabilidad salida"] == "N/A (histórico sin metadatos)"
    assert (
        table([{"trade_id": "older", "entry_price": 100.0}], config).loc[
            0, "SL inicial"
        ]
        == "N/A"
    )
    assert (
        table([verified], BacktestConfig(market_type="PERP")).loc[0, "R bruto simulado"]
        == "N/A"
    )


def test_execution_trace_table_and_summary_distinguish_conflict_gap_and_legacy():
    helpers = _ui_helpers()
    base = make_verified_spot_trade("base", 40.0, 38.0, 40.0)
    conflict = replace(base, execution_trace_status="INTRABAR_SL_FIRST")
    gap = replace(base, trade_id="gap", execution_trace_status="OPENING_LEVEL_REVIEW")
    clean = replace(
        base, trade_id="clean", execution_trace_status="NO_IDENTIFIED_CONFLICT"
    )
    legacy = {
        key: value
        for key, value in base.to_dict().items()
        if key != "execution_trace_status"
    }
    rows = helpers["_backtest_trade_table_for_ui"](
        [conflict, gap, clean, legacy], BacktestConfig()
    )
    assert "SL primero (simulado)" in rows.loc[0, "Trazabilidad salida"]
    assert "fill pendiente de revisión" in rows.loc[1, "Trazabilidad salida"]
    assert "no verificado" in rows.loc[2, "Trazabilidad salida"]
    assert rows.loc[3, "Trazabilidad salida"] == "N/A (histórico sin metadatos)"
    summary = helpers["_execution_trace_summary_for_ui"]([conflict, gap, clean, legacy])
    assert "1 conflictos intrabar" in summary
    assert "1 aperturas/gaps" in summary
    assert "1 estados desconocidos" in summary
    assert "OHLC no revela" in summary


def test_c1_execution_policy_is_visible_without_reclassifying_old_gap_records():
    helpers = _ui_helpers()
    base = make_verified_spot_trade("base", 40.0, 38.0, 40.0)
    prior = replace(base, execution_trace_status="OPENING_LEVEL_REVIEW")
    current = replace(
        base,
        trade_id="c1",
        execution_trace_status="OPENING_LEVEL_REVIEW",
        execution_policy_version=ExecutionPolicyVersion.SPOT_LONG_C1.value,
    )
    rows = helpers["_backtest_trade_table_for_ui"]([prior, current], BacktestConfig())
    assert "fill pendiente de revisión" in rows.loc[0, "Trazabilidad salida"]
    assert (
        rows.loc[0, "Política ejecución"]
        == "N/A (metodología histórica no identificada)"
    )
    assert "fill simulado C1 (no verificado)" in rows.loc[1, "Trazabilidad salida"]
    assert "TP limit simulado" in rows.loc[1, "Política ejecución"]
    summary = helpers["_execution_trace_summary_for_ui"]([prior, current])
    assert "con política C1: 1" in summary
    assert "sin versión acreditada: 1" in summary


def _sample_report():
    trade = make_verified_spot_trade("ui", 40.0, 38.0, 40.0, final_stop=100.0)
    return BacktestReport(
        config=BacktestConfig(),
        symbol="BTCUSDT",
        timeframe="1h",
        start_time="2024-01-01",
        end_time="2024-01-02",
        total_candles=250,
        total_trades=1,
        winning_trades=1,
        losing_trades=0,
        win_rate_pct=100.0,
        profit_factor=2.0,
        expectancy=38.0,
        expectancy_r=99.0,
        max_drawdown_pct=5.0,
        max_drawdown_usd=50.0,
        max_drawdown_duration_bars=2,
        avg_mfe_pct=2.0,
        avg_mae_pct=1.0,
        avg_bars_held=1.0,
        total_gross_pnl=40.0,
        total_fees_paid=2.0,
        total_net_pnl=38.0,
        return_on_capital_pct=3.8,
        trades=[trade],
        gross_expectancy_r=1.0,
        net_expectancy_r=0.95,
        r_verified_trades=1,
        r_excluded_trades=0,
        r_coverage_status="COMPLETE",
    )


def test_streamlit_renders_independent_excursion_coverage_and_intervals(
    monkeypatch,
    tmp_path,
    synthetic_ohlcv,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "contexts.db"))
    monkeypatch.setattr(
        BinanceDataLoader,
        "get_klines",
        lambda self, *args, **kwargs: synthetic_ohlcv.copy(),
    )
    report = _sample_report()
    trade = replace(
        report.trades[0],
        excursion_policy_version=EXCURSION_POLICY_VERSION,
        mfe_observability="EXACT_OHLC",
        mfe_exact_pct=2.0,
        mae_observability="BOUNDED_OHLC",
        mae_lower_bound_pct=0.5,
        mae_upper_bound_pct=1.5,
    )
    report = replace(
        report,
        trades=[trade],
        mfe_exact_avg_pct=2.0,
        mfe_exact_trades=1,
        mfe_exact_denominator=1,
        mfe_total_trades=1,
        mfe_coverage_status="COMPLETE",
        mae_exact_avg_pct=None,
        mae_exact_trades=0,
        mae_exact_denominator=0,
        mae_total_trades=1,
        mae_coverage_status="NONE",
    )
    app = AppTest.from_file(str(APP_PATH), default_timeout=30)
    app.session_state["backtest_report"] = report
    app.run()
    assert not app.exception
    assert any(
        "MFE exacta OHLC: 2.00%; cobertura COMPLETE (1/1" in item.value
        for item in app.caption
    )
    assert any(
        "MAE exacta OHLC: N/A; cobertura NONE (0/1" in item.value
        for item in app.caption
    )
    assert any(
        "[0.50%, 1.50%] (cota OHLC)" in item.value["MAE"].iloc[0]
        for item in app.dataframe
        if "MAE" in item.value.columns
    )
    assert any("Optimización no solicitada" in item.value for item in app.caption)


def test_streamlit_renders_verified_metrics_unknown_provenance_and_plan(
    monkeypatch,
    tmp_path,
    synthetic_ohlcv,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "contexts.db"))
    monkeypatch.setattr(
        BinanceDataLoader,
        "get_klines",
        lambda self, *args, **kwargs: synthetic_ohlcv.copy(),
    )
    app = AppTest.from_file(str(APP_PATH), default_timeout=30)
    app.session_state["backtest_report"] = _sample_report()
    app.run()
    assert not app.exception
    metrics = {item.label: item.value for item in app.metric}
    assert metrics["Expectativa bruta (R) — Simulación"] == "1.00"
    assert metrics["Expectativa neta (R) — Simulación"] == "0.95"
    assert metrics["R:R planificado medio — Simulación"] == "1 : 5.00"
    assert any("Cobertura R: COMPLETE" in item.value for item in app.caption)
    assert any("Procedencia del dataset: UNKNOWN" in item.value for item in app.warning)
    assert any("Planes R:R verificables: 1 de 1" in item.value for item in app.caption)
    assert any("1 estados desconocidos" in item.value for item in app.caption)
    assert any(
        "SL inicial" in item.value.columns and "SL final" in item.value.columns
        for item in app.dataframe
    )
    preset_selector = next(
        item for item in app.selectbox if item.label == "Estrategia Cuantitativa:"
    )
    assert len(preset_selector.options) == 5


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("INTRABAR_SL_FIRST", "SL primero (simulado)"),
        ("OPENING_LEVEL_REVIEW", "fill pendiente de revisión"),
    ],
)
def test_streamlit_shows_execution_trace_without_changing_metrics(
    monkeypatch, tmp_path, synthetic_ohlcv, status, expected
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "contexts.db"))
    monkeypatch.setattr(
        BinanceDataLoader,
        "get_klines",
        lambda self, *args, **kwargs: synthetic_ohlcv.copy(),
    )
    report = _sample_report()
    report.trades = [replace(report.trades[0], execution_trace_status=status)]
    app = AppTest.from_file(str(APP_PATH), default_timeout=30)
    app.session_state["backtest_report"] = report
    app.run()
    assert not app.exception
    assert any(
        expected in item.value["Trazabilidad salida"].iloc[0]
        for item in app.dataframe
        if "Trazabilidad salida" in item.value.columns
    )
    assert any(
        "SL primero es una hipótesis conservadora" in item.value for item in app.caption
    )
    metrics = {item.label: item.value for item in app.metric}
    assert metrics["Expectativa bruta (R) — Simulación"] == "1.00"
    assert metrics["Expectativa neta (R) — Simulación"] == "0.95"


@pytest.mark.parametrize(
    ("coverage", "expected_gross", "expected_net", "expected_plan"),
    [
        ("PARTIAL", "1.00", "0.95", "1 : 5.00"),
        ("NONE_VERIFIED", "N/A", "N/A", "N/A"),
        ("NO_TRADES", "N/A", "N/A", "N/A"),
    ],
)
def test_streamlit_coverage_states_do_not_fallback_to_legacy_or_hide_unknown_dataset(
    monkeypatch,
    tmp_path,
    synthetic_ohlcv,
    coverage,
    expected_gross,
    expected_net,
    expected_plan,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "contexts.db"))
    monkeypatch.setattr(
        BinanceDataLoader,
        "get_klines",
        lambda self, *args, **kwargs: synthetic_ohlcv.copy(),
    )
    report = _sample_report()
    old = replace(
        report.trades[0],
        trade_id="old",
        initial_stop_price=None,
        initial_risk_per_unit=None,
        initial_risk_amount=None,
        net_r_multiple=None,
    )
    if coverage == "PARTIAL":
        report = replace(
            report,
            trades=[report.trades[0], old],
            total_trades=2,
            r_excluded_trades=1,
            r_coverage_status=coverage,
        )
    elif coverage == "NONE_VERIFIED":
        report = replace(
            report,
            trades=[old.to_dict()],
            gross_expectancy_r=None,
            net_expectancy_r=None,
            r_verified_trades=0,
            r_excluded_trades=1,
            r_coverage_status=coverage,
        )
    else:
        report = replace(
            report,
            trades=[],
            total_trades=0,
            gross_expectancy_r=None,
            net_expectancy_r=None,
            r_verified_trades=0,
            r_excluded_trades=0,
            r_coverage_status=coverage,
        )
    app = AppTest.from_file(str(APP_PATH), default_timeout=30)
    app.session_state["backtest_report"] = report
    app.run()
    assert not app.exception
    metrics = {item.label: item.value for item in app.metric}
    assert metrics["Expectativa bruta (R) — Simulación"] == expected_gross
    assert metrics["Expectativa neta (R) — Simulación"] == expected_net
    assert metrics["R:R planificado medio — Simulación"] == expected_plan
    assert any(f"Cobertura R: {coverage}" in item.value for item in app.caption)
    assert any("Procedencia del dataset: UNKNOWN" in item.value for item in app.warning)
