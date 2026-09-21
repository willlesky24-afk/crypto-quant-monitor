from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from src.ai_providers.factory import ProviderFactory
from src.ai_providers.interfaces import BaseLLMProvider
from src.anomaly_detection.detector import MarketAnomalyDetector
from src.market_reports.generator import MarketReportService
from src.operator_assistant.assistant import OperatorAssistant
from src.operator_service.storage.sqlite_provider import SQLiteMarketContextProvider


class OperatorCLI:
    """Interactive Command Line Interface for the AI Quant Trading Copilot.

    Enables human operators to:
    - Inspect real-time quantitative status, regimes, and scores.
    - Ask questions directly to the AI Copilot.
    - Generate institutional market intelligence reports.
    - Run an interactive conversational REPL loop.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        provider_type: str | None = None,
        provider: BaseLLMProvider | None = None,
    ) -> None:
        self.db_path = Path(db_path or os.getenv("DATABASE_PATH", "data/market_contexts.db"))
        self.context_provider = SQLiteMarketContextProvider(db_path=self.db_path)
        self.ai_provider = provider or ProviderFactory.create_provider(provider_type=provider_type)
        self.assistant = OperatorAssistant(
            context_provider=self.context_provider,
            ai_provider=self.ai_provider,
        )
        self.report_service = MarketReportService()
        self.anomaly_detector = MarketAnomalyDetector()

    def get_status(self, symbol: str = "BTCUSDT", timeframe: str = "1h") -> dict[str, Any]:
        """Fetch current market context and return structured status."""
        sym = symbol.strip().upper()
        tf = timeframe.strip().lower()

        repo = self.context_provider.repository
        context = repo.get_latest_context(sym, tf)
        if not context:
            return {
                "symbol": sym,
                "timeframe": tf,
                "status": "NO_DATA",
                "message": f"No persisted context found in {self.db_path} for {sym} ({tf}).",
            }

        anomalies = self.anomaly_detector.evaluate(context)
        return {
            "symbol": context.symbol,
            "timeframe": context.timeframe,
            "candle_timestamp": str(context.timestamp),
            "price": context.current_price,
            "regime": context.market_regime,
            "action": context.signal.action,
            "direction": context.signal.direction,
            "quant_score": context.quant_score,
            "predictive_score": context.predictive_score,
            "stop_loss": context.risk.stop_loss,
            "take_profit": context.risk.take_profit,
            "risk_reward_ratio": context.risk.risk_ratio,
            "anomalies_count": len(anomalies),
            "status": "ACTIVE",
        }

    def format_status_output(self, status: dict[str, Any]) -> str:
        """Format status dictionary into a readable terminal display."""
        if status.get("status") == "NO_DATA":
            return f"\n⚠️  {status.get('message')}\n"

        lines = [
            "\n" + "=" * 56,
            f"📊 MARKET STATUS: {status['symbol']} [{status['timeframe'].upper()}]",
            "=" * 56,
            f"Candle Time:      {status['candle_timestamp']}",
            f"Current Price:    ${status['price']:,.2f}",
            f"Market Regime:    {status['regime']}",
            f"Action / Dir:     {status['action']} ({status['direction']})",
            f"Quant Score:      {status['quant_score']:.2f}",
            f"Predictive Score: {status['predictive_score']:.2f}",
            f"Stop Loss:        ${status['stop_loss']:.2f}" if status.get("stop_loss") else "Stop Loss:        None",
            f"Take Profit:      ${status['take_profit']:.2f}" if status.get("take_profit") else "Take Profit:      None",
            f"Risk/Reward:      {status['risk_reward_ratio']:.2f}" if status.get("risk_reward_ratio") else "Risk/Reward:      N/A",
            f"Active Anomalies: {status['anomalies_count']}",
            "=" * 56 + "\n",
        ]
        return "\n".join(lines)

    def ask(self, query: str, symbol: str = "BTCUSDT", timeframe: str = "1h") -> str:
        """Query the AI Copilot and return formatted response."""
        import asyncio

        from src.operator_assistant.models import OperatorQuery

        sym = symbol.strip().upper()
        tf = timeframe.strip().lower()

        query_obj = OperatorQuery(query=query, symbol=sym, timeframe=tf)
        t0 = time.perf_counter()
        resp = asyncio.run(self.assistant.ask(query_obj))
        latency_ms = (time.perf_counter() - t0) * 1000

        output = [
            "\n" + "-" * 60,
            f"🤖 COPILOT RESPONSE [{sym} {tf}] ({latency_ms:.1f}ms)",
            "-" * 60,
            resp.answer.strip(),
            "",
            f"⚠️  DISCLAIMER: {resp.disclaimer}",
            "-" * 60 + "\n",
        ]
        return "\n".join(output)


    def get_report(self, symbol: str = "BTCUSDT", timeframe: str = "1h") -> str:
        """Generate and format an institutional market intelligence report."""
        sym = symbol.strip().upper()
        tf = timeframe.strip().lower()

        repo = self.context_provider.repository
        context = repo.get_latest_context(sym, tf)
        if not context:
            return f"\n⚠️  Cannot generate report: No persisted context found for {sym} ({tf}).\n"

        anomalies = self.anomaly_detector.evaluate(context)
        report = self.report_service.generate_daily_briefing(context=context)

        output = [
            "\n" + "=" * 64,
            f"📑 DAILY BRIEFING: {report.symbol} [{report.timeframe.upper()}] — {report.timestamp}",
            "=" * 64,
            f"Regime: {report.current_regime} | Quant Score: {report.quant_score:.1f} | Predictive: {report.predictive_score:.2f}",
            "",
            "EXECUTIVE SUMMARY:",
            f"  {report.market_overview}",
            "",
            "TECHNICAL & PREDICTIVE ASSESSMENT:",
            f"  {report.volatility_analysis}",
            "",
            "RISK FACTORS:",
        ]
        for risk in report.main_risks:
            output.append(f"  • {risk}")

        if anomalies:
            output.append("\nDETECTED ANOMALIES:")
            for anom in anomalies:
                output.append(f"  ⚡ [{anom.severity.value}] {anom.headline}: {anom.reason}")

        output.append("\nDECISION SUPPORT CONCLUSION:")
        output.append(f"  Historical Context: {report.historical_context}")
        output.append(f"\n⚠️  DISCLAIMER: {report.disclaimer}")
        output.append("=" * 64 + "\n")

        return "\n".join(output)

    def run_repl(self, default_symbol: str = "BTCUSDT", default_timeframe: str = "1h") -> None:
        """Launch an interactive REPL dialogue loop for continuous operator assistance."""
        symbol = default_symbol.strip().upper()
        timeframe = default_timeframe.strip().lower()

        print("\n" + "=" * 60)
        print("🤖 Crypto Quant Copilot — Interactive REPL Session")
        print(f"Tracking: {symbol} [{timeframe}] | Provider: {self.ai_provider.__class__.__name__}")
        print("Commands: 'status', 'report', 'switch <sym> <tf>', 'exit', 'quit'")
        print("=" * 60 + "\n")

        while True:
            try:
                prompt_str = f"[{symbol} {timeframe}] Copilot > "
                user_input = input(prompt_str).strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting Copilot REPL session. Goodbye.")
                break

            if not user_input:
                continue

            cmd_lower = user_input.lower()
            if cmd_lower in ("exit", "quit", "q"):
                print("Exiting Copilot REPL session. Goodbye.")
                break
            elif cmd_lower == "status":
                status = self.get_status(symbol=symbol, timeframe=timeframe)
                print(self.format_status_output(status))
            elif cmd_lower == "report":
                print(self.get_report(symbol=symbol, timeframe=timeframe))
            elif cmd_lower.startswith("switch"):
                parts = user_input.split()
                if len(parts) >= 2:
                    symbol = parts[1].strip().upper()
                if len(parts) >= 3:
                    timeframe = parts[2].strip().lower()
                print(f"Switched active focus to: {symbol} [{timeframe}]")
            else:
                print(self.ask(query=user_input, symbol=symbol, timeframe=timeframe))
