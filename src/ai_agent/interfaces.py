from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.ai_agent.models import AgentExplanation, AgentMarketSummary, MarketContext


class BaseAIProvider(ABC):
    """Abstract interface defining the contract for AI interpretation providers.

    All AI providers are consumer-only intelligence layers. They receive an immutable
    MarketContext and produce human-readable structured explanations and summaries.
    They must never generate trading signals, alter quantitative scores, or execute orders.
    """

    @abstractmethod
    async def generate_explanation(self, context: MarketContext) -> AgentExplanation:
        """Generate a detailed, contextual explanation of the current quantitative signal.

        Args:
            context: Immutable snapshot of closed candle T quantitative state.

        Returns:
            Structured AgentExplanation containing summary, rationale, drivers, and risk notes.
        """
        ...

    @abstractmethod
    async def summarize_market(self, context: MarketContext) -> AgentMarketSummary:
        """Generate a high-level briefing of the current market state and regime.

        Args:
            context: Immutable snapshot of closed candle T quantitative state.

        Returns:
            Structured AgentMarketSummary containing overview, regime analysis, and key levels.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check the operational readiness of the AI provider.

        Returns:
            True if the provider is available and ready to process requests, False otherwise.
        """
        ...


class MockAIProvider(BaseAIProvider):
    """Deterministic, offline mock AI provider for testing and baseline operations.

    Performs template-driven interpretation without external network calls, API keys,
    or quantitative calculations.
    """

    def __init__(self, name: str = "mock-provider", is_healthy: bool = True) -> None:
        self.name = name
        self._is_healthy = is_healthy

    async def generate_explanation(self, context: MarketContext) -> AgentExplanation:
        """Generate a deterministic template explanation based on the quantitative context."""
        action = context.signal.action
        direction = context.signal.direction
        regime = context.market_regime
        score = context.quant_score
        pred_score = context.predictive_score

        # Structured summary
        if action in ("BUY", "SELL"):
            summary = (
                f"{action} signal identified for {context.symbol} on {context.timeframe} "
                f"with {direction} bias under {regime} regime."
            )
        else:
            summary = (
                f"Neutral/Wait condition for {context.symbol} on {context.timeframe} "
                f"under {regime} regime."
            )

        # Rationale derived purely from provided context
        rationale = (
            f"The quantitative engine produced a Quant Score of {score:.1f}/100 and a "
            f"Predictive Score of {pred_score:.2f}. "
            f"Primary reasoning: {context.signal.reasoning or 'No specific reason provided'}."
        )

        drivers: list[str] = []
        if context.signal.positives:
            drivers.extend(context.signal.positives)
        else:
            drivers.append(f"Regime: {regime}")
            drivers.append(f"Score: {score:.1f}")

        # Risk assessment
        risk_parts: list[str] = []
        if context.risk.risk_category:
            risk_parts.append(f"Risk Category: {context.risk.risk_category}.")
        if context.risk.stop_loss is not None:
            risk_parts.append(f"Stop Loss at {context.risk.stop_loss:,.2f}.")
        if context.risk.take_profit is not None:
            risk_parts.append(f"Take Profit at {context.risk.take_profit:,.2f}.")
        if context.risk.risk_ratio is not None:
            risk_parts.append(f"Risk/Reward ratio: {context.risk.risk_ratio:.2f}.")

        risk_assessment = " ".join(risk_parts) if risk_parts else "Standard risk boundaries apply."

        meta: dict[str, Any] = {
            "provider": self.name,
            "deterministic": True,
            "symbol": context.symbol,
            "timeframe": context.timeframe,
        }

        return AgentExplanation(
            summary=summary,
            rationale=rationale,
            key_drivers=tuple(drivers),
            risk_assessment=risk_assessment,
            confidence=context.signal.confidence,
            raw_response="[MOCK_AI_RESPONSE: Deterministic template explanation]",
            metadata=meta,
        )

    async def summarize_market(self, context: MarketContext) -> AgentMarketSummary:
        """Generate a deterministic market overview based on the quantitative context."""
        title = f"{context.symbol} Market Intelligence Briefing ({context.timeframe})"
        overview = (
            f"{context.symbol} is trading at {context.current_price:,.2f} in a {context.market_regime} environment. "
            f"System action status: {context.signal.action} ({context.signal.direction})."
        )
        regime_interpretation = (
            f"Market is currently exhibiting characteristics of {context.market_regime}. "
            f"Predictive continuation/reversal score is {context.predictive_score:.2f}."
        )
        outlook = (
            f"Cautious stance: {context.signal.reasoning or 'Monitoring for confirmed structure'}."
        )

        key_levels: dict[str, float] = {}
        if context.volume_profile.get("poc") is not None:
            key_levels["POC"] = float(context.volume_profile["poc"])
        if context.volume_profile.get("vah") is not None:
            key_levels["VAH"] = float(context.volume_profile["vah"])
        if context.volume_profile.get("val") is not None:
            key_levels["VAL"] = float(context.volume_profile["val"])
        if context.risk.stop_loss is not None:
            key_levels["StopLoss"] = float(context.risk.stop_loss)
        if context.risk.take_profit is not None:
            key_levels["TakeProfit"] = float(context.risk.take_profit)

        meta: dict[str, Any] = {
            "provider": self.name,
            "deterministic": True,
        }

        return AgentMarketSummary(
            title=title,
            overview=overview,
            regime_interpretation=regime_interpretation,
            outlook=outlook,
            key_levels=key_levels,
            raw_response="[MOCK_AI_RESPONSE: Deterministic market briefing]",
            metadata=meta,
        )

    async def health_check(self) -> bool:
        """Return operational health status."""
        return self._is_healthy
