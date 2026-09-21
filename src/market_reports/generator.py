from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.ai_agent.models import MarketContext
from src.market_reports.models import DailyBriefingReport, IntradayUpdateReport


class MarketReportService:
    """Service generating institutional-grade, human-readable market intelligence reports.

    Consumes existing quantitative snapshots (MarketContext) without modifying
    calculations or issuing automated trading actions.
    """

    def generate_daily_briefing(self, context: MarketContext) -> DailyBriefingReport:
        """Generate a structured daily briefing based on the latest closed-candle context."""
        report_id = f"briefing-{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Extract levels
        levels: dict[str, float] = {}
        if context.risk.stop_loss is not None:
            levels["Stop Loss"] = context.risk.stop_loss
        if context.risk.take_profit is not None:
            levels["Take Profit"] = context.risk.take_profit
        if "poc" in context.volume_profile and context.volume_profile["poc"] is not None:
            levels["Volume POC"] = float(context.volume_profile["poc"])
        if "vah" in context.volume_profile and context.volume_profile["vah"] is not None:
            levels["Value Area High"] = float(context.volume_profile["vah"])
        if "val" in context.volume_profile and context.volume_profile["val"] is not None:
            levels["Value Area Low"] = float(context.volume_profile["val"])

        # Signals
        signals: list[str] = []
        if context.signal.action != "WAIT":
            signals.append(
                f"{context.signal.action} ({context.signal.direction}) signal active with "
                f"{context.signal.confidence*100:.1f}% confidence."
            )
        if context.signal.positives:
            signals.extend(context.signal.positives)
        else:
            signals.append(f"Regime baseline: {context.market_regime}")

        # Risks
        risks: list[str] = []
        if context.signal.warnings:
            risks.extend(context.signal.warnings)
        if context.risk.risk_category:
            risks.append(f"Risk Profile: {context.risk.risk_category}")
        if not risks:
            risks.append("No adverse volatility spikes detected.")

        # Volatility
        atr_val = context.risk.atr
        vol_str = (
            f"Current ATR is {atr_val:.2f}. Volatility is within normalized historical bounds."
            if atr_val
            else "ATR volatility metric unavailable."
        )

        overview = (
            f"{context.symbol} is trading at ${context.current_price:,.2f} under the "
            f"'{context.market_regime}' regime. Quantitative score stands at {context.quant_score:.1f}/100 "
            f"with a predictive score of {context.predictive_score:.2f}."
        )

        hist_context = (
            f"Market context reflects closed candle T state at {context.timestamp}. "
            f"Current bias is aligned with {context.signal.direction} positioning."
        )

        return DailyBriefingReport(
            report_id=report_id,
            symbol=context.symbol,
            timeframe=context.timeframe,
            timestamp=now_iso,
            market_overview=overview,
            current_regime=context.market_regime,
            quant_score=context.quant_score,
            predictive_score=context.predictive_score,
            strongest_signals=tuple(signals),
            main_risks=tuple(risks),
            important_levels=levels,
            volatility_analysis=vol_str,
            historical_context=hist_context,
        )

    def generate_intraday_update(
        self, current_context: MarketContext, previous_context: MarketContext | None = None
    ) -> IntradayUpdateReport:
        """Generate an intraday delta report comparing current and previous snapshots."""
        report_id = f"intraday-{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        if previous_context is None:
            return IntradayUpdateReport(
                report_id=report_id,
                symbol=current_context.symbol,
                timeframe=current_context.timeframe,
                timestamp=now_iso,
                what_changed=f"Baseline established for {current_context.symbol} at ${current_context.current_price:,.2f}.",
                why_it_changed="Initial context ingested; awaiting consecutive snapshot for delta computation.",
                what_to_monitor=(
                    f"Monitor regime stability ({current_context.market_regime})",
                    f"Watch key support at {current_context.risk.stop_loss or 'nearest level'}",
                ),
                regime_shift=None,
                price_delta_pct=0.0,
                score_delta=0.0,
            )

        # Calculate deltas
        price_delta_pct = (
            ((current_context.current_price - previous_context.current_price) / previous_context.current_price) * 100.0
            if previous_context.current_price > 0
            else 0.0
        )
        score_delta = current_context.quant_score - previous_context.quant_score

        regime_shift = (
            f"Shifted from '{previous_context.market_regime}' to '{current_context.market_regime}'"
            if current_context.market_regime != previous_context.market_regime
            else None
        )

        what_changed = (
            f"Price moved {price_delta_pct:+.2f}% to ${current_context.current_price:,.2f}. "
            f"Quant Score moved {score_delta:+.1f} pts to {current_context.quant_score:.1f}. "
            f"{regime_shift if regime_shift else 'Regime remained stable.'}"
        )


        why_it_changed = (
            f"Driven by action: {current_context.signal.action} ({current_context.signal.direction}) "
            f"with confidence {current_context.signal.confidence*100:.1f}%. "
            f"Reasoning: {current_context.signal.reasoning or 'Continuous quantitative monitoring'}"
        )

        what_to_monitor = [
            f"Regime status: {current_context.market_regime}",
            f"Predictive score trajectory (now {current_context.predictive_score:.2f})",
        ]
        if current_context.risk.stop_loss:
            what_to_monitor.append(f"Risk boundary stop: ${current_context.risk.stop_loss:,.2f}")
        if current_context.risk.take_profit:
            what_to_monitor.append(f"Target boundary TP: ${current_context.risk.take_profit:,.2f}")

        return IntradayUpdateReport(

            report_id=report_id,
            symbol=current_context.symbol,
            timeframe=current_context.timeframe,
            timestamp=now_iso,
            what_changed=what_changed,
            why_it_changed=why_it_changed,
            what_to_monitor=tuple(what_to_monitor),
            regime_shift=regime_shift,
            price_delta_pct=round(price_delta_pct, 3),
            score_delta=round(score_delta, 2),
        )