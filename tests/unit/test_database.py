from __future__ import annotations

import inspect
from pathlib import Path

from src.database import Database


def make_database(path: Path) -> Database:
    parameters = inspect.signature(Database).parameters
    if "db_path" in parameters:
        return Database(db_path=path)
    if "database_name" in parameters:
        return Database(database_name=path)
    if "path" in parameters:
        return Database(path=path)
    raise AssertionError("Database debe aceptar una ruta de base inyectada")


def signal_row(index: int) -> dict:
    return {
        "timestamp": f"2025-01-01 00:00:0{index}",
        "symbol": "BTCUSDT",
        "price": 100.0 + index,
        "trend": "Alcista",
        "signal": "🟢 Señal alcista",
        "decision": "🟢 Condición favorable",
        "quant_score": 90,
        "risk": "Bajo",
    }


def test_database_uses_injected_path_and_honors_recent_limit(tmp_path: Path):
    db_path = tmp_path / "signals-test.db"
    db = make_database(db_path)
    try:
        for index in range(3):
            db.insert_signal(signal_row(index))
        rows = db.get_recent_signals(limit=2)
        assert len(rows) == 2
        assert [row[3] for row in rows] == [102.0, 101.0]
        assert db_path.exists()
    finally:
        db.connection.close()


def test_database_schema_is_v16_compatible(tmp_path: Path):
    db = make_database(tmp_path / "schema.db")
    try:
        columns = [
            row[1]
            for row in db.connection.execute("PRAGMA table_info(signals)").fetchall()
        ]
        assert columns == [
            "id",
            "timestamp",
            "symbol",
            "price",
            "trend",
            "signal",
            "decision",
            "quant_score",
            "risk",
        ]
    finally:
        db.connection.close()


def test_database_context_manager_closes_connection(tmp_path: Path):
    with make_database(tmp_path / "context.db") as db:
        db.insert_signal(signal_row(1))
        connection = db.connection

    import sqlite3

    try:
        connection.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        pass
    else:
        raise AssertionError("Database.__exit__ debe cerrar la conexión")
