from __future__ import annotations

import ast
import math
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.backtest_metrics import BacktestMetricsCalculator
from src.backtest_models import BacktestConfig, BacktestReport
from src.data_loader import BinanceDataLoader
from tests.unit.test_backtest_metrics import make_verified_spot_trade

APP_PATH = Path(__file__).resolve().parents[2] / "src" / "app.py"
HELPERS = {
    "_format_verified_expectancy_for_ui", "_r_coverage_for_ui",
    "_trade_field_for_ui", "_positive_finite_for_ui", "_supported_spot_long_for_ui",
    "_planned_rr_for_ui", "_planned_rr_summary_for_ui",
    "_verified_trade_r_for_ui", "_backtest_trade_table_for_ui",
}


def _ui_helpers():
    """app.py executes Streamlit on import; compile its real pure helpers."""
    parsed = ast.parse(APP_PATH.read_text(encoding="utf-8"), filename=str(APP_PATH))
    functions = [node for node in parsed.body
                 if isinstance(node, ast.FunctionDef) and node.name in HELPERS]
    assert {node.name for node in functions} == HELPERS
    namespace = {"math": math, "pd": pd,
                 "BacktestMetricsCalculator": BacktestMetricsCalculator}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(APP_PATH), "exec"), namespace)
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
    status, gross, net, expected_gross, expected_net,
):
    format_value = _ui_helpers()["_format_verified_expectancy_for_ui"]
    metrics = {"r_coverage_status": status, "gross_expectancy_r": gross,
               "net_expectancy_r": net, "expectancy_r": 99.0}
    assert format_value(metrics, "gross_expectancy_r") == expected_gross
    assert format_value(metrics, "net_expectancy_r") == expected_net
    metrics["gross_expectancy_r"] = None
    assert format_value(metrics, "gross_expectancy_r") == "N/A"


def test_r_coverage_describes_partial_complete_missing_and_no_trades():
    coverage = _ui_helpers()["_r_coverage_for_ui"]
    partial = coverage({"r_coverage_status": "PARTIAL", "r_verified_trades": 2,
                        "r_excluded_trades": 1, "total_trades": 3})
    assert "2 verificables, 1 excluidas, 3 en total" in partial
    assert "Expectativa calculada únicamente sobre operaciones verificables" in partial
    assert "COMPLETE" in coverage({"r_coverage_status": "COMPLETE",
                                   "r_verified_trades": 3, "r_excluded_trades": 0,
                                   "total_trades": 3})
    assert "N/A" in coverage({"r_coverage_status": "NONE_VERIFIED"})
    assert "N/A" in coverage({"r_coverage_status": "NO_TRADES"})
    assert "UNKNOWN" in coverage({})


def test_planned_rr_uses_executed_entry_initial_stop_and_individual_signal_plan():
    planned = _ui_helpers()["_planned_rr_for_ui"]
    trade = make_verified_spot_trade("trail", 40.0, 38.0, 40.0, final_stop=100.0)
    config = BacktestConfig()
    assert planned(trade, config) == pytest.approx(5.0)  # (120 - 100) / (100 - 96)
    assert planned(replace(trade, sl_price=99.0), config) == pytest.approx(5.0)
    assert planned(replace(trade, initial_stop_price=90.0,
                           initial_risk_per_unit=10.0,
                           initial_risk_amount=100.0), config) == pytest.approx(2.0)
    assert planned(replace(trade, tp_price=0.0), config) is None
    assert planned(replace(trade, initial_stop_price=None), config) is None
    assert planned(replace(trade, initial_stop_price=100.0), config) is None
    assert planned(replace(trade, initial_risk_amount=41.0), config) is None
    assert planned(replace(trade, direction="SHORT"), config) is None
    assert planned(replace(trade, size_units=0.0), config) is None
    assert planned(replace(trade, tp_price=math.inf), config) is None
    assert planned({"entry_price": 100, "sl_price": 90, "tp_price": 120}, config) is None
    assert planned(trade, BacktestConfig(market_type="PERP")) is None
    assert planned(trade, BacktestConfig(leverage=2.0)) is None


