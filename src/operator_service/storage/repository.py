from __future__ import annotations

from abc import ABC, abstractmethod

from src.ai_agent.models import MarketContext


class BaseMarketContextRepository(ABC):
    """Abstract interface for persisting and querying historical and latest MarketContext snapshots.

    Adheres strictly to the architectural constraints:
    - Infrastructure layer only.
    - No modification or recalculation of quantitative, predictive, or risk metrics.
    - Closed candle snapshots are stored immutably.
    """

    @abstractmethod
    def save_context(self, context: MarketContext) -> int:
        """Persist a MarketContext snapshot.

        If a snapshot for (symbol, timeframe, candle_timestamp) already exists,
        it should be replaced (upsert/idempotent update).

        Args:
            context: Immutable snapshot of closed candle T.

        Returns:
            Internal database row/record ID.
        """
        ...

    @abstractmethod
    def get_latest_context(self, symbol: str, timeframe: str) -> MarketContext | None:
        """Retrieve the most recent closed candle MarketContext for a symbol and timeframe.

        Args:
            symbol: Ticker symbol (e.g. 'BTCUSDT').
            timeframe: Candle interval (e.g. '1h').

        Returns:
            MarketContext instance if found, else None.
        """
        ...

    @abstractmethod
    def get_context_history(
        self, symbol: str, timeframe: str, limit: int = 50
    ) -> list[MarketContext]:
        """Retrieve historical closed candle MarketContext snapshots.

        Snapshots are ordered descending by candle timestamp (most recent first).

        Args:
            symbol: Ticker symbol.
            timeframe: Candle interval.
            limit: Maximum number of historical records to return.

        Returns:
            List of MarketContext instances.
        """
        ...

    @abstractmethod
    def get_available_symbols(self) -> list[str]:
        """Return distinct symbols currently saved in the repository."""
        ...

    @abstractmethod
    def get_available_timeframes(self, symbol: str) -> list[str]:
        """Return distinct timeframes available for a given symbol."""
        ...

    @abstractmethod
    def count_records(self, symbol: str | None = None, timeframe: str | None = None) -> int:
        """Count the number of stored context records, optionally filtered by symbol and timeframe."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Safely close underlying database connection and release resources."""
        ...
