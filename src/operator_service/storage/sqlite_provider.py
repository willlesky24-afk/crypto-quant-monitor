from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from src.ai_agent.models import MarketContext
from src.operator_service.interfaces import BaseMarketContextProvider
from src.operator_service.storage.models import market_context_from_dict
from src.operator_service.storage.repository import BaseMarketContextRepository

logger = logging.getLogger(__name__)


class SQLiteMarketContextRepository(BaseMarketContextRepository):
    """Thread-safe SQLite-backed repository for MarketContext snapshots.

    Features:
    - Supports on-disk file paths and in-memory databases (:memory:).
    - Uses WAL (Write-Ahead Logging) mode on file databases for concurrent read performance.
    - Safe for multi-threaded access using a reentrant thread lock and check_same_thread=False.
    - Index optimized for latest snapshot and historical range queries.
    - Payload serialization with structured column indexing for fast filtering.
    """

    SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS market_contexts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        timeframe TEXT NOT NULL,
        candle_timestamp TEXT NOT NULL,
        price REAL NOT NULL,
        regime TEXT NOT NULL,
        action TEXT NOT NULL,
        direction TEXT NOT NULL,
        quant_score REAL NOT NULL,
        predictive_score REAL NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(symbol, timeframe, candle_timestamp)
    );

    CREATE INDEX IF NOT EXISTS idx_mc_symbol_tf_ts 
    ON market_contexts(symbol, timeframe, candle_timestamp DESC);
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        """Initialize SQLite context repository.

        Args:
            db_path: Path to SQLite file or ':memory:' for transient storage.
        """
        self._db_path = str(db_path)
        self._lock = threading.RLock()
        self._is_closed = False

        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            timeout=30.0,
            isolation_level=None,  # autocommit mode
        )
        self._conn.row_factory = sqlite3.Row

        self._initialize_database()

    def _initialize_database(self) -> None:
        with self._lock:
            cursor = self._conn.cursor()
            if self._db_path != ":memory:":
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.executescript(self.SCHEMA_SQL)

    def save_context(self, context: MarketContext) -> int:
        """Persist a MarketContext snapshot using an idempotent upsert."""
        with self._lock:
            if self._is_closed:
                raise RuntimeError("Cannot execute operation on closed repository.")

            symbol = context.symbol.strip().upper()
            timeframe = context.timeframe.strip().lower()
            candle_timestamp = str(context.timestamp)
            payload_json = json.dumps(context.to_dict(), default=str)
            created_at = datetime.now(timezone.utc).isoformat()

            sql = """
            INSERT INTO market_contexts (
                symbol, timeframe, candle_timestamp, price, regime,
                action, direction, quant_score, predictive_score,
                payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, timeframe, candle_timestamp) DO UPDATE SET
                price = excluded.price,
                regime = excluded.regime,
                action = excluded.action,
                direction = excluded.direction,
                quant_score = excluded.quant_score,
                predictive_score = excluded.predictive_score,
                payload_json = excluded.payload_json,
                created_at = excluded.created_at;
            """
            cursor = self._conn.cursor()
            cursor.execute(
                sql,
                (
                    symbol,
                    timeframe,
                    candle_timestamp,
                    context.current_price,
                    context.market_regime,
                    context.signal.action,
                    context.signal.direction,
                    context.quant_score,
                    context.predictive_score,
                    payload_json,
                    created_at,
                ),
            )
            return cursor.lastrowid or 0

    def get_latest_context(self, symbol: str, timeframe: str) -> MarketContext | None:
        """Retrieve the most recent closed candle MarketContext snapshot."""
        with self._lock:
            if self._is_closed:
                raise RuntimeError("Cannot execute operation on closed repository.")

            sym = symbol.strip().upper()
            tf = timeframe.strip().lower()

            sql = """
            SELECT payload_json FROM market_contexts
            WHERE symbol = ? AND timeframe = ?
            ORDER BY candle_timestamp DESC
            LIMIT 1;
            """
            cursor = self._conn.cursor()
            cursor.execute(sql, (sym, tf))
            row = cursor.fetchone()
            if not row:
                return None

            try:
                return market_context_from_dict(row["payload_json"])
            except Exception as exc:
                logger.error(
                    f"Corrupted MarketContext payload for {sym} {tf}: {exc}", exc_info=True
                )
                return None

    def get_context_history(
        self, symbol: str, timeframe: str, limit: int = 50
    ) -> list[MarketContext]:
        """Retrieve historical closed candle MarketContext snapshots descending by timestamp."""
        with self._lock:
            if self._is_closed:
                raise RuntimeError("Cannot execute operation on closed repository.")

            sym = symbol.strip().upper()
            tf = timeframe.strip().lower()

            sql = """
            SELECT payload_json FROM market_contexts
            WHERE symbol = ? AND timeframe = ?
            ORDER BY candle_timestamp DESC
            LIMIT ?;
            """
            cursor = self._conn.cursor()
            cursor.execute(sql, (sym, tf, max(1, limit)))
            rows = cursor.fetchall()

            contexts: list[MarketContext] = []
            for row in rows:
                try:
                    contexts.append(market_context_from_dict(row["payload_json"]))
                except Exception as exc:
                    logger.warning(f"Skipping corrupted history record for {sym} {tf}: {exc}")
            return contexts

    def get_available_symbols(self) -> list[str]:
        """Return distinct symbols currently saved in the repository."""
        with self._lock:
            if self._is_closed:
                raise RuntimeError("Cannot execute operation on closed repository.")

            sql = "SELECT DISTINCT symbol FROM market_contexts ORDER BY symbol ASC;"
            cursor = self._conn.cursor()
            cursor.execute(sql)
            return [str(row["symbol"]) for row in cursor.fetchall()]

    def get_available_timeframes(self, symbol: str) -> list[str]:
        """Return distinct timeframes available for a given symbol."""
        with self._lock:
            if self._is_closed:
                raise RuntimeError("Cannot execute operation on closed repository.")

            sym = symbol.strip().upper()
            sql = "SELECT DISTINCT timeframe FROM market_contexts WHERE symbol = ? ORDER BY timeframe ASC;"
            cursor = self._conn.cursor()
            cursor.execute(sql, (sym,))
            return [str(row["timeframe"]) for row in cursor.fetchall()]

    def count_records(self, symbol: str | None = None, timeframe: str | None = None) -> int:
        """Count the number of stored context records."""
        with self._lock:
            if self._is_closed:
                raise RuntimeError("Cannot execute operation on closed repository.")

            cursor = self._conn.cursor()
            if symbol and timeframe:
                sql = "SELECT COUNT(*) as cnt FROM market_contexts WHERE symbol = ? AND timeframe = ?;"
                cursor.execute(sql, (symbol.strip().upper(), timeframe.strip().lower()))
            elif symbol:
                sql = "SELECT COUNT(*) as cnt FROM market_contexts WHERE symbol = ?;"
                cursor.execute(sql, (symbol.strip().upper(),))
            elif timeframe:
                sql = "SELECT COUNT(*) as cnt FROM market_contexts WHERE timeframe = ?;"
                cursor.execute(sql, (timeframe.strip().lower(),))
            else:
                sql = "SELECT COUNT(*) as cnt FROM market_contexts;"
                cursor.execute(sql)

            row = cursor.fetchone()
            return int(row["cnt"]) if row else 0

    def close(self) -> None:
        """Close SQLite database connection safely."""
        with self._lock:
            if not self._is_closed:
                self._conn.close()
                self._is_closed = True


