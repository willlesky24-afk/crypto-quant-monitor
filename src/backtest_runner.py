from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd

from .backtest_engine import BacktestEngine
from .backtest_metrics import BacktestMetricsCalculator
from .backtest_models import BacktestConfig, BacktestReport, SignalEvent, TradeDirection
from .dataset_manager import HistoricalDatasetManager
from .decision_engine import DecisionEngine
from .engine import MarketEngine
from .indicators import TechnicalIndicators
from .market_intelligence import MarketIntelligence
from .quant_score import QuantScore
from .risk_engine import RiskEngine
from .signal_engine import SignalEngine
from .volume_profile import VolumeProfile

logger = logging.getLogger(__name__)


class BacktestRunner:
    """High-level facade that coordinates historical dataset loading, causal feature generation,

    pure signal evaluation, chronological execution simulation, and performance reporting.
    """

    def __init__(
        self,
        config: BacktestConfig | None = None,
        dataset_manager: HistoricalDatasetManager | None = None,
        indicators: TechnicalIndicators | None = None,
        volume_profile: VolumeProfile | None = None,
        market_engine: MarketEngine | None = None,
        signal_engine: SignalEngine | None = None,
        risk_engine: RiskEngine | None = None,
        decision_engine: DecisionEngine | None = None,
        quant_score: QuantScore | None = None,
        market_intelligence: MarketIntelligence | None = None,
    ):
        self.config = config or BacktestConfig()
        self.dataset_manager = dataset_manager or HistoricalDatasetManager()
        self.indicators = indicators or TechnicalIndicators()
        self.volume_profile = volume_profile or VolumeProfile()
        self.market_engine = market_engine or MarketEngine()
        self.signal_engine = signal_engine or SignalEngine()
        self.risk_engine = risk_engine or RiskEngine()
        self.decision_engine = decision_engine or DecisionEngine()
        self.quant_score = quant_score or QuantScore()
        self.intelligence = market_intelligence or MarketIntelligence()
        self.engine = BacktestEngine(config=self.config)

    def run_backtest(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "1h",
        start_time: str | datetime | pd.Timestamp | int | None = None,
        end_time: str | datetime | pd.Timestamp | int | None = None,
        warmup_bars: int = 200,
        df: pd.DataFrame | None = None,
    ) -> BacktestReport:
        """Executes a full backtest pipeline for a given symbol and interval.

        Parameters:
        - symbol: Market ticker (e.g. 'BTCUSDT').
        - interval: Temporal timeframe (e.g. '1h').
        - start_time: Optional start timestamp slice.
        - end_time: Optional end timestamp slice.
        - warmup_bars: Minimum closed candles before generating trade signals (ensures EMA 200 convergence).
        - df: Optional in-memory DataFrame (if provided, bypasses disk dataset loading).

        Returns:
        - BacktestReport containing trade log, performance metrics, and equity curve.
        """
        sym = symbol.strip().upper()
        inv = interval.strip().lower()

        # 1. Load data
        if df is not None:
            raw_df = df.copy()
        else:
            raw_df = self.dataset_manager.load_dataset(
                symbol=sym,
                interval=inv,
                start_time=start_time,
                end_time=end_time,
            )

        if raw_df.empty or len(raw_df) < warmup_bars:
            logger.warning(
                "Dataset para %s %s tiene solo %d velas (mínimo requerido: %d para warm-up).",
                sym,
                inv,
                len(raw_df),
                warmup_bars,
            )
            empty_metrics = BacktestMetricsCalculator.calculate_metrics([], [], self.config.initial_capital)
            return self._build_report(
                config=self.config,
                symbol=sym,
                interval=inv,
                candles_df=raw_df,
                trades=[],
                equity_curve=[],
                metrics=empty_metrics,
            )

        # 2. Enrich indicators across the full causal dataset
        enriched_df = self.indicators.calculate_all(raw_df.copy())
        enriched_df["timestamp"] = pd.to_datetime(enriched_df["timestamp"], utc=True)
        enriched_df = enriched_df.sort_values("timestamp").reset_index(drop=True)

        # 3. Generate Signals Step-by-Step with Strict Look-Ahead Bias Prevention
        signals: list[SignalEvent] = []
        total_bars = len(enriched_df)

        for t_idx in range(warmup_bars - 1, total_bars):
            sub_df = enriched_df.iloc[: t_idx + 1]
            profile = self.volume_profile.calculate(sub_df)
            analysis = self.market_engine.analyze(sub_df, profile)
            signal = self.signal_engine.evaluate(analysis, profile)
            risk = self.risk_engine.evaluate(analysis, profile)
            intel = self.intelligence.evaluate(analysis)
            decision = self.decision_engine.evaluate(signal, risk, intel)
            score = self.quant_score.calculate(analysis, signal, risk)

            last_bar = sub_df.iloc[-1]
            sig_event = SignalEvent(
                signal_id=f"sig-{sym}-{inv}-{t_idx}",
                symbol=sym,
                timeframe=inv,
                candle_timestamp=last_bar["timestamp"],
                price_at_signal=float(last_bar["close"]),
                signal_state=signal["state"],
                confidence=float(decision["confidence"]),
                decision=decision["decision"],
                quant_score=float(score["score"]),
                risk_level=risk["level"],
                atr=float(last_bar.get("atr", 0.0)),
                poc=float(profile["poc"]),
                vah=float(profile["vah"]),
                val=float(profile["val"]),
                direction=TradeDirection.LONG.value,
            )
            signals.append(sig_event)

        # 4. Run Execution Simulation (Entries on Open(T+1))
        trades, equity_curve = self.engine.run(df=enriched_df, signals=signals)

        # 5. Compute Quantitative Metrics
        metrics = BacktestMetricsCalculator.calculate_metrics(
            trades=trades,
            equity_curve=equity_curve,
            initial_capital=self.config.initial_capital,
        )

        return self._build_report(
            config=self.config,
            symbol=sym,
            interval=inv,
            candles_df=enriched_df,
            trades=trades,
            equity_curve=equity_curve,
            metrics=metrics,
        )

    @staticmethod
    def _build_report(
        config: BacktestConfig,
        symbol: str,
        interval: str,
        candles_df: pd.DataFrame,
        trades: list[Any],
        equity_curve: list[Any],
        metrics: dict[str, Any],
    ) -> BacktestReport:
        start_ts = str(candles_df["timestamp"].min()) if not candles_df.empty else ""
        end_ts = str(candles_df["timestamp"].max()) if not candles_df.empty else ""

        return BacktestReport(
            config=config,
            symbol=symbol,
            timeframe=interval,
            start_time=start_ts,
            end_time=end_ts,
            total_candles=len(candles_df),
            total_trades=metrics["total_trades"],
            winning_trades=metrics["winning_trades"],
            losing_trades=metrics["losing_trades"],
            win_rate_pct=metrics["win_rate_pct"],
            profit_factor=metrics["profit_factor"],
            expectancy=metrics["expectancy"],
            expectancy_r=metrics["expectancy_r"],
            max_drawdown_pct=metrics["max_drawdown_pct"],
            max_drawdown_usd=metrics["max_drawdown_usd"],
            max_drawdown_duration_bars=metrics["max_drawdown_duration_bars"],
            avg_mfe_pct=metrics["avg_mfe_pct"],
            avg_mae_pct=metrics["avg_mae_pct"],
            avg_bars_held=metrics["avg_bars_held"],
            total_gross_pnl=metrics["total_gross_pnl"],
            total_fees_paid=metrics["total_fees_paid"],
            total_net_pnl=metrics["total_net_pnl"],
            return_on_capital_pct=metrics["return_on_capital_pct"],
            sharpe_ratio=metrics["sharpe_ratio"],
            calmar_ratio=metrics["calmar_ratio"],
            trades=trades,
            equity_curve=equity_curve,
        )