def test_planned_rr_mean_averages_individual_ratios_without_fallback():
    summary = _ui_helpers()["_planned_rr_summary_for_ui"]
    first = make_verified_spot_trade("first", 40.0, 38.0, 40.0)
    second = replace(first, trade_id="second", initial_stop_price=90.0,
                     initial_risk_per_unit=10.0, initial_risk_amount=100.0)
    missing = replace(first, trade_id="missing", tp_price=0.0)
    assert summary([first, second, missing], BacktestConfig()) == (3.5, 2)
    assert summary([missing], BacktestConfig()) == (None, 0)


def test_trade_table_separates_initial_and_final_stop_and_excludes_legacy_r():
    table = _ui_helpers()["_backtest_trade_table_for_ui"]
    config = BacktestConfig()
    verified = make_verified_spot_trade("verified", 40.0, 38.0, 40.0, final_stop=100.0)
    old = replace(verified, trade_id="old", initial_stop_price=None,
                  initial_risk_per_unit=None, initial_risk_amount=None,
                  net_r_multiple=None, r_multiple=99.0)
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
    assert table([{"trade_id": "older", "entry_price": 100.0}], config).loc[0, "SL inicial"] == "N/A"
    assert table([verified], BacktestConfig(market_type="PERP")).loc[0, "R bruto simulado"] == "N/A"


def _sample_report():
    trade = make_verified_spot_trade("ui", 40.0, 38.0, 40.0, final_stop=100.0)
    return BacktestReport(
        config=BacktestConfig(), symbol="BTCUSDT", timeframe="1h",
        start_time="2024-01-01", end_time="2024-01-02", total_candles=250,
        total_trades=1, winning_trades=1, losing_trades=0, win_rate_pct=100.0,
        profit_factor=2.0, expectancy=38.0, expectancy_r=99.0,
        max_drawdown_pct=5.0, max_drawdown_usd=50.0,
        max_drawdown_duration_bars=2, avg_mfe_pct=2.0, avg_mae_pct=1.0,
        avg_bars_held=1.0, total_gross_pnl=40.0, total_fees_paid=2.0,
        total_net_pnl=38.0, return_on_capital_pct=3.8, trades=[trade],
        gross_expectancy_r=1.0, net_expectancy_r=0.95,
        r_verified_trades=1, r_excluded_trades=0, r_coverage_status="COMPLETE",
    )


def test_streamlit_renders_verified_metrics_unknown_provenance_and_plan(
    monkeypatch, tmp_path, synthetic_ohlcv,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "contexts.db"))
    monkeypatch.setattr(BinanceDataLoader, "get_klines",
                        lambda self, *args, **kwargs: synthetic_ohlcv.copy())
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
    assert any("SL inicial" in item.value.columns and "SL final" in item.value.columns
               for item in app.dataframe)
    preset_selector = next(item for item in app.selectbox
                           if item.label == "Estrategia Cuantitativa:")
    assert len(preset_selector.options) == 5


@pytest.mark.parametrize(
    ("coverage", "expected_gross", "expected_net", "expected_plan"),
    [
        ("PARTIAL", "1.00", "0.95", "1 : 5.00"),
        ("NONE_VERIFIED", "N/A", "N/A", "N/A"),
        ("NO_TRADES", "N/A", "N/A", "N/A"),
    ],
)
def test_streamlit_coverage_states_do_not_fallback_to_legacy_or_hide_unknown_dataset(
    monkeypatch, tmp_path, synthetic_ohlcv, coverage, expected_gross,
    expected_net, expected_plan,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "contexts.db"))
    monkeypatch.setattr(BinanceDataLoader, "get_klines",
                        lambda self, *args, **kwargs: synthetic_ohlcv.copy())
    report = _sample_report()
    old = replace(report.trades[0], trade_id="old", initial_stop_price=None,
                  initial_risk_per_unit=None, initial_risk_amount=None,
                  net_r_multiple=None)
    if coverage == "PARTIAL":
        report = replace(report, trades=[report.trades[0], old], total_trades=2,
                         r_excluded_trades=1, r_coverage_status=coverage)
    elif coverage == "NONE_VERIFIED":
        report = replace(report, trades=[old.to_dict()], gross_expectancy_r=None,
                         net_expectancy_r=None, r_verified_trades=0,
                         r_excluded_trades=1, r_coverage_status=coverage)
    else:
        report = replace(report, trades=[], total_trades=0,
                         gross_expectancy_r=None, net_expectancy_r=None,
                         r_verified_trades=0, r_excluded_trades=0,
                         r_coverage_status=coverage)
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
