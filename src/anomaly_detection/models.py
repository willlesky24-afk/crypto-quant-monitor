from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AnomalyType(str, Enum):
    REGIME_CHANGE = "REGIME_CHANGE"
    VOLATILITY_EXPANSION = "VOLATILITY_EXPANSION"
    VOLUME_SURGE = "VOLUME_SURGE"
    SCORE_DIVERGENCE = "SCORE_DIVERGENCE"


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class MarketAlert:
    """Structured alert describing a detected market anomaly for human operator attention.

    Passively observes market states. Does NOT issue trading orders or actions.
    """

    alert_id: str
    anomaly_type: AnomalyType
    severity: AlertSeverity
    symbol: str
    timeframe: str
    headline: str
    reason: str
    current_value: float
    reference_value: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)
    disclaimer: str = "OBSERVATION ONLY: Anomaly detected for human review. No automated trading action."

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["anomaly_type"] = self.anomaly_type.value
        d["severity"] = self.severity.value
        return d