class SQLiteMarketContextProvider(BaseMarketContextProvider):
    """Persistent, drop-in replacement for InMemoryMarketContextProvider.

    Conforms directly to BaseMarketContextProvider:
    - async get_latest_context(symbol, timeframe)
    - async get_available_symbols()
    - update_context(context)

    Also provides:
    - async get_context_history(symbol, timeframe, limit)
    - async get_available_timeframes(symbol)
    - repository access
    """

    def __init__(
        self,
        repository: BaseMarketContextRepository | None = None,
        db_path: str | Path = ":memory:",
    ) -> None:
        """Initialize the persistent provider.

        Args:
            repository: Existing repository instance, or None to instantiate SQLiteMarketContextRepository.
            db_path: Target database path when repository is None.
        """
        self._repository = repository or SQLiteMarketContextRepository(db_path=db_path)

    @property
    def repository(self) -> BaseMarketContextRepository:
        """Access underlying repository instance."""
        return self._repository

    def update_context(self, context: MarketContext) -> None:
        """Store or update the closed candle MarketContext in the persistent database."""
        self._repository.save_context(context)

    async def get_latest_context(self, symbol: str, timeframe: str) -> MarketContext | None:
        """Retrieve the latest closed candle MarketContext for a given symbol and timeframe."""
        return self._repository.get_latest_context(symbol=symbol, timeframe=timeframe)

    async def get_available_symbols(self) -> list[str]:
        """Return list of distinct symbols currently tracked in the persistent storage."""
        return self._repository.get_available_symbols()

    async def get_available_timeframes(self, symbol: str) -> list[str]:
        """Return list of available timeframes for a given symbol."""
        return self._repository.get_available_timeframes(symbol=symbol)

    async def get_context_history(
        self, symbol: str, timeframe: str, limit: int = 50
    ) -> list[MarketContext]:
        """Retrieve historical closed candle MarketContext snapshots."""
        return self._repository.get_context_history(symbol=symbol, timeframe=timeframe, limit=limit)

    def close(self) -> None:
        """Close the underlying repository."""
        self._repository.close()
