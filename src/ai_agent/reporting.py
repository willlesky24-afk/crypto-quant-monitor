from __future__ import annotations

from typing import Any

from src.ai_agent.interfaces import BaseAIProvider
from src.ai_agent.models import AgentMarketSummary, MarketContext


class MarketReportGenerator:
    """Generates structured, high-level market intelligence summaries from MarketContext.

    Adheres strictly to the architectural constraints:
    - Does NOT predict markets or create trading signals.
    - Consumes exclusively existing quantitative outputs from closed candle T.
    - Never recalculates indicators or scores.
    - Maintains deterministic and offline operation.
    """

    def __init__(self, provider: BaseAIProvider | None = None) -> None:
        """Initialize the market report generator.

        Args:
            provider: Optional AI provider (e.g. BaseAIProvider).
                      If omitted, reports are generated via the built-in deterministic engine.
        """
        self._provider = provider

    @property
    def provider(self) -> BaseAIProvider | None:
        """Configured AI provider, if any."""
        return self._provider

    def generate_report(self, context: MarketContext) -> AgentMarketSummary:
        """Synchronously generate a structured, deterministic market intelligence briefing.

        Args:
            context: Immutable snapshot of closed candle T quantitative state.

        Returns:
            Structured AgentMarketSummary containing title, overview, regime analysis, outlook, and key levels.
        """
        symbol = context.symbol
        timeframe = context.timeframe
        price = context.current_price
        regime = context.market_regime
        quant_score = context.quant_score
        pred_score = context.predictive_score
        action = context.signal.action
        direction = context.signal.direction

        # 1. Title & Executive Overview
        title = f"{symbol} Market Intelligence Report ({timeframe})"
        overview = (
            f"{symbol} is trading at {price:,.2f} on the {timeframe} timeframe in an established "
            f"{regime} environment. Quantitative engine assessment reflects a Quant Score of "
            f"{quant_score:.1f}/100 with predictive continuation/reversal score at {pred_score:.2f}. "
            f"System stance is {action} ({direction})."
        )

        # 2. Detailed Regime & Volume Profile Interpretation
        regime_parts = []
        if regime == "TRENDING_BULL":
            regime_parts.append(
                "Bullish trend regime identified. Price structure exhibits higher highs and "
                "supportive moving average alignment, favoring long-side trend continuation."
            )
        elif regime == "TRENDING_BEAR":
            regime_parts.append(
                "Bearish trend regime identified. Downward momentum dominates with prices below "
                "key trend benchmarks, favoring defensive positioning or short bias."
            )
        elif regime == "RANGING_CONSOLIDATION":
            regime_parts.append(
                "Consolidation/Range regime identified. Market is trading sideways with low directional "
                "persistence; caution is warranted near range boundaries."
            )
        elif regime == "HIGH_VOLATILITY_EXPANSION":
            regime_parts.append(
                "High volatility expansion regime identified. Wide price swings and expanding ranges "
                "increase execution risk and potential slippage."
            )
        else:
            regime_parts.append(f"Market is operating under an unclassified or custom {regime} regime.")

        # Volume Profile value area positioning
        vp = context.volume_profile
        poc = vp.get("poc")
        vah = vp.get("vah")
        val = vp.get("val")

        if poc is not None and isinstance(poc, (int, float)):
            poc_val = float(poc)
            vah_val = float(vah) if vah is not None and isinstance(vah, (int, float)) else None
            val_val = float(val) if val is not None and isinstance(val, (int, float)) else None

            if vah_val is not None and price > vah_val:
                regime_parts.append(
                    f"Price is trading above the Value Area (VAH at {vah_val:,.2f}), "
                    f"indicating strong bullish extension or potential buyer exhaustion."
                )
            elif val_val is not None and price < val_val:
                regime_parts.append(
                    f"Price is trading below the Value Area (VAL at {val_val:,.2f}), "
                    f"indicating seller extension or potential oversold conditions."
                )
            elif val_val is not None and vah_val is not None:
                regime_parts.append(
                    f"Price is trading within the Value Area ({val_val:,.2f} - {vah_val:,.2f}), "
                    f"confirming fair value acceptance centered at POC ({poc_val:,.2f})."
                )
            else:
                regime_parts.append(f"High-volume Point of Control (POC) is situated at {poc_val:,.2f}.")

        regime_interpretation = " ".join(regime_parts)

        # 3. Market Outlook & Risk Environment Summary
        outlook_parts = []
        if context.signal.reasoning:
            outlook_parts.append(f"Operational focus: {context.signal.reasoning}.")
        else:
            outlook_parts.append("Operational focus: Quantitative parameters monitor for confirmed setups.")

        # Volatility context
        if context.risk.atr is not None:
            outlook_parts.append(f"Local volatility measured by ATR is {context.risk.atr:,.2f}.")

        # Risk context
        risk_cat = context.risk.risk_category or "Standard"
        outlook_parts.append(f"Risk environment is assessed as {risk_cat}.")

        if context.risk.stop_loss is not None and context.risk.take_profit is not None:
            rr_str = f" (R:R {context.risk.risk_ratio:.2f})" if context.risk.risk_ratio is not None else ""
            outlook_parts.append(
                f"Established execution boundaries: Stop Loss at {context.risk.stop_loss:,.2f} "
                f"and Take Profit at {context.risk.take_profit:,.2f}{rr_str}."
            )
        elif context.risk.stop_loss is not None:
            outlook_parts.append(f"Protective Stop Loss is stationed at {context.risk.stop_loss:,.2f}.")
        elif context.risk.take_profit is not None:
            outlook_parts.append(f"Target Take Profit is set at {context.risk.take_profit:,.2f}.")
        else:
            outlook_parts.append("No explicit Stop Loss or Take Profit targets defined for this posture.")

        outlook = " ".join(outlook_parts)

        # 4. Key Quantitative Levels
        key_levels: dict[str, float] = {"CurrentPrice": float(price)}
        if poc is not None and isinstance(poc, (int, float)):
            key_levels["POC"] = float(poc)
        if vah is not None and isinstance(vah, (int, float)):
            key_levels["VAH"] = float(vah)
        if val is not None and isinstance(val, (int, float)):
            key_levels["VAL"] = float(val)
        if context.risk.stop_loss is not None:
            key_levels["StopLoss"] = float(context.risk.stop_loss)
        if context.risk.take_profit is not None:
            key_levels["TakeProfit"] = float(context.risk.take_profit)

        # 5. Metadata
        market_state = str(
            context.metadata.get("market_state")
            or context.technical_indicators.get("market_state")
            or ""
        )
        meta: dict[str, Any] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": str(context.timestamp),
            "market_regime": regime,
            "market_state": market_state,
            "risk_category": risk_cat,
            "quant_score": quant_score,
            "predictive_score": pred_score,
            "deterministic": True,
            "generator": "MarketReportGenerator",
        }
        if context.metadata:
            meta["context_metadata"] = dict(context.metadata)

        return AgentMarketSummary(
            title=title,
            overview=overview,
            regime_interpretation=regime_interpretation,
            outlook=outlook,
            key_levels=key_levels,
            raw_response="[DETERMINISTIC_REPORT: MarketReportGenerator]",
            metadata=meta,
        )

    async def generate_report_async(self, context: MarketContext) -> AgentMarketSummary:
        """Asynchronously generate a market summary.

        If an external AI provider was injected, delegates to `provider.summarize_market(context)`.
        Otherwise, falls back to the deterministic in-process engine.
        """
        if self._provider is not None:
            return await self._provider.summarize_market(context)
        return self.generate_report(context)
