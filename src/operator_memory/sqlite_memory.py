from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.operator_memory.interfaces import BaseOperatorMemory
from src.operator_memory.models import MemoryEntry


class SQLiteOperatorMemory(BaseOperatorMemory):
    """Thread-safe SQLite-backed operator memory store.

    Stores conversation queries, operator notes, and asset observations.
    Excludes private keys, API secrets, and sensitive credentials via sanitization.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return self._conn


    def _init_db(self) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS operator_memory (
                    id TEXT PRIMARY KEY,
                    entry_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    content TEXT NOT NULL,
                    operator_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_op_memory_symbol ON operator_memory(symbol)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_op_memory_op_id ON operator_memory(operator_id)"
            )
            conn.commit()

    async def add_entry(
        self,
        entry_type: str,
        symbol: str,
        content: str,
        operator_id: str = "default_operator",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        sanitized = MemoryEntry.sanitize_content(content)
        entry_id = f"mem-{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        meta = metadata or {}

        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO operator_memory (id, entry_type, symbol, content, operator_id, timestamp, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    entry_type.strip().lower(),
                    symbol.strip().upper(),
                    sanitized,
                    operator_id.strip(),
                    now_iso,
                    json.dumps(meta),
                ),
            )
            conn.commit()

        return MemoryEntry(
            id=entry_id,
            entry_type=entry_type.strip().lower(),
            symbol=symbol.strip().upper(),
            content=sanitized,
            operator_id=operator_id.strip(),
            timestamp=now_iso,
            metadata=meta,
        )

    async def get_recent_entries(
        self,
        symbol: str | None = None,
        entry_type: str | None = None,
        operator_id: str = "default_operator",
        limit: int = 20,
    ) -> list[MemoryEntry]:
        query = "SELECT * FROM operator_memory WHERE operator_id = ?"
        params: list[Any] = [operator_id.strip()]

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol.strip().upper())
        if entry_type:
            query += " AND entry_type = ?"
            params.append(entry_type.strip().lower())

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        entries: list[MemoryEntry] = []
        for r in rows:
            meta = json.loads(r["metadata_json"]) if r["metadata_json"] else {}
            entries.append(
                MemoryEntry(
                    id=r["id"],
                    entry_type=r["entry_type"],
                    symbol=r["symbol"],
                    content=r["content"],
                    operator_id=r["operator_id"],
                    timestamp=r["timestamp"],
                    metadata=meta,
                )
            )
        return entries

    async def search_memory(
        self,
        query: str,
        operator_id: str = "default_operator",
        limit: int = 10,
    ) -> list[MemoryEntry]:
        sql = (
            "SELECT * FROM operator_memory WHERE operator_id = ? AND content LIKE ? "
            "ORDER BY timestamp DESC LIMIT ?"
        )
        params = [operator_id.strip(), f"%{query.strip()}%", limit]

        with self._lock, self._get_connection() as conn:
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()

        entries: list[MemoryEntry] = []
        for r in rows:
            meta = json.loads(r["metadata_json"]) if r["metadata_json"] else {}
            entries.append(
                MemoryEntry(
                    id=r["id"],
                    entry_type=r["entry_type"],
                    symbol=r["symbol"],
                    content=r["content"],
                    operator_id=r["operator_id"],
                    timestamp=r["timestamp"],
                    metadata=meta,
                )
            )
        return entries

    async def clear(self, operator_id: str | None = None) -> int:
        with self._lock, self._get_connection() as conn:
            if operator_id:
                cursor = conn.execute(
                    "DELETE FROM operator_memory WHERE operator_id = ?",
                    (operator_id.strip(),),
                )
            else:
                cursor = conn.execute("DELETE FROM operator_memory")
            count = cursor.rowcount
            conn.commit()
            return count