from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class OperatorQuery:
    """Represents a question, request, or command submitted by the human operator."""

    query: str
    symbol: str = "BTCUSDT"
    timeframe: str = "1h"
    operator_id: str = "default_operator"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AnalysisRequest:
    """Explicit request for comprehensive market contextual breakdown."""

    symbol: str
    timeframe: str = "1h"
    focus_areas: tuple[str, ...] = ("regime", "quantitative", "predictive", "risk", "levels")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["focus_areas"] = list(self.focus_areas)
        return d


@dataclass(frozen=True)
class OperatorResponse:
    """Structured analytical response produced by the AI Quant Copilot.

    Strictly provides decision support and market interpretation.
    Never executes trades, modifies quantitative engine states, or creates order directives.
    """

    answer: str
    symbol: str
    timeframe: str
    market_regime: str
    quant_score: float
    predictive_score: float
    confidence: float
    key_drivers: tuple[str, ...] = field(default_factory=tuple)
    risk_factors: tuple[str, ...] = field(default_factory=tuple)
    scenarios: tuple[str, ...] = field(default_factory=tuple)
    disclaimer: str = (
        "DECISION SUPPORT ONLY: This analysis is an AI interpretation of quantitative "
        "signals for human operator review. No trading recommendations or execution actions."
    )
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["key_drivers"] = list(self.key_drivers)
        d["risk_factors"] = list(self.risk_factors)
        d["scenarios"] = list(self.scenarios)
        return d


@dataclass(frozen=True)
class AnalysisResponse:
    """Structured response for deep contextual analysis requests."""

    symbol: str
    timeframe: str
    current_price: float
    market_regime: str
    quant_score: float
    predictive_score: float
    technical_summary: str
    volume_analysis: str
    risk_assessment: str
    possible_scenarios: tuple[str, ...] = field(default_factory=tuple)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["possible_scenarios"] = list(self.possible_scenarios)
        return d