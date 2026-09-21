from __future__ import annotations

from typing import Any

from src.ai_agent.interfaces import BaseAIProvider
from src.ai_agent.models import AgentExplanation, MarketContext


class SignalExplanationService:
    """Service that transforms quantitative MarketContext into structured, human-readable explanations.

    Adheres strictly to the architectural constraints:
    - Never creates or alters trading decisions.
    - Consumes exclusively existing MarketContext attributes.
    - Never recalculates indicators or scores.
    - Maintains deterministic and offline operation.
    """

    def __init__(self, provider: BaseAIProvider | None = None) -> None:
        """Initialize the explanation service.

        Args:
            provider: Optional AI provider (e.g. BaseAIProvider or MockAIProvider).
                      If omitted, explanations are generated via the built-in deterministic engine.
        """
        self._provider = provider

    @property
    def provider(self) -> BaseAIProvider | None:
        """Configured AI provider, if any."""
        return self._provider

    def explain(self, context: MarketContext) -> AgentExplanation:
        """Synchronously generate a structured, deterministic explanation of the quantitative signal.

        Args:
            context: Immutable snapshot of closed candle T quantitative state.

        Returns:
            Structured AgentExplanation containing summary, rationale, drivers, and risk notes.
        """
        action = context.signal.action
        direction = context.signal.direction
        symbol = context.symbol
        timeframe = context.timeframe
        price = context.current_price
        regime = context.market_regime
        quant_score = context.quant_score
        pred_score = context.predictive_score
        confidence = float(context.signal.confidence)

        # 1. Concise Summary
        if action in ("BUY", "SELL"):
            summary = (
                f"{action} signal identified for {symbol} ({timeframe}) with {direction} bias "
                f"at {price:,.2f} under {regime} regime."
            )
        else:
            summary = (
                f"WAIT condition for {symbol} ({timeframe}) at {price:,.2f} under {regime} regime; "
                f"awaiting clear market confirmation."
            )

        # 2. Detailed Quantitative Rationale
        rationale_parts = [
            f"Quantitative evaluation yielded a Quant Score of {quant_score:.1f}/100 "
            f"and a Predictive Score of {pred_score:.2f}."
        ]

        if context.signal.reasoning:
            rationale_parts.append(f"Signal engine rationale: {context.signal.reasoning}.")
        else:
            rationale_parts.append("Signal engine rationale: No explicit qualitative reason provided.")

        # Contextual regime explanation
        if regime == "TRENDING_BULL":
            rationale_parts.append(
                "The market is in an established bullish trend favoring continuation of upward momentum."
            )
        elif regime == "TRENDING_BEAR":
            rationale_parts.append(
                "The market is in an established bearish trend with downward pressure dominant."
            )
        elif regime == "RANGING_CONSOLIDATION":
            rationale_parts.append(
                "The market is consolidating in a range; caution is advised around support and resistance boundaries."
            )
        elif regime == "HIGH_VOLATILITY_EXPANSION":
            rationale_parts.append(
                "The market is undergoing volatility expansion with widening ranges and increased execution risk."
            )
        else:
            rationale_parts.append(f"The market regime is categorized as {regime}.")

        # Passive Volume Profile integration (without recalculating)
        poc = context.volume_profile.get("poc")
        if poc is not None and isinstance(poc, (int, float)):
            poc_val = float(poc)
            if price > poc_val:
                rationale_parts.append(
                    f"Price is currently trading above the high-volume node (POC at {poc_val:,.2f}), serving as potential support."
                )
            elif price < poc_val:
                rationale_parts.append(
                    f"Price is currently trading below the high-volume node (POC at {poc_val:,.2f}), presenting overhead resistance."
                )
            else:
                rationale_parts.append(f"Price is trading directly at the Point of Control (POC at {poc_val:,.2f}).")

        rationale = " ".join(rationale_parts)

        # 3. Key Drivers
        drivers: list[str] = []
        if context.signal.positives:
            drivers.extend(context.signal.positives)

        if context.signal.warnings:
            for w in context.signal.warnings:
                drivers.append(f"Caution: {w}")

        if not drivers:
            drivers.append(f"Regime: {regime}")
            drivers.append(f"Quant Score: {quant_score:.1f}/100")
            drivers.append(f"Predictive Score: {pred_score:.2f}")

        # 4. Structured Risk Assessment
        risk_parts = [
            f"Risk profile: {context.risk.risk_category or 'Standard'}."
        ]

        if context.risk.stop_loss is not None:
            risk_parts.append(f"Protective Stop Loss set at {context.risk.stop_loss:,.2f}.")
        if context.risk.take_profit is not None:
            risk_parts.append(f"Target Take Profit set at {context.risk.take_profit:,.2f}.")

        if context.risk.stop_loss is None and context.risk.take_profit is None:
            risk_parts.append("No explicit Stop Loss or Take Profit targets defined.")

        if context.risk.risk_ratio is not None:
            risk_parts.append(f"Risk/Reward ratio is calculated at {context.risk.risk_ratio:.2f}.")

        if context.risk.atr is not None:
            risk_parts.append(f"Local volatility measured by ATR is {context.risk.atr:,.2f}.")

        if context.risk.tp_multiplier is not None and context.risk.sl_multiplier is not None:
            risk_parts.append(
                f"Dynamic ATR bounds: {context.risk.tp_multiplier:.1f}x TP / {context.risk.sl_multiplier:.1f}x SL."
            )

        risk_assessment = " ".join(risk_parts)

        # 5. Metadata
        meta: dict[str, Any] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": str(context.timestamp),
            "regime": regime,
            "action": action,
            "direction": direction,
            "deterministic": True,
            "service": "SignalExplanationService",
        }
        if context.metadata:
            meta["context_metadata"] = dict(context.metadata)

        return AgentExplanation(
            summary=summary,
            rationale=rationale,
            key_drivers=tuple(drivers),
            risk_assessment=risk_assessment,
            confidence=confidence,
            raw_response="[DETERMINISTIC_EXPLANATION: SignalExplanationService]",
            metadata=meta,
        )

    async def explain_async(self, context: MarketContext) -> AgentExplanation:
        """Asynchronously generate a structured explanation.

        If an external AI provider was injected, delegates to `provider.generate_explanation(context)`.
        Otherwise, falls back to the deterministic in-process engine.
        """
        if self._provider is not None:
            return await self._provider.generate_explanation(context)
        return self.explain(context)
