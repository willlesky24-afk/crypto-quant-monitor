from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

try:
    from .constants import (
        DECISION_FAVORABLE,
        DECISION_WAIT_CONFIRMATION,
        DECISION_WEAK_CONTEXT,
        RISK_LOW,
    )
except ImportError:  # Streamlit execution with ``src`` on sys.path.
    from constants import (
        DECISION_FAVORABLE,
        DECISION_WAIT_CONFIRMATION,
        DECISION_WEAK_CONTEXT,
        RISK_LOW,
    )

if TYPE_CHECKING:
    from src.predictive_engine import PredictiveResult
    from src.regime_classifier import MarketRegime
    from src.strategy_optimizer import OptimizedParameters


@dataclass(frozen=True)
class DecisionResult:
    """Traceable, immutable record of the final strategy decision."""

    decision: str
    confidence: float
    positives: list[str]
    warnings: list[str]
    market_state: str
    signal: str = ""
    technical_score: float = 0.0
    predictive_score: float = 0.0
    regime: str = ""
    tp_multiplier: float = 2.0
    sl_multiplier: float = 1.0
    reasoning: str = ""
    final_score: float = 0.0
    direction: str = "LONG"

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DecisionEngine:
    """Enhanced decision engine integrating technical signals, predictive scoring, and risk optimization.

    Combines:
    1. Technical analysis (QuantScore, SignalEngine, RiskEngine)
    2. Predictive engine (PredictiveScore, conditional probabilities)
    3. Strategy optimizer (Empirical MFE/MAE calibrated TP and SL multipliers)

    Maintains 100% backward compatibility via `legacy_mode=True` or `predictive_mode=False`.
    """

    def __init__(
        self,
        technical_weight: float = 0.60,
        predictive_weight: float = 0.40,
        legacy_mode: bool = False,
    ) -> None:
        if not (0.0 <= technical_weight <= 1.0):
            raise ValueError(f"technical_weight debe estar en [0, 1], recibido {technical_weight}")
        if not (0.0 <= predictive_weight <= 1.0):
            raise ValueError(f"predictive_weight debe estar en [0, 1], recibido {predictive_weight}")

        total_weight = technical_weight + predictive_weight
        if total_weight > 0:
            self.technical_weight = technical_weight / total_weight
            self.predictive_weight = predictive_weight / total_weight
        else:
            self.technical_weight = 1.0
            self.predictive_weight = 0.0

        self.legacy_mode = legacy_mode

    def evaluate(
        self,
        signal: dict[str, Any],
        risk: dict[str, Any],
        intelligence: dict[str, Any],
        predictive: PredictiveResult | dict[str, Any] | None = None,
        optimized_params: OptimizedParameters | dict[str, Any] | None = None,
        regime: str | MarketRegime | None = None,
        technical_score: float | None = None,
        legacy_mode: bool | None = None,
        predictive_mode: bool | None = None,
    ) -> DecisionResult:
        """Evaluates market state, risks, predictive probabilities, and calibrated parameters."""
        # 1. Determine execution mode (legacy vs enhanced predictive)
        is_legacy = (
            legacy_mode
            if legacy_mode is not None
            else (not predictive_mode if predictive_mode is not None else self.legacy_mode)
        )

        # Baseline technical confidence adjustment
        raw_confidence = float(signal.get("confidence", 0.0))
        risk_adjustment = float(risk.get("adjustment", 0.0))
        tech_confidence = max(0.0, min(raw_confidence - risk_adjustment, 100.0))

        positives = list(signal.get("positives", []))
        warnings = list(signal.get("risks", [])) + list(risk.get("risks", []))
        market_state = str(intelligence.get("state", ""))
        sig_state = str(signal.get("state", ""))

        tech_score_val = (
            float(technical_score)
            if technical_score is not None
            else float(signal.get("quant_score", tech_confidence))
        )

        # -----------------------------------------------------------------
        # Mode A: Legacy Execution (100% v1.8 Bit-for-Bit Deterministic)
        # -----------------------------------------------------------------
        if is_legacy or predictive is None:
            if tech_confidence >= 80.0 and risk.get("level") == RISK_LOW:
                decision = DECISION_FAVORABLE
            elif tech_confidence >= 60.0:
                decision = DECISION_WAIT_CONFIRMATION
            else:
                decision = DECISION_WEAK_CONTEXT

            reasoning = (
                f"Legacy Rule: TechConfidence={tech_confidence:.1f} (Risk={risk.get('level')}). "
                f"Predictive and optimizer enhancements disabled."
            )

            return DecisionResult(
                decision=decision,
                confidence=round(tech_confidence, 2),
                positives=positives,
                warnings=warnings,
                market_state=market_state,
                signal=sig_state,
                technical_score=round(tech_score_val, 2),
                predictive_score=0.0,
                regime=str(getattr(regime, "value", regime) or ""),
                tp_multiplier=2.0,
                sl_multiplier=1.0,
                reasoning=reasoning,
                final_score=round(tech_confidence, 2),
                direction="LONG",
            )

        # -----------------------------------------------------------------
        # Mode B: Enhanced Predictive Decision
        # -----------------------------------------------------------------
        pred_score = float(
            getattr(
                predictive,
                "predictive_score",
                predictive.get("predictive_score", 0.5) if isinstance(predictive, dict) else 0.5,
            )
        )
        pred_dir = str(
            getattr(
                predictive,
                "direction_bias",
                predictive.get("direction_bias", "LONG") if isinstance(predictive, dict) else "LONG",
            )
        )

        regime_str = (
            str(getattr(regime, "value", regime))
            if regime is not None
            else str(
                getattr(predictive, "features_used", {}).get("regime", "")
                if hasattr(predictive, "features_used")
                else (
                    predictive.get("features_used", {}).get("regime", "")
                    if isinstance(predictive, dict)
                    else ""
                )
            )
        )

        # Adaptive Weighted Confidence: FinalScore = W_tech * TechScore + W_pred * (PredScore * 100)
        pred_confidence = pred_score * 100.0
        final_confidence = (
            self.technical_weight * tech_confidence + self.predictive_weight * pred_confidence
        )
        final_confidence = max(0.0, min(100.0, final_confidence))

        final_score = (
            self.technical_weight * tech_score_val + self.predictive_weight * pred_confidence
        )
        final_score = max(0.0, min(100.0, final_score))

        # Directional mapping (LONG vs SHORT)
        if pred_dir == "SHORT" and (
            regime_str in {"TRENDING_BEAR", "HIGH_VOLATILITY_EXPANSION"} or tech_score_val < 50.0
        ):
            direction = "SHORT"
        else:
            direction = "LONG"

        # Optimized TP and SL parameters
        if optimized_params is not None:
            tp_multiplier = float(
                getattr(
                    optimized_params,
                    "atr_tp_multiplier",
                    optimized_params.get("atr_tp_multiplier", 3.0)
                    if isinstance(optimized_params, dict)
                    else 3.0,
                )
            )
            sl_multiplier = float(
                getattr(
                    optimized_params,
                    "atr_sl_multiplier",
                    optimized_params.get("atr_sl_multiplier", 1.5)
                    if isinstance(optimized_params, dict)
                    else 1.5,
                )
            )
        else:
            # Safe defaults
            tp_multiplier = 3.0
            sl_multiplier = 1.5

        # Decision classification
        if final_confidence >= 80.0 and risk.get("level") == RISK_LOW:
            decision = DECISION_FAVORABLE
        elif final_confidence >= 60.0:
            decision = DECISION_WAIT_CONFIRMATION
        else:
            decision = DECISION_WEAK_CONTEXT

        # Enriched diagnostics
        if pred_score >= 0.70:
            positives.append(
                f"Fuerte alineación probabilística ({pred_score:.2f}) en régimen {regime_str or 'N/A'}"
            )
        elif pred_score < 0.40:
            warnings.append(f"Baja probabilidad condicional futura ({pred_score:.2f})")

        reasoning = (
            f"Enhanced Decision: Technical={tech_confidence:.1f} (w={self.technical_weight:.2f}) + "
            f"Predictive={pred_confidence:.1f} (w={self.predictive_weight:.2f}) -> "
            f"FinalConfidence={final_confidence:.1f}, FinalScore={final_score:.1f}. "
            f"Regime={regime_str or 'N/A'}, Direction={direction}, "
            f"TP={tp_multiplier:.2f}x ATR, SL={sl_multiplier:.2f}x ATR"
        )

        return DecisionResult(
            decision=decision,
            confidence=round(final_confidence, 2),
            positives=positives,
            warnings=warnings,
            market_state=market_state,
            signal=sig_state,
            technical_score=round(tech_score_val, 2),
            predictive_score=round(pred_score, 4),
            regime=regime_str,
            tp_multiplier=round(tp_multiplier, 2),
            sl_multiplier=round(sl_multiplier, 2),
            reasoning=reasoning,
            final_score=round(final_score, 2),
            direction=direction,
        )
