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
from .regime_classifier import RegimeClassifier
from .risk_engine import RiskEngine
from .signal_engine import SignalEngine
from .strategy_optimizer import StrategyOptimizer
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
        regime_classifier: RegimeClassifier | None = None,
        predictive_engine: Any | None = None,
        strategy_optimizer: StrategyOptimizer | None = None,
        predictive_mode: bool = False,
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
        self.regime_classifier = regime_classifier or RegimeClassifier()
        if predictive_engine is None:
            from .predictive_engine import PredictiveEngine

            self.predictive_engine = PredictiveEngine()
        else:
            self.predictive_engine = predictive_engine
        self.strategy_optimizer = strategy_optimizer or StrategyOptimizer()
        self.predictive_mode = predictive_mode
        self.engine = BacktestEngine(config=self.config)

    def run_backtest(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "1h",
        start_time: str | datetime | pd.Timestamp | int | None = None,
        end_time: str | datetime | pd.Timestamp | int | None = None,
        warmup_bars: int = 200,
        df: pd.DataFrame | None = None,
        predictive_mode: bool | None = None,
        calibrated_params: dict[str, Any] | None = None,
    ) -> BacktestReport:
        """Executes a full backtest pipeline for a given symbol and interval.

        Parameters:
        - symbol: Market ticker (e.g. 'BTCUSDT').
        - interval: Temporal timeframe (e.g. '1h').
        - start_time: Optional start timestamp slice.
        - end_time: Optional end timestamp slice.
        - warmup_bars: Minimum closed candles before generating trade signals (ensures EMA 200 convergence).
        - df: Optional in-memory DataFrame (if provided, bypasses disk dataset loading).
        - predictive_mode: Optional flag to enable predictive-enhanced decision flow (overrides instance default).
        - calibrated_params: Optional dictionary of OptimizedParameters by regime.

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
        use_predictive = (
            predictive_mode if predictive_mode is not None else self.predictive_mode
        )

        all_regimes = []
        if use_predictive and total_bars >= 25:
            all_regimes = self.regime_classifier.classify_series(enriched_df, warmup_bars=25)

        for t_idx in range(warmup_bars - 1, total_bars):
            sub_df = enriched_df.iloc[: t_idx + 1]
            profile = self.volume_profile.calculate(sub_df)
            analysis = self.market_engine.analyze(sub_df, profile)
            signal = self.signal_engine.evaluate(analysis, profile)
            risk = self.risk_engine.evaluate(analysis, profile)
            intel = self.intelligence.evaluate(analysis)
            score = self.quant_score.calculate(analysis, signal, risk)

            if use_predictive:
                reg_offset = t_idx - 24
                regime_res = all_regimes[reg_offset] if (all_regimes and 0 <= reg_offset < len(all_regimes)) else self.regime_classifier.classify(sub_df)
                h = self.predictive_engine.horizon_bars
                past_cutoff = max(0, reg_offset - h + 1)
                past_regimes = all_regimes[:past_cutoff] if all_regimes else None
                pred_res = self.predictive_engine.evaluate(
                    sub_df,
                    current_regime_res=regime_res,
                    precomputed_past_regimes=past_regimes,
                )
                opt_param = (
                    calibrated_params.get(regime_res.regime.value)
                    if calibrated_params
                    else None
                )
                decision = self.decision_engine.evaluate(
                    signal,
                    risk,
                    intel,
                    predictive=pred_res,
                    optimized_params=opt_param,
                    regime=regime_res.regime,
                    technical_score=score["score"],
                    predictive_mode=True,
                )
                sig_dir = (
                    TradeDirection.SHORT.value
                    if decision.direction == "SHORT"
                    else TradeDirection.LONG.value
                )
                tp_atr_mult = decision.tp_multiplier
                sl_atr_mult = decision.sl_multiplier
                quant_score_val = float(decision.final_score)
            else:
                decision = self.decision_engine.evaluate(signal, risk, intel)
                sig_dir = TradeDirection.LONG.value
                tp_atr_mult = None
                sl_atr_mult = None
                quant_score_val = float(score["score"])

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
                quant_score=quant_score_val,
                risk_level=risk["level"],
                atr=float(last_bar.get("atr", 0.0)),
                poc=float(profile["poc"]),
                vah=float(profile["vah"]),
                val=float(profile["val"]),
                direction=sig_dir,
                tp_atr_multiple=tp_atr_mult,
                sl_atr_multiple=sl_atr_mult,
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
