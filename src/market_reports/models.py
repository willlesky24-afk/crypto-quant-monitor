from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class DailyBriefingReport:
    """Comprehensive daily market intelligence briefing for human operators."""

    report_id: str
    symbol: str
    timeframe: str
    timestamp: str
    market_overview: str
    current_regime: str
    quant_score: float
    predictive_score: float
    strongest_signals: tuple[str, ...]
    main_risks: tuple[str, ...]
    important_levels: dict[str, Any]
    volatility_analysis: str
    historical_context: str
    disclaimer: str = (
        "DECISION SUPPORT ONLY: Generated for human operator intelligence. "
        "Crypto Quant Monitor provides quantitative analysis, not automated trade execution."
    )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["strongest_signals"] = list(self.strongest_signals)
        d["main_risks"] = list(self.main_risks)
        return d


@dataclass(frozen=True)
class IntradayUpdateReport:
    """Delta / change-oriented market report explaining recent shifts."""

    report_id: str
    symbol: str
    timeframe: str
    timestamp: str
    what_changed: str
    why_it_changed: str
    what_to_monitor: tuple[str, ...]
    regime_shift: str | None = None
    price_delta_pct: float = 0.0
    score_delta: float = 0.0
    disclaimer: str = "DECISION SUPPORT ONLY: Interpretive delta analysis for operator review."

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["what_to_monitor"] = list(self.what_to_monitor)
        return d