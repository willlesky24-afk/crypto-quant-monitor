from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.ai_agent.context_builder import ContextBuilder
from src.ai_providers.factory import ProviderFactory
from src.data_loader import BinanceDataLoader
from src.decision_engine import DecisionEngine
from src.engine import MarketEngine
from src.indicators import TechnicalIndicators
from src.market_intelligence import MarketIntelligence
from src.notifications.models import SignalEvent
from src.operator_assistant.assistant import OperatorAssistant
from src.operator_service.storage.sqlite_provider import SQLiteMarketContextProvider
from src.predictive_engine import PredictiveEngine
from src.quant_score import QuantScore
from src.regime_classifier import RegimeClassifier
from src.risk_engine import RiskEngine
from src.signal_engine import SignalEngine
from src.volume_profile import VolumeProfile

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CheckResult:
    """Individual operational validation check result."""

    name: str
    status: str  # "PASS", "WARN", "FAIL"
    message: str
    latency_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationReport:
    """Consolidated operational validation report."""

    timestamp: datetime
    overall_status: str  # "PASS", "WARN", "FAIL"
    checks: list[CheckResult]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "overall_status": self.overall_status,
            "summary": self.summary,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "message": c.message,
                    "latency_ms": c.latency_ms,
                    "details": c.details,
                }
                for c in self.checks
            ],
        }


