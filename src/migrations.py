from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


class MigrationError(RuntimeError):
    """Raised when a database migration fails."""


class DatabaseMigrator:
    """Handles safe, transactional SQLite schema migrations with automatic backup,

    count validation, rollback, and version tracking.
    """

    CURRENT_VERSION = 1

    def __init__(self, connection: sqlite3.Connection, database_name: str | Path = "signals.db"):
        self.connection = connection
        self.database_name = str(database_name)

    def is_memory_db(self) -> bool:
        return (
            self.database_name == ":memory:"
            or "mode=memory" in self.database_name
            or self.database_name.startswith("file::memory:")
        )

    def _ensure_version_table(self):
        cursor = self.connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL,
                description TEXT NOT NULL
            )
            """
        )
        self.connection.commit()

    def get_applied_versions(self) -> set[int]:
        self._ensure_version_table()
        cursor = self.connection.cursor()
        cursor.execute("SELECT version FROM schema_migrations")
        return {row[0] for row in cursor.fetchall()}

    def _create_backup(self) -> str | None:
        if self.is_memory_db():
            return None

        db_path = Path(self.database_name)
        if not db_path.exists() or db_path.stat().st_size == 0:
            return None

        backup_path = f"{self.database_name}.bak"
        shutil.copy2(self.database_name, backup_path)
        return backup_path

    def _restore_backup(self, backup_path: str | None):
        if backup_path and os.path.exists(backup_path):
            shutil.copy2(backup_path, self.database_name)

    def run_migrations(self):
        self._ensure_version_table()
        applied = self.get_applied_versions()

        if 1 not in applied:
            self._migrate_to_v1()

    def _migrate_to_v1(self):
        cursor = self.connection.cursor()

        # Check if legacy signals table exists
        cursor.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='signals'"
        )
        signals_exists = cursor.fetchone()[0] > 0

        if not signals_exists:
            # Fresh database, no data migration needed
            self._record_version(1, "Initial v1.5 Quant Integrity schema")
            return

        cursor.execute("PRAGMA table_info(signals)")
        columns = [row[1] for row in cursor.fetchall()]

        # If it already has candle_timestamp and is_legacy, mark as applied and return
        if "candle_timestamp" in columns and "is_legacy" in columns:
            self._record_version(1, "v1.5 schema already active")
            return

        # Legacy v1.6 table detected. Perform transactional migration.
        backup_path = self._create_backup()

        try:
            cursor.execute("BEGIN TRANSACTION")

            # Rename legacy table
            cursor.execute("ALTER TABLE signals RENAME TO _signals_old_v16")

            # Count existing records
            cursor.execute("SELECT count(*) FROM _signals_old_v16")
            old_count = cursor.fetchone()[0]

            # Create new table
            cursor.execute(
                """
                CREATE TABLE signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    candle_timestamp TEXT NOT NULL,
                    price REAL NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    trend TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    quant_score INTEGER NOT NULL,
                    risk TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_legacy INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(symbol, timeframe, candle_timestamp)
                )
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_signals_symbol_tf_candle
                ON signals(symbol, timeframe, candle_timestamp)
                """
            )

            # Migrate data: assign timeframe='1h', candle_timestamp=timestamp, is_legacy=1
            cursor.execute(
                """
                INSERT OR IGNORE INTO signals (
                    id,
                    symbol,
                    timeframe,
                    candle_timestamp,
                    price,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    trend,
                    signal,
                    decision,
                    quant_score,
                    risk,
                    created_at,
                    is_legacy
                )
                SELECT
                    id,
                    symbol,
                    '1h' AS timeframe,
                    timestamp AS candle_timestamp,
                    price,
                    price AS open,
                    price AS high,
                    price AS low,
                    price AS close,
                    0.0 AS volume,
                    trend,
                    signal,
                    decision,
                    quant_score,
                    risk,
                    timestamp AS created_at,
                    1 AS is_legacy
                FROM _signals_old_v16
                """
            )

            # Validate record count
            cursor.execute("SELECT count(*) FROM signals")
            new_count = cursor.fetchone()[0]

            if new_count < old_count:
                raise MigrationError(
                    f"Conteo de registros inconsistente: {new_count} nuevos vs {old_count} originales"
                )

            # Drop temporary backup table
            cursor.execute("DROP TABLE _signals_old_v16")

            # Record version
            now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """
                INSERT INTO schema_migrations (version, applied_at, description)
                VALUES (1, ?, 'v1.5 Quant Integrity: idempotent schema with legacy tagging')
                """,
                (now_iso,),
            )

            self.connection.commit()

        except Exception as error:
            self.connection.rollback()
            self._restore_backup(backup_path)
            raise MigrationError(f"Error durante la migración de esquema: {error}") from error

    def _record_version(self, version: int, description: str):
        cursor = self.connection.cursor()
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            INSERT OR IGNORE INTO schema_migrations (version, applied_at, description)
            VALUES (?, ?, ?)
            """,
            (version, now_iso, description),
        )
        self.connection.commit()
