from __future__ import annotations

import pytest

from src.operator_memory.models import MemoryEntry
from src.operator_memory.sqlite_memory import SQLiteOperatorMemory


def test_memory_entry_credential_sanitization():
    raw_text = "Checking BTC key api_key: 'abcdef1234567890' with secret: 'super_secret_value'"
    sanitized = MemoryEntry.sanitize_content(raw_text)

    assert "abcdef1234567890" not in sanitized
    assert "super_secret_value" not in sanitized
    assert "[REDACTED_SENSITIVE_CREDENTIAL]" in sanitized


@pytest.mark.anyio
async def test_sqlite_memory_lifecycle():
    mem = SQLiteOperatorMemory(db_path=":memory:")

    entry1 = await mem.add_entry(
        entry_type="query",
        symbol="BTCUSDT",
        content="What is the current BTC regime?",
        operator_id="trader_1",
    )
    assert entry1.symbol == "BTCUSDT"
    assert entry1.entry_type == "query"

    entry2 = await mem.add_entry(
        entry_type="note",
        symbol="BTCUSDT",
        content="Support held firmly at 62k; watch for breakout.",
        operator_id="trader_1",
    )
    assert entry2.entry_type == "note"

    # Query recent
    entries = await mem.get_recent_entries(operator_id="trader_1")
    assert len(entries) == 2

    # Filter by symbol
    btc_entries = await mem.get_recent_entries(symbol="BTCUSDT", operator_id="trader_1")
    assert len(btc_entries) == 2

    # Filter by entry_type
    note_entries = await mem.get_recent_entries(entry_type="note", operator_id="trader_1")
    assert len(note_entries) == 1

    # Search keyword
    searched = await mem.search_memory(query="breakout", operator_id="trader_1")
    assert len(searched) == 1
    assert "breakout" in searched[0].content

    # Clear memory for specific operator
    deleted = await mem.clear(operator_id="trader_1")
    assert deleted == 2
    rem = await mem.get_recent_entries(operator_id="trader_1")
    assert len(rem) == 0

    # Clear all memories globally
    await mem.add_entry(entry_type="note", symbol="ETHUSDT", content="Test note")
    all_deleted = await mem.clear(operator_id=None)
    assert all_deleted == 1

