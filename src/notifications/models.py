from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

import pandas as pd


class NotificationChannelType(str, Enum):
    """Supported notification delivery channels."""

    DISCORD = "DISCORD"
    TELEGRAM = "TELEGRAM"
    WEBHOOK = "WEBHOOK"
    LOG = "LOG"


class NotificationPriority(str, Enum):
    """Priority levels for message routing and alert urgency."""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class SignalEvent:
    """Central event contract and single source of truth for trading decisions.

    Emitted strictly upon the completion of closed candle T.
    Consumed by notifications, dashboards, backtesters, and persistence layers.
    """

    timestamp: pd.Timestamp
    symbol: str
    timeframe: str
    action: str  # "BUY", "SELL", "WAIT"
    direction: str  # "LONG", "SHORT", "NEUTRAL"
    confidence: float  # 0.0 to 1.0
    predictive_score: float  # 0.0 to 1.0
    regime: str  # e.g., "TRENDING_BULL", "RANGING_CONSOLIDATION"
    reasoning: str
    price: float
    quant_score: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert the signal event to a JSON-serializable dictionary."""
        d = asdict(self)
        d["timestamp"] = str(self.timestamp)
        return d

    @classmethod
    def from_decision(
        cls,
        decision_result: Any,
        candle: dict[str, Any] | pd.Series,
        symbol: str,
        timeframe: str,
        signal_id: str | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SignalEvent:
        """Factory method to build a SignalEvent from a DecisionResult and candle data."""
        ts = candle.get("timestamp") if isinstance(candle, dict) else candle["timestamp"]
        if not isinstance(ts, pd.Timestamp):
            ts = pd.to_datetime(ts)

        close_price = float(candle.get("close") if isinstance(candle, dict) else candle["close"])
        action_val = str(getattr(decision_result, "decision", "WAIT"))
        direction_val = str(getattr(decision_result, "direction", "NEUTRAL"))
        conf_val = float(getattr(decision_result, "confidence", 0.0))
        pred_score_val = float(getattr(decision_result, "predictive_score", 0.0))
        regime_val = str(getattr(decision_result, "regime", "UNKNOWN"))
        reasoning_val = str(getattr(decision_result, "reasoning", ""))
        tech_score_val = float(getattr(decision_result, "technical_score", 0.0))

        extra_meta = dict(metadata or {})
        if hasattr(decision_result, "positives"):
            extra_meta["positives"] = list(decision_result.positives)
        if hasattr(decision_result, "warnings"):
            extra_meta["warnings"] = list(decision_result.warnings)

        return cls(
            timestamp=ts,
            symbol=symbol.strip().upper(),
            timeframe=timeframe.strip().lower(),
            action=action_val,
            direction=direction_val,
            confidence=conf_val,
            predictive_score=pred_score_val,
            regime=regime_val,
            reasoning=reasoning_val,
            price=close_price,
            quant_score=tech_score_val,
            stop_loss=stop_loss,
            take_profit=take_profit,
            signal_id=signal_id or str(uuid.uuid4())[:8],
            metadata=extra_meta,
        )


@dataclass(frozen=True)
class NotificationPayload:
    """Normalized message payload prepared for multi-channel dispatch."""

    event_id: str
    timestamp: pd.Timestamp
    symbol: str
    timeframe: str
    action: str
    direction: str
    price: float
    confidence: float
    predictive_score: float
    regime: str
    priority: NotificationPriority
    summary: str
    reasoning: str
    quant_score: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_reward_ratio: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to a JSON-serializable dictionary."""
        d = asdict(self)
        d["timestamp"] = str(self.timestamp)
        d["priority"] = self.priority.value
        return d

    @classmethod
    def from_signal_event(
        cls,
        event: SignalEvent,
        priority: NotificationPriority | None = None,
        custom_summary: str | None = None,
    ) -> NotificationPayload:
        """Derive a normalized notification payload directly from a SignalEvent."""
        # Calculate risk/reward ratio if SL and TP are defined
        rr_ratio: float | None = None
        if event.stop_loss is not None and event.take_profit is not None:
            risk = abs(event.price - event.stop_loss)
            reward = abs(event.take_profit - event.price)
            if risk > 1e-6:
                rr_ratio = round(reward / risk, 2)

        # Automatic priority assignment if not provided
        if priority is None:
            if event.action in ("BUY", "SELL") and event.confidence >= 0.75:
                prio = NotificationPriority.HIGH
            elif event.action in ("BUY", "SELL"):
                prio = NotificationPriority.NORMAL
            else:
                prio = NotificationPriority.LOW
        else:
            prio = priority

        summary_text = (
            custom_summary
            or f"[{event.symbol} {event.timeframe}] {event.action} ({event.direction}) @ {event.price:.2f}"
        )

        return cls(
            event_id=event.signal_id,
            timestamp=event.timestamp,
            symbol=event.symbol,
            timeframe=event.timeframe,
            action=event.action,
            direction=event.direction,
            price=event.price,
            confidence=event.confidence,
            predictive_score=event.predictive_score,
            regime=event.regime,
            priority=prio,
            summary=summary_text,
            reasoning=event.reasoning,
            quant_score=event.quant_score,
            stop_loss=event.stop_loss,
            take_profit=event.take_profit,
            risk_reward_ratio=rr_ratio,
            metadata=dict(event.metadata),
        )


@dataclass(frozen=True)
class NotificationResult:
    """Outcome of a dispatch attempt to a specific notification channel."""

    success: bool
    channel: NotificationChannelType
    status_code: int | None = None
    error_message: str | None = None
    delivered_at: pd.Timestamp | None = None
    retry_count: int = 0
    event_id: str = ""
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert dispatch result to a JSON-serializable dictionary."""
        d = asdict(self)
        d["channel"] = self.channel.value
        d["delivered_at"] = str(self.delivered_at) if self.delivered_at is not None else None
        d["latency_ms"] = self.latency_ms
        return d

