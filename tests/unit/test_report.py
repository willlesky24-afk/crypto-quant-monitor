from __future__ import annotations

import inspect

from src.report import MarketReport
from src.signal_history import SignalHistory
from tests.unit.test_database import make_database


def make_history(tmp_path):
    database = make_database(tmp_path / "report.db")
    parameters = inspect.signature(SignalHistory).parameters
    if "database" in parameters:
        return SignalHistory(database=database)
    if "db" in parameters:
        return SignalHistory(db=database)
    database.connection.close()
    if "db_path" in parameters:
        return SignalHistory(db_path=tmp_path / "report.db")
    if "database_name" in parameters:
        return SignalHistory(database_name=tmp_path / "report.db")
    raise AssertionError("SignalHistory debe permitir inyección")


def make_report(history):
    parameters = inspect.signature(MarketReport).parameters
    if "signal_history" in parameters:
        return MarketReport(signal_history=history)
    if "history" in parameters:
        return MarketReport(history=history)
    raise AssertionError("MarketReport debe permitir inyectar SignalHistory")


def test_report_contract_is_pure_by_default(tmp_path, analysis_factory, profile):
    history = make_history(tmp_path)
    report_engine = make_report(history)
    try:
        report = report_engine.generate("BTCUSDT", analysis_factory(), profile)
        assert set(report) == {
            "symbol",
            "price",
            "trend",
            "momentum",
            "volatility",
            "volume",
            "score",
            "profile",
            "summary",
            "conclusion",
            "state",
            "risk",
            "risk_reason",
            "trend_analysis",
            "alerts",
            "signal",
            "risk_engine",
            "decision",
            "quant_score",
        }
        # Analytical purity: no side effects in database by default
        rows = history.get_history()
        assert len(rows) == 0
    finally:
        history.db.connection.close()


def test_report_auto_save_persists_when_enabled(tmp_path, analysis_factory, profile):
    history = make_history(tmp_path)
    report_engine = make_report(history)
    try:
        report = report_engine.generate(
            "BTCUSDT", analysis_factory(), profile, auto_save=True
        )
        rows = history.get_history()
        assert len(rows) == 1
        # In new schema: index 11 is signal, index 12 is decision
        assert rows[0][11] == report["signal"]["state"]
        assert rows[0][12] == report["decision"]["decision"]
    finally:
        history.db.connection.close()


def test_report_keeps_default_history_factory_compatible(monkeypatch):
    sentinel = object()
    monkeypatch.setattr("src.report.SignalHistory", lambda: sentinel)
    assert MarketReport().signal_history is sentinel

