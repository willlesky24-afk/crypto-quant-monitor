from __future__ import annotations

from abc import ABC, abstractmethod

from src.operator_memory.models import MemoryEntry


class BaseOperatorMemory(ABC):
    """Abstract interface defining memory persistence for the AI Quant Copilot."""

    @abstractmethod
    async def add_entry(
        self,
        entry_type: str,
        symbol: str,
        content: str,
        operator_id: str = "default_operator",
        metadata: dict | None = None,
    ) -> MemoryEntry:
        """Add a memory entry with automatic credential sanitization."""
        ...

    @abstractmethod
    async def get_recent_entries(
        self,
        symbol: str | None = None,
        entry_type: str | None = None,
        operator_id: str = "default_operator",
        limit: int = 20,
    ) -> list[MemoryEntry]:
        """Retrieve recent entries matching filters."""
        ...

    @abstractmethod
    async def search_memory(
        self,
        query: str,
        operator_id: str = "default_operator",
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Search memory entries by textual keyword."""
        ...

    @abstractmethod
    async def clear(self, operator_id: str | None = None) -> int:
        """Clear memory entries."""
        ...