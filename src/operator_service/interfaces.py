from __future__ import annotations

from abc import ABC, abstractmethod

from src.ai_agent.models import MarketContext
from src.operator_service.models import (
    MarketSummaryRequest,
    MarketSummaryResponse,
    OperatorServiceHealthResponse,
    SignalExplanationRequest,
    SignalExplanationResponse,
)


class BaseMarketContextProvider(ABC):
    """Abstract interface for retrieving existing quantitative MarketContext snapshots.

    This provider is strictly read-only and does not generate signals or indicators.
    """

    @abstractmethod
    async def get_latest_context(self, symbol: str, timeframe: str) -> MarketContext | None:
        """Retrieve the latest closed candle MarketContext for a given symbol and timeframe.

        Args:
            symbol: Ticker symbol (e.g., 'BTCUSDT').
            timeframe: Candle timeframe interval (e.g., '1h').

        Returns:
            MarketContext instance if available, otherwise None.
        """
        ...

    @abstractmethod
    async def get_available_symbols(self) -> list[str]:
        """Return list of distinct symbols currently tracked in the context provider."""
        ...


class InMemoryMarketContextProvider(BaseMarketContextProvider):
    """Thread-safe, in-memory repository of latest MarketContext snapshots.

    Acts as the bridging read-only adapter between the live streaming/quantitative engine
    and the operator service.
    """

    def __init__(self) -> None:
        self._contexts: dict[tuple[str, str], MarketContext] = {}

    def update_context(self, context: MarketContext) -> None:
        """Store or update the latest closed candle MarketContext for (symbol, timeframe).

        Args:
            context: Immutable snapshot of closed candle T.
        """
        key = (context.symbol.strip().upper(), context.timeframe.strip().lower())
        self._contexts[key] = context

    async def get_latest_context(self, symbol: str, timeframe: str) -> MarketContext | None:
        """Retrieve the latest closed candle MarketContext."""
        key = (symbol.strip().upper(), timeframe.strip().lower())
        return self._contexts.get(key)

    async def get_available_symbols(self) -> list[str]:
        """Return distinct symbols registered in memory."""
        return sorted(list({sym for sym, _ in self._contexts.keys()}))


class BaseOperatorService(ABC):
    """Abstract interface defining the external-facing operator intelligence service."""

    @abstractmethod
    async def get_signal_explanation(
        self, request: SignalExplanationRequest
    ) -> SignalExplanationResponse:
        """Process an explanation request and return a structured explanation response."""
        ...

    @abstractmethod
    async def get_market_summary(
        self, request: MarketSummaryRequest
    ) -> MarketSummaryResponse:
        """Process a market summary request and return a structured summary response."""
        ...

    @abstractmethod
    async def health_check(self) -> OperatorServiceHealthResponse:
        """Check the operational status of the operator service and underlying components."""
        ...
