from __future__ import annotations

import logging
import re

from src.ai_agent.interfaces import BaseAIProvider, MockAIProvider
from src.ai_agent.models import MarketContext
from src.ai_providers.interfaces import BaseLLMProvider
from src.ai_providers.prompt_builder import PromptBuilder
from src.operator_assistant.interfaces import BaseOperatorAssistant
from src.operator_assistant.models import (
    AnalysisRequest,
    AnalysisResponse,
    OperatorQuery,
    OperatorResponse,
)
from src.operator_service.interfaces import BaseMarketContextProvider

logger = logging.getLogger(__name__)


class OperatorAssistant(BaseOperatorAssistant):
    """AI Quant Trading Copilot Assistant.

    Provides high-fidelity market intelligence and decision support directly to the human operator:
    - Interprets real-time quantitative context (QuantScore, PredictiveScore, MarketRegime, Risk).
    - Structures conditional scenario frameworks (Bullish continuation vs. Mean reversion).
    - Evaluates technical, volume profile, and risk indicators.
    - Zero execution authority: NEVER generates or executes automated trades.
    """

    def __init__(
        self,
        context_provider: BaseMarketContextProvider,
        ai_provider: BaseAIProvider | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self._context_provider = context_provider
        self._ai_provider = ai_provider or MockAIProvider()
        self._prompt_builder = prompt_builder or PromptBuilder()

    @property
    def context_provider(self) -> BaseMarketContextProvider:
        return self._context_provider

    @property
    def ai_provider(self) -> BaseAIProvider:
        return self._ai_provider

    @property
    def prompt_builder(self) -> PromptBuilder:
        return self._prompt_builder


    def _extract_symbol_timeframe(self, text: str, fallback_symbol: str, fallback_tf: str) -> tuple[str, str]:
        """Extract symbol and timeframe tokens if explicitly mentioned in query string."""
        symbol = fallback_symbol
        tf = fallback_tf

        # Look for explicit crypto pairs e.g. BTCUSDT, ETHUSDT, SOLUSDT, or specific known base assets
        match_sym = re.search(r"\b([A-Z]{2,10}(?:USDT|USD|BUSD))\b", text.upper())
        if match_sym:
            symbol = match_sym.group(1)
        else:
            match_base = re.search(r"\b(BTC|ETH|SOL|ADA|XRP|DOGE|BNB|AVAX|DOT|LINK)\b", text.upper())
            if match_base:
                symbol = f"{match_base.group(1)}USDT"

        # Look for timeframes e.g. 15m, 1h, 4h, 1d
        match_tf = re.search(r"\b(15[mM]|1[hH]|4[hH]|1[dD])\b", text)
        if match_tf:
            tf = match_tf.group(1).lower()

        return symbol, tf


    async def ask(self, query: OperatorQuery) -> OperatorResponse:
        """Process an operator query and return structured market interpretation and decision support."""
        symbol, timeframe = self._extract_symbol_timeframe(
            query.query, query.symbol, query.timeframe
        )

        context = await self._context_provider.get_latest_context(symbol, timeframe)
        if context is None:
            return OperatorResponse(
                answer=(
                    f"Unable to analyze {symbol} ({timeframe}): No closed-candle quantitative "
                    f"context is currently available in the active provider."
                ),
                symbol=symbol,
                timeframe=timeframe,
                market_regime="UNKNOWN",
                quant_score=0.0,
                predictive_score=0.0,
                confidence=0.0,
                key_drivers=(),
                risk_factors=("Context unavailable",),
                scenarios=(),
            )

        # Delegate narrative generation to AI provider
        if isinstance(self._ai_provider, BaseLLMProvider):
            prompt = self._prompt_builder.build_copilot_prompt(
                context=context,
                query=query.query,
            )
            llm_res = await self._ai_provider.generate_response(prompt)
            explanation_summary = llm_res.content
            market_outlook = f"Provider: {llm_res.provider} ({llm_res.model}) | Latency: {llm_res.latency_ms:.1f}ms"
            key_drivers = list(context.signal.positives) or [
                f"Regime: {context.market_regime}",
                f"Quant Score: {context.quant_score:.1f}",
            ]
        else:
            explanation = await self._ai_provider.generate_explanation(context)
            summary = await self._ai_provider.summarize_market(context)
            explanation_summary = explanation.summary
            market_outlook = summary.outlook
            key_drivers = list(explanation.key_drivers) if explanation.key_drivers else list(context.signal.positives)
            if not key_drivers:
                key_drivers.append(f"Regime: {context.market_regime}")
                key_drivers.append(f"Quant Score: {context.quant_score:.1f}")

        # Build scenario matrix based on quantitative and predictive metrics
        scenarios = self._formulate_scenarios(context)
        risk_factors = list(context.signal.warnings)
        if context.risk.risk_category:
            risk_factors.append(f"Risk Category: {context.risk.risk_category}")

        answer = self._compose_copilot_narrative(
            query=query.query,
            context=context,
            explanation_summary=explanation_summary,
            market_outlook=market_outlook,
            scenarios=scenarios,
        )

        return OperatorResponse(

            answer=answer,
            symbol=context.symbol,
            timeframe=context.timeframe,
            market_regime=context.market_regime,
            quant_score=context.quant_score,
            predictive_score=context.predictive_score,
            confidence=context.signal.confidence,
            key_drivers=tuple(key_drivers),
            risk_factors=tuple(risk_factors),
            scenarios=tuple(scenarios),
            metadata={
                "current_price": context.current_price,
                "action_bias": context.signal.action,
                "direction_bias": context.signal.direction,
                "stop_loss": context.risk.stop_loss,
                "take_profit": context.risk.take_profit,
            },
        )

    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        """Perform a deep-dive contextual breakdown for the requested asset."""
        context = await self._context_provider.get_latest_context(
            request.symbol, request.timeframe
        )

        if context is None:
            return AnalysisResponse(
                symbol=request.symbol,
                timeframe=request.timeframe,
                current_price=0.0,
                market_regime="UNKNOWN",
                quant_score=0.0,
                predictive_score=0.0,
                technical_summary=f"No data available for {request.symbol} ({request.timeframe}).",
                volume_analysis="No volume profile data available.",
                risk_assessment="No risk boundaries calculated.",
                possible_scenarios=(),
            )

        scenarios = self._formulate_scenarios(context)

        # Technical Indicators overview
        tech_lines: list[str] = []
        for k, v in sorted(context.technical_indicators.items()):
            val_str = f"{v:.2f}" if isinstance(v, float) else str(v)
            tech_lines.append(f"- {k}: {val_str}")
        tech_summary = "\n".join(tech_lines) if tech_lines else "Indicators within expected baselines."

        # Volume Profile summary
        vp = context.volume_profile
        poc = vp.get("poc", "N/A")
        vah = vp.get("vah", "N/A")
        val = vp.get("val", "N/A")
        vol_summary = f"POC: {poc} | Value Area High (VAH): {vah} | Value Area Low (VAL): {val}"

        # Risk parameters
        risk_summary = (
            f"Category: {context.risk.risk_category or 'Moderate'} | "
            f"Stop Loss: {context.risk.stop_loss or 'N/A'} | "
            f"Take Profit: {context.risk.take_profit or 'N/A'} | "
            f"ATR: {context.risk.atr or 'N/A'}"
        )

        return AnalysisResponse(
            symbol=context.symbol,
            timeframe=context.timeframe,
            current_price=context.current_price,
            market_regime=context.market_regime,
            quant_score=context.quant_score,
            predictive_score=context.predictive_score,
            technical_summary=tech_summary,
            volume_analysis=vol_summary,
            risk_assessment=risk_summary,
            possible_scenarios=tuple(scenarios),
        )

    def _formulate_scenarios(self, context: MarketContext) -> list[str]:
        """Formulate scenario frameworks based on quantitative indicators."""
        scenarios: list[str] = []
        regime = context.market_regime
        pred = context.predictive_score
        quant = context.quant_score

        if "BULL" in regime or pred > 0.65:
            scenarios.append(
                f"Primary Scenario (Bullish Expansion): Continuation toward resistance while holding above "
                f"support/SL level ({context.risk.stop_loss or 'nearest pivot'})."
            )
            scenarios.append(
                "Alternative Scenario (Exhaustion / Pullback): Failure to sustain momentum could trigger "
                "a mean-reversion retest of the Value Area POC."
            )
        elif "BEAR" in regime or pred < 0.35:
            scenarios.append(
                f"Primary Scenario (Bearish Continuation): Downside drift remains favored under {regime} regime; "
                f"watch for breakdown below support."
            )
            scenarios.append(
                "Alternative Scenario (Short Squeeze / Relief Rally): Bullish divergence could prompt "
                "a quick liquidity reclaim toward Value Area High."
            )
        else:
            scenarios.append(
                f"Primary Scenario (Range Bound / Consolidation): Price likely to oscillate within the current value "
                f"area with Quant Score at {quant:.1f}/100."
            )
            scenarios.append(
                "Breakout Scenario: Sustained expansion accompanied by volume deviation required for trend definition."
            )

        return scenarios

    def _compose_copilot_narrative(
        self,
        query: str,
        context: MarketContext,
        explanation_summary: str,
        market_outlook: str,
        scenarios: list[str],
    ) -> str:
        """Assemble structured markdown narrative for the human operator."""
        lines = [
            f"### 🤖 Copilot Intelligence: {context.symbol} [{context.timeframe.upper()}]",
            f"**Current Price:** ${context.current_price:,.2f} | **Regime:** `{context.market_regime}`",
            f"**Quant Score:** {context.quant_score:.1f}/100 | **Predictive Score:** {context.predictive_score:.2f} | **Confidence:** {context.signal.confidence*100:.1f}%",
            "",
            "#### 📊 Quantitative Assessment & Bias",
            f"{explanation_summary}",
            f"{market_outlook}",
            "",
            "#### 🎯 Scenarios for Operator Evaluation",
        ]
        for sc in scenarios:
            lines.append(f"- {sc}")

        sl_str = f"${context.risk.stop_loss:,.2f}" if context.risk.stop_loss is not None else "None specified"
        tp_str = f"${context.risk.take_profit:,.2f}" if context.risk.take_profit is not None else "None specified"

        lines.extend([
            "",
            "#### 🛡️ Risk & Boundary Factors",
            f"- **Stop Loss Level:** {sl_str}",
            f"- **Take Profit Target:** {tp_str}",
            f"- **Risk Category:** {context.risk.risk_category or 'Standard'}",
        ])


        if context.signal.warnings:
            lines.append("- **Active Warnings:**")
            for w in context.signal.warnings:
                lines.append(f"  * {w}")

        return "\n".join(lines)