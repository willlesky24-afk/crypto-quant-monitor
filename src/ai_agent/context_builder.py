from __future__ import annotations

from typing import Any

import pandas as pd

from src.ai_agent.models import MarketContext, RiskMetrics, SignalInfo
from src.notifications.models import SignalEvent


class ContextBuilder:
    """Builder that consolidates quantitative engine outputs into an immutable MarketContext.

    Adheres strictly to the architectural constraints:
    - Consumes existing quantitative outputs only (SignalEvent is the primary source of truth).
    - Never calculates new indicators or alters signals.
    - Preserves zero look-ahead bias (operates strictly on closed candle T data).
    """

    @classmethod
    def build_from_signal_event(
        cls,
        signal_event: SignalEvent,
        market_report: dict[str, Any] | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> MarketContext:
        """Primary construction path: build MarketContext directly from a SignalEvent.

        Args:
            signal_event: The single source of truth produced on closed candle T.
            market_report: Optional descriptive market report dictionary for supplemental metadata.
            extra_metadata: Optional supplemental contextual key-values.

        Returns:
            An immutable MarketContext instance ready for AI interpretation.
        """
        meta = dict(signal_event.metadata)
        if extra_metadata:
            meta.update(extra_metadata)

        # 1. Signal Information
        positives_raw = meta.get("positives", [])
        warnings_raw = meta.get("warnings", [])
        if not positives_raw and market_report:
            positives_raw = market_report.get("decision", {}).get("positives", [])
        if not warnings_raw and market_report:
            warnings_raw = market_report.get("decision", {}).get("warnings", [])

        signal_info = SignalInfo(
            action=signal_event.action,
            direction=signal_event.direction,
            confidence=float(signal_event.confidence),
            reasoning=str(signal_event.reasoning),
            positives=tuple(str(p) for p in positives_raw),
            warnings=tuple(str(w) for w in warnings_raw),
        )

        # 2. Risk Metrics & Ratio
        sl = signal_event.stop_loss
        tp = signal_event.take_profit
        price = float(signal_event.price)

        risk_ratio: float | None = None
        if sl is not None and tp is not None and price > 0:
            risk_dist = abs(price - sl)
            reward_dist = abs(tp - price)
            if risk_dist > 1e-9:
                risk_ratio = round(reward_dist / risk_dist, 4)

        risk_cat = str(meta.get("risk_category", ""))
        if not risk_cat and market_report:
            if isinstance(market_report.get("risk"), str):
                risk_cat = market_report["risk"]
            elif isinstance(market_report.get("risk_engine"), dict):
                risk_cat = str(market_report["risk_engine"].get("risk", ""))

        atr_val = meta.get("atr")
        if atr_val is None and market_report and "volatility" in market_report:
            atr_val = market_report.get("volatility", {}).get("atr")

        risk_metrics = RiskMetrics(
            stop_loss=sl,
            take_profit=tp,
            risk_ratio=risk_ratio,
            risk_category=risk_cat,
            atr=float(atr_val) if atr_val is not None else None,
            tp_multiplier=float(meta["tp_multiplier"]) if "tp_multiplier" in meta and meta["tp_multiplier"] is not None else None,
            sl_multiplier=float(meta["sl_multiplier"]) if "sl_multiplier" in meta and meta["sl_multiplier"] is not None else None,
        )

        # 3. Volume Profile Snapshot
        vol_prof: dict[str, Any] = {}
        for key in ("poc", "vah", "val"):
            if key in meta:
                vol_prof[key] = meta[key]

        if market_report and "profile" in market_report and isinstance(market_report["profile"], dict):
            for k, v in market_report["profile"].items():
                if k not in vol_prof:
                    vol_prof[k] = v

        # 4. Technical Indicators Snapshot (passive capture, no calculation)
        tech_indicators: dict[str, Any] = {}
        if market_report:
            for section in ("trend", "momentum", "volatility", "volume"):
                val = market_report.get(section)
                if val is not None:
                    tech_indicators[section] = val

        for k, v in meta.items():
            if k in ("rsi", "ema_50", "ema_200", "p_continuation", "p_reversal", "market_state"):
                tech_indicators[k] = v

        return MarketContext(
            timestamp=signal_event.timestamp,
            symbol=signal_event.symbol,
            timeframe=signal_event.timeframe,
            current_price=price,
            market_regime=signal_event.regime,
            predictive_score=float(signal_event.predictive_score),
            quant_score=float(signal_event.quant_score),
            signal=signal_info,
            risk=risk_metrics,
            technical_indicators=tech_indicators,
            volume_profile=vol_prof,
            metadata=meta,
        )

    @classmethod
    def build_from_decision(
        cls,
        decision_result: Any,
        candle: pd.Series | dict[str, Any],
        symbol: str,
        timeframe: str,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        market_report: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MarketContext:
        """Utility/testing path: builds MarketContext by routing through SignalEvent.from_decision.

        Preserves SignalEvent as the single source of truth.
        """
        signal_event = SignalEvent.from_decision(
            decision_result=decision_result,
            candle=candle,
            symbol=symbol,
            timeframe=timeframe,
            stop_loss=stop_loss,
            take_profit=take_profit,
            metadata=metadata,
        )
        return cls.build_from_signal_event(
            signal_event=signal_event,
            market_report=market_report,
        )

    @classmethod
    def build_context(
        cls,
        signal_event: SignalEvent,
        technical_indicators: dict[str, Any] | None = None,
        volume_profile: dict[str, Any] | None = None,
        market_report: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MarketContext:
        """Convenience method building MarketContext from a SignalEvent with supplemental indicators."""
        meta = dict(metadata or {})
        if technical_indicators:
            meta["technical_indicators"] = technical_indicators
        if volume_profile:
            meta["volume_profile"] = volume_profile
        return cls.build_from_signal_event(
            signal_event=signal_event,
            market_report=market_report,
            extra_metadata=meta,
        )
