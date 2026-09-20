from __future__ import annotations

import inspect
import sqlite3
from pathlib import Path

from src.signal_history import SignalHistory
from tests.unit.test_database import make_database


def make_history(tmp_path: Path):
    path = tmp_path / "history.db"
    parameters = inspect.signature(SignalHistory).parameters
    if "database" in parameters:
        return SignalHistory(database=make_database(path))
    if "db" in parameters:
        return SignalHistory(db=make_database(path))
    if "db_path" in parameters:
        return SignalHistory(db_path=path)
    if "database_name" in parameters:
        return SignalHistory(database_name=path)
    raise AssertionError("SignalHistory debe aceptar una base o ruta inyectada")


def test_history_persists_real_signal_separately_from_decision(
    tmp_path, analysis_factory
):
    history = make_history(tmp_path)
    signal = {"state": "🟡 Señal moderada"}
    decision = {"decision": "🔴 Contexto débil"}
    try:
        saved = history.save(
            "BTCUSDT",
            analysis_factory(),
            decision,
            {"score": 55},
            {"level": "Medio"},
            signal=signal,
            timeframe="4h",
            candle_timestamp="2026-01-01 12:00:00",
        )
        assert saved["signal"] == signal["state"]
        assert saved["decision"] == decision["decision"]
        assert saved["timeframe"] == "4h"
        assert saved["candle_timestamp"] == "2026-01-01 12:00:00"
        assert saved["inserted"] is True
        assert len(history.get_history()) == 1

        # Second save with exact same candle_timestamp and timeframe -> ignored (inserted=False)
        saved_duplicate = history.save(
            "BTCUSDT",
            analysis_factory(),
            decision,
            {"score": 55},
            {"level": "Medio"},
            signal=signal,
            timeframe="4h",
            candle_timestamp="2026-01-01 12:00:00",
        )
        assert saved_duplicate["inserted"] is False
        assert len(history.get_history()) == 1
    finally:
        history.db.connection.close()


def test_legacy_save_signature_remains_valid(tmp_path, analysis_factory):
    history = make_history(tmp_path)
    decision = {"decision": "🟡 Esperar confirmación"}
    try:
        saved = history.save(
            "ETHUSDT",
            analysis_factory(),
            decision,
            {"score": 60},
            {"level": "Medio"},
        )
        assert saved["decision"] == decision["decision"]
        assert saved["timeframe"] == "1h"
        assert saved["inserted"] is True
    finally:
        history.db.connection.close()


def test_history_accepts_injected_path_and_context_manager(tmp_path):
    path = tmp_path / "context-history.db"
    with SignalHistory(database_name=path) as history:
        connection = history.db.connection
        assert history.get_history() == []

    try:
        connection.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        pass
    else:
        raise AssertionError("SignalHistory.__exit__ debe cerrar la conexión")


def test_history_rejects_database_and_database_name_together(tmp_path):
    database = make_database(tmp_path / "one.db")
    try:
        try:
            SignalHistory(database=database, database_name=tmp_path / "two.db")
        except ValueError as error:
            assert "not both" in str(error)
        else:
            raise AssertionError("Debe rechazar dos fuentes de base simultáneas")
    finally:
        database.close()

