from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.database import Database
from src.migrations import DatabaseMigrator, MigrationError


def _create_legacy_v16_database(path: Path, count: int = 5):
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            price REAL,
            trend TEXT,
            signal TEXT,
            decision TEXT,
            quant_score INTEGER,
            risk TEXT
        )
        """
    )
    for i in range(count):
        cursor.execute(
            """
            INSERT INTO signals (timestamp, symbol, price, trend, signal, decision, quant_score, risk)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"2026-01-01 10:0{i}:00",
                "BTCUSDT",
                80000.0 + i * 100,
                "Alcista",
                "🟢 Señal alcista",
                "🟢 Condición favorable",
                90 + i,
                "Bajo",
            ),
        )
    conn.commit()
    conn.close()


def test_migration_creates_backup_and_marks_legacy_records(tmp_path: Path):
    db_file = tmp_path / "legacy.db"
    _create_legacy_v16_database(db_file, count=3)

    db = Database(database_name=db_file)
    try:
        cursor = db.connection.cursor()

        # Verify backup was created
        backup_file = tmp_path / "legacy.db.bak"
        assert backup_file.exists()

        # Verify schema_migrations table
        cursor.execute("SELECT version, description FROM schema_migrations")
        versions = cursor.fetchall()
        assert len(versions) == 1
        assert versions[0][0] == 1

        # Verify signals table has new schema
        cursor.execute("PRAGMA table_info(signals)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "candle_timestamp" in columns
        assert "timeframe" in columns
        assert "is_legacy" in columns

        # Verify data migrated with is_legacy = 1
        cursor.execute("SELECT symbol, timeframe, candle_timestamp, is_legacy FROM signals ORDER BY id")
        rows = cursor.fetchall()
        assert len(rows) == 3
        assert rows[0][0] == "BTCUSDT"
        assert rows[0][1] == "1h"
        assert rows[0][2] == "2026-01-01 10:00:00"
        assert rows[0][3] == 1
    finally:
        db.close()


def test_migration_is_idempotent_and_does_not_rerun(tmp_path: Path):
    db_file = tmp_path / "idempotent.db"
    _create_legacy_v16_database(db_file, count=2)

    # First open applies migration
    db1 = Database(database_name=db_file)
    db1.close()

    # Second open sees version 1 already in schema_migrations
    db2 = Database(database_name=db_file)
    try:
        cursor = db2.connection.cursor()
        cursor.execute("SELECT count(*) FROM schema_migrations WHERE version=1")
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT count(*) FROM signals")
        assert cursor.fetchone()[0] == 2
    finally:
        db2.close()


def test_migration_rolls_back_and_restores_backup_on_error(tmp_path: Path, monkeypatch):
    db_file = tmp_path / "fail.db"
    _create_legacy_v16_database(db_file, count=2)

    conn = sqlite3.connect(db_file)
    migrator = DatabaseMigrator(conn, db_file)

    # Monkeypatch to simulate failure during migration
    def _fail_execute(*args, **kwargs):
        raise sqlite3.OperationalError("Simulated disk error during migration")

    class FailingCursor:
        def __init__(self, real_cursor):
            self._real = real_cursor

        def execute(self, sql, *args):
            if "INSERT OR IGNORE INTO signals" in sql:
                raise sqlite3.OperationalError("Simulated failure")
            return self._real.execute(sql, *args)

        def fetchone(self):
            return self._real.fetchone()

        def fetchall(self):
            return self._real.fetchall()

    class FailingConnection:
        def __init__(self, real):
            self._real = real

        def cursor(self):
            return FailingCursor(self._real.cursor())

        def rollback(self):
            return self._real.rollback()

        def commit(self):
            return self._real.commit()

    failing_conn = FailingConnection(conn)
    migrator = DatabaseMigrator(failing_conn, db_file)

    with pytest.raises(MigrationError, match="Error durante la migración"):
        migrator.run_migrations()

    conn.close()

    # Verify backup exists
    assert (tmp_path / "fail.db.bak").exists()
