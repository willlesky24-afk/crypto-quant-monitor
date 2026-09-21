from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.ai_agent.models import MarketContext, RiskMetrics, SignalInfo


@dataclass(frozen=True)
class MarketContextRecord:
    """Represents a database row record of a stored MarketContext snapshot."""

    id: int | None
    symbol: str
    timeframe: str
    candle_timestamp: str
    price: float
    regime: str
    action: str
    direction: str
    quant_score: float
    predictive_score: float
    payload_json: str
    created_at: str


def market_context_from_dict(data: dict[str, Any] | str) -> MarketContext:
    """Reconstruct an immutable MarketContext instance from a dictionary or JSON string.

    Properly deserializes nested SignalInfo and RiskMetrics, converting
    lists back to immutable tuples and ensuring all field types match.

    Args:
        data: Dictionary matching MarketContext.to_dict() or a serialized JSON string.

    Returns:
        Reconstructed immutable MarketContext instance.

    Raises:
        ValueError: If data cannot be parsed or required fields are missing/corrupted.
    """
    if isinstance(data, str):
        try:
            raw_dict = json.loads(data)
        except Exception as exc:
            raise ValueError(f"Failed to parse JSON payload: {exc}") from exc
    elif isinstance(data, dict):
        raw_dict = data
    else:
        raise ValueError(f"Expected dict or JSON string, got {type(data).__name__}")

    try:
        # Reconstruct SignalInfo
        signal_data = raw_dict.get("signal", {})
        positives = tuple(signal_data.get("positives", ()))
        warnings = tuple(signal_data.get("warnings", ()))
        signal = SignalInfo(
            action=str(signal_data.get("action", "WAIT")),
            direction=str(signal_data.get("direction", "NEUTRAL")),
            confidence=float(signal_data.get("confidence", 0.0)),
            reasoning=str(signal_data.get("reasoning", "")),
            positives=positives,
            warnings=warnings,
        )

        # Reconstruct RiskMetrics
        risk_data = raw_dict.get("risk", {})
        risk = RiskMetrics(
            stop_loss=float(risk_data["stop_loss"]) if risk_data.get("stop_loss") is not None else None,
            take_profit=float(risk_data["take_profit"]) if risk_data.get("take_profit") is not None else None,
            risk_ratio=float(risk_data["risk_ratio"]) if risk_data.get("risk_ratio") is not None else None,
            risk_category=str(risk_data.get("risk_category", "")),
            atr=float(risk_data["atr"]) if risk_data.get("atr") is not None else None,
            tp_multiplier=float(risk_data["tp_multiplier"]) if risk_data.get("tp_multiplier") is not None else None,
            sl_multiplier=float(risk_data["sl_multiplier"]) if risk_data.get("sl_multiplier") is not None else None,
        )

        # Parse timestamp safely
        ts_val = raw_dict.get("timestamp")
        timestamp = pd.Timestamp(ts_val)

        return MarketContext(
            timestamp=timestamp,
            symbol=str(raw_dict["symbol"]).strip().upper(),
            timeframe=str(raw_dict["timeframe"]).strip().lower(),
            current_price=float(raw_dict.get("current_price", 0.0)),
            market_regime=str(raw_dict.get("market_regime", "UNKNOWN")),
            predictive_score=float(raw_dict.get("predictive_score", 0.0)),
            quant_score=float(raw_dict.get("quant_score", 0.0)),
            signal=signal,
            risk=risk,
            technical_indicators=dict(raw_dict.get("technical_indicators", {})),
            volume_profile=dict(raw_dict.get("volume_profile", {})),
            metadata=dict(raw_dict.get("metadata", {})),
        )
    except Exception as exc:
        raise ValueError(f"Invalid MarketContext payload structure: {exc}") from exc
