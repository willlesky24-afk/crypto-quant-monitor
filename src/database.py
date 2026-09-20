from __future__ import annotations

import sqlite3
from datetime import datetime

try:
    from .migrations import DatabaseMigrator
except ImportError:  # Streamlit execution with ``src`` on sys.path.
    from migrations import DatabaseMigrator

DATABASE_NAME = "signals.db"


class Database:
    def __init__(self, database_name=DATABASE_NAME):
        self.database_name = str(database_name)
        self.connection = sqlite3.connect(database_name)

        migrator = DatabaseMigrator(self.connection, self.database_name)
        migrator.run_migrations()

        self.create_tables()

    def create_tables(self):
        cursor = self.connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS signals (
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

        self.connection.commit()

    def insert_signal(self, data: dict) -> bool:
        cursor = self.connection.cursor()

        timeframe = data.get("timeframe", "1h")
        candle_timestamp = data.get(
            "candle_timestamp", data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        price = float(data["price"])
        open_p = float(data.get("open", price))
        high_p = float(data.get("high", price))
        low_p = float(data.get("low", price))
        close_p = float(data.get("close", price))
        volume = float(data.get("volume", 0.0))
        created_at = data.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        is_legacy = int(data.get("is_legacy", 0))

        cursor.execute(
            """
            INSERT OR IGNORE INTO signals (
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["symbol"],
                timeframe,
                str(candle_timestamp),
                price,
                open_p,
                high_p,
                low_p,
                close_p,
                volume,
                data["trend"],
                data["signal"],
                data["decision"],
                int(data["quant_score"]),
                data["risk"],
                created_at,
                is_legacy,
            ),
        )

        self.connection.commit()
        return cursor.rowcount > 0

    def get_recent_signals(self, limit=10):
        cursor = self.connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM signals
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

        return cursor.fetchall()

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False
