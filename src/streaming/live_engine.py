from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import pandas as pd

from src.backtest_models import CalibrationState, OptimizationUnavailableError
from src.decision_engine import DecisionEngine, DecisionResult
from src.engine import MarketEngine
from src.indicators import TechnicalIndicators
from src.market_intelligence import MarketIntelligence
from src.notifications.dispatcher import NotificationDispatcher
from src.notifications.models import NotificationResult, SignalEvent
from src.predictive_engine import PredictiveEngine
from src.quant_score import QuantScore
from src.regime_classifier import RegimeClassifier
from src.risk_engine import RiskEngine
from src.signal_engine import SignalEngine
from src.streaming.candle_aggregator import CandleAggregator, KlineEvent
from src.volume_profile import VolumeProfile

logger = logging.getLogger(__name__)


class LiveExecutionEngine:
    """Real-time execution engine coordinating stream ingestion, quantitative analysis,

    predictive scoring, decision generation, and notification routing.

    Preserves strict causality and zero look-ahead bias:
    Signals and decisions are generated exclusively on fully closed candles (T).
    """

    def __init__(
        self,
        symbol: str,
        interval: str,
        dispatcher: NotificationDispatcher | None = None,
        calibrated_params: dict[str, Any] | None = None,
        predictive_mode: bool = True,
        warm_up_bars: int = 200,
        calibration_required: bool = False,
    ) -> None:
        self.symbol = symbol.strip().upper()
        self.interval = interval.strip().lower()
        self.dispatcher = dispatcher
        # The explicit request flag is the source of truth. None and {} remain
        # legitimate on legacy, uncalibrated calls but cannot satisfy a request.
        self.calibration_required = calibration_required
        self.calibrated_params = calibrated_params
        if calibration_required and (
            not isinstance(calibrated_params, dict) or not calibrated_params
        ):
            raise OptimizationUnavailableError(
                "Optimización no disponible: no hay parámetros calibrados."
            )
        if calibration_required and not predictive_mode:
            raise OptimizationUnavailableError(
                "Optimización no disponible: modo predictivo desactivado."
            )
        if calibration_required:
            for params in calibrated_params.values():
                DecisionEngine.validate_calibration_params(params, required=True)
        self.calibration_state = (
            CalibrationState.AVAILABLE.value
            if calibration_required
            else CalibrationState.NOT_REQUESTED.value
        )
        self.predictive_mode = predictive_mode
        self.warm_up_bars = warm_up_bars

        # Reuse validated quantitative pipeline components (no duplicated math)
        self.indicators = TechnicalIndicators()
        self.volume_profile = VolumeProfile()
        self.market_engine = MarketEngine()
        self.signal_engine = SignalEngine()
        self.risk_engine = RiskEngine()
        self.intelligence = MarketIntelligence()
        self.quant_score = QuantScore()
        self.regime_classifier = RegimeClassifier()
        self.predictive_engine = PredictiveEngine()
        self.decision_engine = DecisionEngine()

        # Engine state and listeners
        self._signal_history: list[SignalEvent] = []
        self._signal_listeners: list[Callable[[SignalEvent], None]] = []
        self._last_decision: DecisionResult | None = None
        self._last_signal: SignalEvent | None = None

    @property
    def signal_history(self) -> list[SignalEvent]:
        """Chronological list of all generated signal events."""
        return list(self._signal_history)

    @property
    def last_signal(self) -> SignalEvent | None:
        """Most recent signal event emitted by the engine."""
        return self._last_signal

    @property
    def last_decision(self) -> DecisionResult | None:
        """Most recent decision result produced by DecisionEngine."""
        return self._last_decision

    def on_signal(self, callback: Callable[[SignalEvent], None]) -> None:
        """Register a callback invoked whenever a new SignalEvent is generated."""
        self._signal_listeners.append(callback)

    def attach_aggregator(self, aggregator: CandleAggregator) -> None:
        """Connect this execution engine directly to a CandleAggregator."""
        aggregator._on_candle_close = self.on_candle_closed
        logger.info(f"[{self.symbol} {self.interval}] Attached to CandleAggregator.")

    def on_candle_closed(
        self,
        df: pd.DataFrame,
        candle_event: KlineEvent,
    ) -> tuple[SignalEvent | None, DecisionResult | None, list[NotificationResult]]:
        """Process a newly closed candle T through the quantitative and predictive pipeline.

        Returns:
            Tuple of (SignalEvent, DecisionResult, list[NotificationResult])
        """
        if self.calibration_required:
            # A rejected new bar must not expose an earlier calibrated decision
            # as though it belonged to the rejected observation.
            self._last_decision = None
            self._last_signal = None
        # 1. Warm-up verification
        if len(df) < self.warm_up_bars:
            logger.info(
                f"[{self.symbol} {self.interval}] Insufficient candles for warm-up: {len(df)}/{self.warm_up_bars}. Skipping analysis."
            )
            return None, None, []

        # 2. Descriptive Analysis Layer (t <= T)
        df_enriched = self.indicators.calculate_all(df)
        profile = self.volume_profile.calculate(df_enriched)
        analysis = self.market_engine.analyze(df_enriched, profile)
        signal = self.signal_engine.evaluate(analysis, profile)

        risk = self.risk_engine.evaluate(analysis, profile)
        intel = self.intelligence.evaluate(analysis)
        score = self.quant_score.calculate(analysis, signal, risk)

        last_bar = df_enriched.iloc[-1]
        price = float(last_bar["close"])
        atr = float(last_bar.get("atr", 0.0))

        # 3. Predictive & Optimization Layer (t > T)
        if self.predictive_mode:
            regime_res = self.regime_classifier.classify(df_enriched)
            pred_res = self.predictive_engine.evaluate(
                df_enriched, current_regime_res=regime_res
            )

            opt_param = (
                self.calibrated_params.get(regime_res.regime.value)
                if self.calibrated_params
                else None
            )
            if self.calibration_required and opt_param is None:
                raise OptimizationUnavailableError(
                    f"Optimización no disponible: faltan parámetros para {regime_res.regime.value}."
                )

            decision = self.decision_engine.evaluate(
                signal=signal,
                risk=risk,
                intelligence=intel,
                predictive=pred_res,
                optimized_params=opt_param,
                calibration_required=self.calibration_required,
                regime=regime_res.regime,
                technical_score=score["score"],
                technical_score_short=score.get("score_short"),
                predictive_mode=True,
            )

            regime_val = regime_res.regime.value
            pred_score_val = float(pred_res.predictive_score)
            p_cont = float(pred_res.probability_continuation)
            p_rev = float(pred_res.probability_reversal)

        else:
            decision = self.decision_engine.evaluate(
                signal=signal,
                risk=risk,
                intelligence=intel,
                predictive_mode=False,
            )
            regime_val = "UNKNOWN"
            pred_score_val = 0.0
            p_cont = 0.0
            p_rev = 0.0

        # 4. Indicative risk plan; a closed candle is not an entry confirmation.
        plan = self.risk_engine.plan_from_decision(
            decision=decision.decision,
            direction=decision.direction,
            reference_price=price,
            atr=atr,
            sl_multiplier=decision.sl_multiplier,
            tp_multiplier=decision.tp_multiplier,
        )

        # 5. Construct Single Source of Truth: SignalEvent
        ts = pd.Timestamp(last_bar["timestamp"])
        sig_id = f"sig-{self.symbol}-{self.interval}-{int(ts.timestamp())}"

        meta = {
            "poc": float(profile.get("poc", 0.0)),
            "vah": float(profile.get("vah", 0.0)),
            "val": float(profile.get("val", 0.0)),
            "atr": atr,
            "p_continuation": p_cont,
            "p_reversal": p_rev,
            "market_state": decision.market_state,
            "positives": list(decision.positives),
            "warnings": list(decision.warnings),
            "signal_status": plan["status"],
            "entry_confirmed": plan["entry_confirmed"],
            "entry_price": plan["entry_price"],
            "risk_distance": plan["risk_distance"],
            "reward_distance": plan["reward_distance"],
            "risk_reward_ratio": plan["gross_risk_reward"],
            "risk_reward_basis": "bruto_sin_costes",
            "risk_reason": plan["reason"],
            "risk_methodology": plan["methodology"],
            "risk_levels_source": "RiskEngine",
            "decision_label": decision.decision,
        }

        signal_event = SignalEvent(
            timestamp=ts,
            symbol=self.symbol,
            timeframe=self.interval,
            action="WAIT",  # No activation rule or confirmed fill exists.
            direction=plan["direction"],
            confidence=float(decision.confidence),
            predictive_score=pred_score_val,
            regime=regime_val,
            reasoning=f"{decision.reasoning} Estado: {plan['status']}. {plan['reason']}",
            price=price,
            quant_score=float(score["score"]),
            stop_loss=plan["stop_loss"],
            take_profit=plan["take_profit"],
            signal_id=sig_id,
            metadata=meta,
        )

        # 6. Update Engine State & Emit to Listeners
        self._last_decision = decision
        self._last_signal = signal_event
        self._signal_history.append(signal_event)

        for listener in self._signal_listeners:
            try:
                listener(signal_event)
            except Exception as exc:
                logger.error(f"Error in signal listener: {exc}", exc_info=True)

        # 7. Only confirmed, validated entries may be dispatched as operational alerts.
        notif_results: list[NotificationResult] = []
        if (
            self.dispatcher is not None
            and plan["status"] == "ACTIVADA"
            and plan["entry_confirmed"]
        ):
            try:
                notif_results = self.dispatcher.dispatch_signal(signal_event)
            except Exception as exc:
                logger.error(f"Error in notification dispatcher: {exc}", exc_info=True)
        elif self.dispatcher is not None:
            logger.info(
                "[%s %s] Informational event %s not dispatched: %s",
                self.symbol,
                self.interval,
                plan["status"],
                plan["reason"],
            )

        return signal_event, decision, notif_results