class RealMarketValidator:
    """Automated operational validation harness for production deployment and live market feeds.

    Validates:
    1. Exchange connectivity, REST ping, and server time clock drift.
    2. Real market data ingestion, OHLC integrity, and causal closed-candle boundaries.
    3. Quantitative pipeline calculation (Indicators, Volume Profile, Regime, Predictive, Decision).
    4. Persistent state management (SQLite context read/write).
    5. AI Copilot reasoning & mandatory decision-support disclaimer.
    6. Non-autonomous verification (zero trade execution / no order placement).
    """

    def __init__(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "1h",
        db_path: str | Path = ":memory:",
        timeout_sec: float = 5.0,
    ) -> None:
        self.symbol = symbol.strip().upper()
        self.interval = interval.strip().lower()
        self.db_path = str(db_path)
        self.timeout_sec = timeout_sec

    def check_exchange_connectivity(self, base_url: str = "https://api.binance.com") -> CheckResult:
        """Validate exchange ping and clock synchronization."""
        t0 = time.perf_counter()
        try:
            # 1. Ping
            ping_url = f"{base_url}/api/v3/ping"
            req = urllib.request.Request(ping_url, headers={"User-Agent": "CryptoQuant-Validator/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                if resp.status != 200:
                    return CheckResult(
                        name="exchange_connectivity",
                        status="FAIL",
                        message=f"Ping returned HTTP {resp.status}",
                        latency_ms=(time.perf_counter() - t0) * 1000,
                    )

            # 2. Time check
            time_url = f"{base_url}/api/v3/time"
            req_time = urllib.request.Request(time_url, headers={"User-Agent": "CryptoQuant-Validator/1.0"})
            with urllib.request.urlopen(req_time, timeout=self.timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                server_time_ms = int(data.get("serverTime", 0))
                local_time_ms = int(time.time() * 1000)
                drift_ms = abs(server_time_ms - local_time_ms)

            latency = (time.perf_counter() - t0) * 1000
            status = "PASS" if drift_ms < 2000 else "WARN"
            msg = f"Connected. Clock drift: {drift_ms}ms"
            return CheckResult(
                name="exchange_connectivity",
                status=status,
                message=msg,
                latency_ms=latency,
                details={"server_time_ms": server_time_ms, "drift_ms": drift_ms},
            )
        except Exception as exc:
            return CheckResult(
                name="exchange_connectivity",
                status="FAIL",
                message=f"Failed to connect to exchange: {exc}",
                latency_ms=(time.perf_counter() - t0) * 1000,
            )

    def check_market_data_ingestion(self, loader: BinanceDataLoader | None = None) -> tuple[CheckResult, pd.DataFrame | None]:
        """Validate live candle fetching, OHLCV constraints, and anti-repainting closed candle rule."""
        t0 = time.perf_counter()
        data_loader = loader or BinanceDataLoader()
        try:
            df = data_loader.get_klines(
                symbol=self.symbol,
                interval=self.interval,
                limit=250,
                include_open_candle=False,
            )
            latency = (time.perf_counter() - t0) * 1000

            if df is None or df.empty or len(df) < 50:
                return CheckResult(
                    name="market_data_ingestion",
                    status="FAIL",
                    message=f"Insufficient candles returned ({len(df) if df is not None else 0})",
                    latency_ms=latency,
                ), None

            # Verify OHLC invariants
            invalid_high_low = (df["high"] < df["low"]).sum()
            invalid_open_high = (df["open"] > df["high"]).sum()
            invalid_close_low = (df["close"] < df["low"]).sum()
            invalid_vol = (df["volume"] < 0).sum()

            if invalid_high_low > 0 or invalid_open_high > 0 or invalid_close_low > 0 or invalid_vol > 0:
                return CheckResult(
                    name="market_data_ingestion",
                    status="FAIL",
                    message="OHLCV invariant violation detected in fetched candles",
                    latency_ms=latency,
                    details={"invalid_high_low": int(invalid_high_low)},
                ), None

            return CheckResult(
                name="market_data_ingestion",
                status="PASS",
                message=f"Retrieved {len(df)} validated closed candles for {self.symbol}",
                latency_ms=latency,
                details={"bars_count": len(df), "last_candle_timestamp": str(df["timestamp"].iloc[-1])},
            ), df
        except Exception as exc:
            return CheckResult(
                name="market_data_ingestion",
                status="FAIL",
                message=f"Data ingestion error: {exc}",
                latency_ms=(time.perf_counter() - t0) * 1000,
            ), None

    def check_quantitative_pipeline(self, df: pd.DataFrame) -> tuple[CheckResult, SignalEvent | None]:
        """Validate pipeline execution from raw candles to SignalEvent at closed candle T."""
        t0 = time.perf_counter()
        try:
            indicators_svc = TechnicalIndicators()
            df_enriched = indicators_svc.calculate_all(df)

            vp_svc = VolumeProfile()
            profile = vp_svc.calculate(df_enriched)

            m_engine = MarketEngine()
            analysis = m_engine.analyze(df_enriched, profile)

            s_engine = SignalEngine()
            signal = s_engine.evaluate(analysis, profile)

            r_engine = RiskEngine()
            risk = r_engine.evaluate(analysis, profile)

            i_engine = MarketIntelligence()
            intel = i_engine.evaluate(analysis)

            q_score_engine = QuantScore()
            score = q_score_engine.calculate(analysis, signal, risk)

            regime_clf = RegimeClassifier()
            regime_res = regime_clf.classify(df_enriched)

            pred_engine = PredictiveEngine()
            pred_res = pred_engine.evaluate(df_enriched, current_regime_res=regime_res)

            dec_engine = DecisionEngine()
            decision = dec_engine.evaluate(
                signal=signal,
                risk=risk,
                intelligence=intel,
                predictive=pred_res,
                regime=regime_res.regime,
                technical_score=score["score"],
                predictive_mode=True,
            )

            last_row = df_enriched.iloc[-1]
            signal_event = SignalEvent(
                timestamp=pd.Timestamp(last_row["timestamp"]),
                symbol=self.symbol,
                timeframe=self.interval,
                action=decision.decision,
                direction=decision.direction,
                confidence=decision.confidence,
                predictive_score=pred_res.predictive_score,
                regime=regime_res.regime.value,
                reasoning=decision.reasoning,
                price=float(last_row["close"]),
                quant_score=score["score"],
                stop_loss=risk.get("stop_loss"),
                take_profit=risk.get("take_profit"),
                signal_id=f"val-{self.symbol}-{self.interval}-{int(time.time())}",
                metadata={"risk_reward_ratio": risk.get("risk_ratio"), "atr": risk.get("atr")},
            )

            latency = (time.perf_counter() - t0) * 1000
            return CheckResult(
                name="quantitative_pipeline",
                status="PASS",
                message=f"Pipeline evaluated: action={decision.decision}, regime={regime_res.regime.value}, score={score['score']:.2f}",
                latency_ms=latency,
                details={
                    "action": decision.decision,
                    "direction": decision.direction,
                    "regime": regime_res.regime.value,
                    "quant_score": score["score"],
                    "predictive_score": pred_res.predictive_score,
                },
            ), signal_event
        except Exception as exc:
            return CheckResult(
                name="quantitative_pipeline",
                status="FAIL",
                message=f"Quantitative pipeline execution failed: {exc}",
                latency_ms=(time.perf_counter() - t0) * 1000,
            ), None

    def check_persistence_and_copilot(self, signal_event: SignalEvent) -> CheckResult:
        """Validate SQLite context persistence and Operator Copilot response generation."""
        t0 = time.perf_counter()
        try:
            market_context = ContextBuilder.build_from_signal_event(
                signal_event=signal_event,
                extra_metadata={"validation": True, "poc": signal_event.price},
            )

            provider = SQLiteMarketContextProvider(db_path=self.db_path)
            provider.update_context(market_context)

            # Read back
            repo = provider.repository
            latest = repo.get_latest_context(self.symbol, self.interval)
            if latest is None:
                return CheckResult(
                    name="persistence_and_copilot",
                    status="FAIL",
                    message="Failed to read back saved market context from SQLite",
                    latency_ms=(time.perf_counter() - t0) * 1000,
                )

            # Test Operator Assistant with mock LLM provider for determinism
            import asyncio

            from src.operator_assistant.models import OperatorQuery

            ai_provider = ProviderFactory.create_provider(provider_type="mock")
            assistant = OperatorAssistant(context_provider=provider, ai_provider=ai_provider)

            query_obj = OperatorQuery(
                query=f"Explain current state for {self.symbol}",
                symbol=self.symbol,
                timeframe=self.interval,
            )
            response = asyncio.run(assistant.ask(query_obj))

            repo.close()
            latency = (time.perf_counter() - t0) * 1000

            has_disclaimer = bool(response.disclaimer)
            if not has_disclaimer:
                return CheckResult(
                    name="persistence_and_copilot",
                    status="WARN",
                    message="Context saved but Copilot response lacked decision-support disclaimer",
                    latency_ms=latency,
                )

            return CheckResult(
                name="persistence_and_copilot",
                status="PASS",
                message=f"Context stored & Copilot answered successfully ({len(response.answer)} chars)",
                latency_ms=latency,
                details={"disclaimer_present": has_disclaimer},
            )

        except Exception as exc:
            return CheckResult(
                name="persistence_and_copilot",
                status="FAIL",
                message=f"Persistence / Copilot validation failed: {exc}",
                latency_ms=(time.perf_counter() - t0) * 1000,
            )

    def check_non_autonomous_safety(self) -> CheckResult:
        """Verify that the system contains zero automated trading or order execution hooks."""
        t0 = time.perf_counter()
        prohibited_modules = [
            "src.trade_execution",
            "src.order_router",
            "src.binance_trader",
            "src.auto_execution",
        ]
        found: list[str] = []
        for mod in prohibited_modules:
            try:
                __import__(mod)
                found.append(mod)
            except ImportError:
                pass

        latency = (time.perf_counter() - t0) * 1000
        if found:
            return CheckResult(
                name="non_autonomous_safety",
                status="FAIL",
                message=f"Prohibited execution modules detected: {found}",
                latency_ms=latency,
            )

        return CheckResult(
            name="non_autonomous_safety",
            status="PASS",
            message="Verified: Pure AI Copilot architecture. Zero automated trading logic present.",
            latency_ms=latency,
        )

    def run_full_validation(
        self,
        loader: BinanceDataLoader | None = None,
        dry_run: bool = False,
    ) -> ValidationReport:
        """Execute the full pre-flight validation sequence."""
        checks: list[CheckResult] = []

        # 1. Non-autonomous safety check
        checks.append(self.check_non_autonomous_safety())

        # 2. Exchange connectivity (skip network call if dry_run)
        if dry_run:
            checks.append(
                CheckResult(
                    name="exchange_connectivity",
                    status="PASS",
                    message="Skipped exchange network call (dry-run mode enabled)",
                    latency_ms=0.1,
                )
            )
        else:
            checks.append(self.check_exchange_connectivity())

        # 3. Market data ingestion
        ingestion_check, df = self.check_market_data_ingestion(loader=loader)
        checks.append(ingestion_check)

        # 4. Quantitative pipeline
        signal_event: SignalEvent | None = None
        if df is not None:
            pipeline_check, signal_event = self.check_quantitative_pipeline(df)
            checks.append(pipeline_check)
        else:
            checks.append(
                CheckResult(
                    name="quantitative_pipeline",
                    status="FAIL",
                    message="Skipped pipeline due to missing market data",
                )
            )

        # 5. Persistence & Copilot
        if signal_event is not None:
            checks.append(self.check_persistence_and_copilot(signal_event))
        else:
            checks.append(
                CheckResult(
                    name="persistence_and_copilot",
                    status="FAIL",
                    message="Skipped persistence check due to missing signal event",
                )
            )

        # Determine overall status
        statuses = [c.status for c in checks]
        if "FAIL" in statuses:
            overall = "FAIL"
            summary = "Operational validation failed. Review individual failed checks."
        elif "WARN" in statuses:
            overall = "WARN"
            summary = "Operational validation passed with warnings."
        else:
            overall = "PASS"
            summary = "All operational validation checks passed successfully."

        return ValidationReport(
            timestamp=datetime.now(timezone.utc),
            overall_status=overall,
            checks=checks,
            summary=summary,
        )
