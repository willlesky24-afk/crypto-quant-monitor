from __future__ import annotations

from src.ai_agent.models import MarketContext
from src.anomaly_detection.models import MarketAlert
from src.market_reports.models import DailyBriefingReport


class PromptBuilder:
    """Constructs rigorous, contextual, instruction-safe prompts for LLM providers.

    Guarantees strict operational boundaries:
    - Never instructs or allows order placement or automated trade execution.
    - Explicitly forbids hallucinating or inventing missing quantitative data.
    - Anchors interpretation strictly to closed candle T context.
    """

    SYSTEM_ROLE_PROMPT: str = (
        "You are an institutional AI Quant Trading Copilot assistant for Crypto Quant Monitor.\n"
        "Your role is strictly decision support and market interpretation for a professional human operator.\n\n"
        "MANDATORY OPERATIONAL DIRECTIVES:\n"
        "1. EXPLAIN the provided quantitative metrics, regime, volume profile, and risk boundaries.\n"
        "2. DO NOT provide definitive financial or investment instructions.\n"
        "3. DO NOT generate or execute trades. You have ZERO execution authority.\n"
        "4. DO NOT invent or extrapolate missing quantitative figures.\n"
        "5. Keep the narrative objective, probabilistic, and structured for human review."
    )

    def build_copilot_prompt(
        self,
        context: MarketContext,
        query: str,
        briefing: DailyBriefingReport | None = None,
        alerts: list[MarketAlert] | None = None,
    ) -> str:
        """Compose structured operator prompt merging market context, reports, anomalies, and query."""
        lines = [
            self.SYSTEM_ROLE_PROMPT,
            "",
            "==================================================",
            "IMMUTABLE QUANTITATIVE SNAPSHOT (CLOSED CANDLE T)",
            "==================================================",
            f"Asset: {context.symbol} | Interval: {context.timeframe.upper()}",
            f"Timestamp: {context.timestamp}",
            f"Current Price: ${context.current_price:,.2f}",
            f"Market Regime: {context.market_regime}",
            f"Quant Score: {context.quant_score:.1f}/100",
            f"Predictive Score: {context.predictive_score:.2f} (Scale: 0.0 - 1.0)",
            f"Engine Signal Action: {context.signal.action} ({context.signal.direction})",
            f"Signal Confidence: {context.signal.confidence*100:.1f}%",
            f"Quantitative Reasoning: {context.signal.reasoning or 'N/A'}",
        ]

        if context.signal.positives:
            lines.append("Supporting Confluences:")
            for p in context.signal.positives:
                lines.append(f"  + {p}")

        if context.signal.warnings:
            lines.append("Risk Warnings:")
            for w in context.signal.warnings:
                lines.append(f"  - {w}")

        sl_str = f"${context.risk.stop_loss:,.2f}" if context.risk.stop_loss is not None else "None"
        tp_str = f"${context.risk.take_profit:,.2f}" if context.risk.take_profit is not None else "None"

        lines.extend([
            "",
            "Risk Parameters:",
            f"  - Stop Loss: {sl_str}",
            f"  - Take Profit: {tp_str}",
            f"  - Risk Category: {context.risk.risk_category or 'Standard'}",
            f"  - ATR: {context.risk.atr or 'N/A'}",
        ])


        if context.volume_profile:
            lines.extend([
                "",
                "Volume Profile Levels:",
                f"  - POC: {context.volume_profile.get('poc', 'N/A')}",
                f"  - Value Area High (VAH): {context.volume_profile.get('vah', 'N/A')}",
                f"  - Value Area Low (VAL): {context.volume_profile.get('val', 'N/A')}",
            ])

        if briefing is not None:
            lines.extend([
                "",
                "==================================================",
                "DAILY MARKET BRIEFING CONTEXT",
                "==================================================",
                f"Overview: {briefing.market_overview}",
                f"Volatility Context: {briefing.volatility_analysis}",
            ])

        if alerts:
            lines.extend([
                "",
                "==================================================",
                "PASSIVE MARKET ANOMALY ALERTS DETECTED",
                "==================================================",
            ])
            for alt in alerts:
                lines.append(f"[{alt.severity.value}] {alt.headline}: {alt.reason}")

        lines.extend([
            "",
            "==================================================",
            "HUMAN OPERATOR INQUIRY",
            "==================================================",
            f"Query: \"{query}\"",
            "",
            "RESPONSE INSTRUCTIONS:",
            "- Directly answer the operator's query using the quantitative snapshot above.",
            "- Structure the response with clear headings (Assessment, Scenarios, Risk Factors).",
            "- Remind the operator that all trading decisions remain their responsibility.",
        ])

        return "\n".join(lines)