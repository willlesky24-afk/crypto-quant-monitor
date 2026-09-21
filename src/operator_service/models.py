from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.ai_agent.models import AgentExplanation, AgentMarketSummary


def _utc_now_iso() -> str:
    """Return current UTC timestamp formatted as ISO string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SignalExplanationRequest:
    """Request contract for retrieving the latest explanation of a quantitative signal."""

    symbol: str
    timeframe: str = "1h"
    include_metadata: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "timeframe", self.timeframe.strip().lower())

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class SignalExplanationResponse:
    """Response contract containing the structured explanation of a quantitative signal."""

    success: bool
    symbol: str
    timeframe: str
    explanation: AgentExplanation | None = None
    error: str | None = None
    timestamp: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "success": self.success,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "explanation": self.explanation.to_dict() if self.explanation is not None else None,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class MarketSummaryRequest:
    """Request contract for retrieving a structured market intelligence summary."""

    symbol: str
    timeframe: str = "1h"

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "timeframe", self.timeframe.strip().lower())

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class MarketSummaryResponse:
    """Response contract containing the structured market intelligence summary."""

    success: bool
    symbol: str
    timeframe: str
    summary: AgentMarketSummary | None = None
    error: str | None = None
    timestamp: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "success": self.success,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "summary": self.summary.to_dict() if self.summary is not None else None,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class OperatorServiceHealthResponse:
    """Response contract for operator service health and capability status."""

    status: str
    available_symbols: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return asdict(self)
