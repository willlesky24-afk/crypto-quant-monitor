from __future__ import annotations

import logging
from datetime import datetime
from numbers import Integral
from typing import Any

import numpy as np
import pandas as pd

from .backtest_engine import BacktestEngine
from .backtest_metrics import CRYPTO_24_7_PERIODS, BacktestMetricsCalculator
from .backtest_models import (
    BacktestConfig,
    BacktestReport,
    BacktestValidationError,
    CalibrationState,
    DatasetProvenance,
    OptimizationUnavailableError,
    SignalEvent,
    TradeDirection,
)
from .candle_validator import INTERVAL_TIMEDELTAS
from .dataset_manager import HistoricalDatasetManager
from .decision_engine import DecisionEngine
from .engine import MarketEngine
from .indicators import TechnicalIndicators
from .market_intelligence import MarketIntelligence
from .parquet_store import ParquetStore
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
        calibration_required: bool = False,
    ) -> BacktestReport:
        """Executes a full backtest pipeline for a given symbol and interval.

        Parameters:
        - symbol: Market ticker (e.g. 'BTCUSDT').
        - interval: Temporal timeframe (e.g. '1h').
        - start_time: Optional start timestamp slice.
        - end_time: Optional end timestamp slice.
        - warmup_bars: Requested closed candles before signals; the default observes
          200 EMA samples. Component minimums still apply to smaller requests.
        - df: Optional in-memory DataFrame (if provided, bypasses disk dataset loading).
        - predictive_mode: Optional flag to enable predictive-enhanced decision flow (overrides instance default).
        - calibrated_params: Optional dictionary of OptimizedParameters by regime.
        - calibration_required: Explicit request for verified optimization; omission
          preserves the existing uncalibrated/manual/preset execution contract.

        Returns:
        - BacktestReport containing trade log, performance metrics, and equity curve.
        """
        self.engine.validate_config()
        if (
            isinstance(warmup_bars, bool)
            or not isinstance(warmup_bars, Integral)
            or warmup_bars < 1
        ):
            raise BacktestValidationError("warmup_bars debe ser un entero positivo.")
        sym = symbol.strip().upper()
        inv = interval.strip().lower()
        provenance = DatasetProvenance()
        use_predictive = (
            predictive_mode if predictive_mode is not None else self.predictive_mode
        )
        if calibration_required and not use_predictive:
            raise OptimizationUnavailableError(
                "Optimización no disponible: modo predictivo desactivado."
            )
        if calibration_required and (
            not isinstance(calibrated_params, dict) or not calibrated_params
        ):
            raise OptimizationUnavailableError(
                "Optimización no disponible: no hay parámetros calibrados."
            )
        if calibration_required:
            for params in calibrated_params.values():
                DecisionEngine.validate_calibration_params(params, required=True)

        # The rolling volume mean needs 20 bars. Predictive mode also needs its
        # declared history and the regime classifier's minimum, regardless of
        # how many candles will eventually be added to the dataset.
        minimum_history = 20
        if use_predictive:
            minimum_history = max(
                minimum_history,
                self.regime_classifier.min_bars,
                self.predictive_engine.min_history_bars,
            )
        effective_warmup = max(int(warmup_bars), minimum_history)

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
            if (
                type(self.dataset_manager) is HistoricalDatasetManager
                and type(self.dataset_manager.store) is ParquetStore
            ):
                candidate = raw_df.attrs.get("_controlled_provenance")
                if isinstance(candidate, DatasetProvenance):
                    provenance = candidate

        if len(raw_df) > 0:
            raw_df["timestamp"] = self.engine.validate_chronology(raw_df)

        if len(raw_df) == 0 or len(raw_df) < effective_warmup:
            logger.warning(
                "Dataset para %s %s tiene solo %d velas (mínimo requerido: %d para warm-up).",
                sym,
                inv,
                len(raw_df),
                effective_warmup,
            )
            empty_metrics = BacktestMetricsCalculator.calculate_metrics(
                [],
                [],
                self.config.initial_capital,
                sharpe_unavailable_reason=provenance.reason,
            )
            return self._build_report(
                config=self.config,
                symbol=sym,
                interval=inv,
                candles_df=raw_df,
                trades=[],
                equity_curve=[],
                metrics=empty_metrics,
                provenance=provenance,
                calibration_state=(
                    CalibrationState.AVAILABLE.value
                    if calibration_required
                    else CalibrationState.NOT_REQUESTED.value
                ),
            )

        # 2. Enrich indicators across the full causal dataset
        enriched_df = self.indicators.calculate_all(raw_df.copy())
        enriched_df = enriched_df.reset_index(drop=True)
        # Provenance attrs are deep-copied by pandas on every row access; they
        # stay on the report via raw_df, not inside the per-bar loop (v3.0 D6).
        enriched_df.attrs = {}

        # 3. Generate Signals Step-by-Step with Strict Look-Ahead Bias Prevention
        signals: list[SignalEvent] = []
        total_bars = len(enriched_df)
        all_regimes = []
        if use_predictive and total_bars >= 25:
            all_regimes = self.regime_classifier.classify_series(
                enriched_df, warmup_bars=25
            )
        all_regime_values = np.array(
            [r.regime.value for r in all_regimes], dtype=object
        )

        for t_idx in range(effective_warmup - 1, total_bars):
            sub_df = enriched_df.iloc[: t_idx + 1]
            profile = self.volume_profile.calculate(sub_df)
            analysis = self.market_engine.analyze(sub_df, profile)
            signal = self.signal_engine.evaluate(analysis, profile)
            risk = self.risk_engine.evaluate(analysis, profile)
            intel = self.intelligence.evaluate(analysis)
            score = self.quant_score.calculate(analysis, signal, risk)

            if use_predictive:
                reg_offset = t_idx - 24
                regime_res = (
                    all_regimes[reg_offset]
                    if (all_regimes and 0 <= reg_offset < len(all_regimes))
                    else self.regime_classifier.classify(sub_df)
                )
                h = self.predictive_engine.horizon_bars
                past_cutoff = max(0, reg_offset - h + 1)
                past_regimes = all_regimes[:past_cutoff] if all_regimes else None
                pred_res = self.predictive_engine.evaluate(
                    sub_df,
                    current_regime_res=regime_res,
                    precomputed_past_regimes=past_regimes,
                    precomputed_past_regime_values=(
                        all_regime_values[:past_cutoff] if all_regimes else None
                    ),
                )
                opt_param = (
                    calibrated_params.get(regime_res.regime.value)
                    if calibrated_params
                    else None
                )
                if calibration_required and opt_param is None:
                    raise OptimizationUnavailableError(
                        f"Optimización no disponible: faltan parámetros para {regime_res.regime.value}."
                    )
                decision = self.decision_engine.evaluate(
                    signal,
                    risk,
                    intel,
                    predictive=pred_res,
                    optimized_params=opt_param,
                    calibration_required=calibration_required,
                    regime=regime_res.regime,
                    technical_score=score["score"],
                    technical_score_short=score.get("score_short"),
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
        sharpe_eligible = (
            provenance.status == "CONTROLLED_INGESTION"
            and provenance.provider == "BINANCE_PUBLIC_SPOT_REST"
            and provenance.instrument_type == "CRYPTO_SPOT"
            and provenance.calendar == "24_7"
            and provenance.interval == inv
            and provenance.temporal_validation == "VALID"
            and provenance.content_sha256 is not None
            and inv in CRYPTO_24_7_PERIODS
        )
        metrics = BacktestMetricsCalculator.calculate_metrics(
            trades=trades,
            equity_curve=equity_curve,
            initial_capital=self.config.initial_capital,
            periods_per_year=CRYPTO_24_7_PERIODS[inv] if sharpe_eligible else None,
            expected_interval=INTERVAL_TIMEDELTAS[inv] if sharpe_eligible else None,
            sharpe_unavailable_reason=None
            if sharpe_eligible
            else (provenance.reason or "Procedencia o calendario no acreditado."),
        )

        return self._build_report(
            config=self.config,
            symbol=sym,
            interval=inv,
            candles_df=enriched_df,
            trades=trades,
            equity_curve=equity_curve,
            metrics=metrics,
            provenance=provenance,
            calibration_state=(
                CalibrationState.AVAILABLE.value
                if calibration_required
                else CalibrationState.NOT_REQUESTED.value
            ),
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
        provenance: DatasetProvenance | None = None,
        calibration_state: str = CalibrationState.NOT_REQUESTED.value,
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
            gross_expectancy_r=metrics["gross_expectancy_r"],
            net_expectancy_r=metrics["net_expectancy_r"],
            r_verified_trades=metrics["r_verified_trades"],
            r_excluded_trades=metrics["r_excluded_trades"],
            r_coverage_status=metrics["r_coverage_status"],
            r_unavailable_reason=metrics["r_unavailable_reason"],
            max_drawdown_pct=metrics["max_drawdown_pct"],
            max_drawdown_usd=metrics["max_drawdown_usd"],
            max_drawdown_duration_bars=metrics["max_drawdown_duration_bars"],
            avg_mfe_pct=metrics["avg_mfe_pct"],
            avg_mae_pct=metrics["avg_mae_pct"],
            mfe_exact_avg_pct=metrics["mfe_exact_avg_pct"],
            mae_exact_avg_pct=metrics["mae_exact_avg_pct"],
            mfe_exact_trades=metrics["mfe_exact_trades"],
            mae_exact_trades=metrics["mae_exact_trades"],
            mfe_exact_denominator=metrics["mfe_exact_denominator"],
            mae_exact_denominator=metrics["mae_exact_denominator"],
            mfe_total_trades=metrics["mfe_total_trades"],
            mae_total_trades=metrics["mae_total_trades"],
            mfe_coverage_status=metrics["mfe_coverage_status"],
            mae_coverage_status=metrics["mae_coverage_status"],
            calibration_state=calibration_state,
            avg_bars_held=metrics["avg_bars_held"],
            total_gross_pnl=metrics["total_gross_pnl"],
            total_fees_paid=metrics["total_fees_paid"],
            total_net_pnl=metrics["total_net_pnl"],
            return_on_capital_pct=metrics["return_on_capital_pct"],
            sharpe_ratio=metrics["sharpe_ratio"],
            sharpe_unavailable_reason=metrics["sharpe_unavailable_reason"],
            calmar_ratio=metrics["calmar_ratio"],
            data_provenance=provenance or DatasetProvenance(),
            trades=trades,
            equity_curve=equity_curve,
        )
