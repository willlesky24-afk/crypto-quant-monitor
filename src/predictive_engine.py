from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .indicators import TechnicalIndicators
from .regime_classifier import MarketRegime, RegimeClassifier, RegimeResult


@dataclass(frozen=True)
class PredictiveResult:
    """Immutable report containing conditional probabilistic market projections."""

    timestamp: pd.Timestamp
    probability_continuation: float
    probability_reversal: float
    predictive_score: float
    confidence: float
    regime_context: str
    direction_bias: str
    features_used: dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "timestamp": str(self.timestamp),
            "probability_continuation": round(float(self.probability_continuation), 4),
            "probability_reversal": round(float(self.probability_reversal), 4),
            "predictive_score": round(float(self.predictive_score), 4),
            "confidence": round(float(self.confidence), 4),
            "regime_context": self.regime_context,
            "direction_bias": self.direction_bias,
            "features_used": {
                k: round(float(v), 6) if isinstance(v, (int, float, np.floating, np.integer)) else v
                for k, v in self.features_used.items()
            },
        }


class PredictiveEngine:
    """Decoupled probabilistic estimation engine for conditional market scenarios.

    Computes empirical conditional probabilities of continuation and reversal
    strictly using historical data up to candle T (t <= T). Does NOT alter or replace
    the descriptive analysis (MarketAnalyzer, MarketReport, QuantScore).
    """

    def __init__(
        self,
        regime_classifier: RegimeClassifier | None = None,
        indicators: TechnicalIndicators | None = None,
        horizon_bars: int = 5,
        min_history_bars: int = 35,
    ):
        self.regime_classifier = regime_classifier or RegimeClassifier()
        self.indicators = indicators or TechnicalIndicators()
        self.horizon_bars = horizon_bars
        self.min_history_bars = min_history_bars

    def evaluate(self, df: pd.DataFrame) -> PredictiveResult:
        """Estimates conditional probabilities and calculates PredictiveScore for candle T.

        Parameters:
        - df: OHLCV DataFrame strictly up to candle T.

        Returns:
        - PredictiveResult with probabilities, score in [0, 1], and factor attribution.
        """
        if df.empty:
            raise ValueError("No se puede evaluar un DataFrame vacío")

        required_cols = {"timestamp", "high", "low", "close", "volume"}
        missing = required_cols.difference(set(df.columns))
        if missing:
            missing_str = ", ".join(sorted(missing))
            raise ValueError(f"Faltan columnas requeridas para evaluación predictiva: {missing_str}")

        candles = df.copy()
        candles["timestamp"] = pd.to_datetime(candles["timestamp"], utc=True)
        candles = candles.sort_values("timestamp").reset_index(drop=True)

        last_ts = candles["timestamp"].iloc[-1]
        n_bars = len(candles)

        if n_bars < self.min_history_bars:
            return PredictiveResult(
                timestamp=last_ts,
                probability_continuation=0.5,
                probability_reversal=0.5,
                predictive_score=0.5,
                confidence=0.0,
                regime_context=MarketRegime.RANGING_CONSOLIDATION.value,
                direction_bias="NEUTRAL",
                features_used={
                    "status": "insufficient_data",
                    "bars_count": float(n_bars),
                    "min_required": float(self.min_history_bars),
                },
            )

        # 1. Causal Indicator Enrichment
        if not {"rsi", "atr", "ema_50", "ema_200", "volume_average"}.issubset(set(candles.columns)):
            enriched = self.indicators.calculate_all(candles)
        else:
            enriched = candles

        # 2. Causal Market Regime Classification at T
        regime_res: RegimeResult = self.regime_classifier.classify(enriched)
        current_regime = regime_res.regime

        # 3. Determine Directional Bias from Regime and Technical Indicators
        last_bar = enriched.iloc[-1]
        price = float(last_bar["close"])
        ema_50 = float(last_bar["ema_50"])
        rsi = float(last_bar["rsi"]) if not np.isnan(last_bar["rsi"]) else 50.0

        if current_regime == MarketRegime.TRENDING_BULL:
            direction_bias = "LONG"
        elif current_regime == MarketRegime.TRENDING_BEAR:
            direction_bias = "SHORT"
        elif current_regime == MarketRegime.HIGH_VOLATILITY_EXPANSION:
            direction_bias = "LONG" if price >= ema_50 else "SHORT"
        else:
            direction_bias = "NEUTRAL"

        # 4. Empirical Historical Matching (Past candles i in [warmup .. T - horizon])
        h = self.horizon_bars
        eligible_end = n_bars - h

        matches = 0
        successes = 0

        # Fast vectorized matching over past history where outcome is known
        if eligible_end > 25:
            past_sub = enriched.iloc[:eligible_end]
            past_regimes = self.regime_classifier.classify_series(past_sub, warmup_bars=25)

            start_idx = 24
            for offset, r in enumerate(past_regimes):
                idx = start_idx + offset
                if r.regime == current_regime:
                    matches += 1
                    past_close = float(past_sub["close"].iloc[idx])
                    future_close = float(enriched["close"].iloc[idx + h])

                    if direction_bias == "LONG":
                        if future_close > past_close:
                            successes += 1
                    elif direction_bias == "SHORT":
                        if future_close < past_close:
                            successes += 1
                    else:
                        # Neutral / Range: continuation means staying inside volatility band
                        past_atr = float(past_sub["atr"].iloc[idx])
                        if abs(future_close - past_close) <= max(past_atr, 1e-4):
                            successes += 1

        # 5. Bayesian Laplace Smoothing for Conditional Probability
        # P(continuation) = (successes + 1) / (matches + 2)
        p_continuation = float((successes + 1.0) / (matches + 2.0))
        p_continuation = min(1.0, max(0.0, p_continuation))
        p_reversal = 1.0 - p_continuation

        # 6. Compute Factor Components for Explainable PredictiveScore
        # Factor A: Historical conditional probability of continuation [0, 1]
        f_prob = p_continuation

        # Factor B: Regime Classifier confidence [0, 1]
        f_conf = regime_res.confidence

        # Factor C: Momentum alignment [0, 1]
        if direction_bias == "LONG":
            f_mom = min(1.0, max(0.0, 0.5 + ((rsi - 50.0) / 100.0)))
        elif direction_bias == "SHORT":
            f_mom = min(1.0, max(0.0, 0.5 + ((50.0 - rsi) / 100.0)))
        else:
            f_mom = min(1.0, max(0.0, 1.0 - (abs(rsi - 50.0) / 50.0)))

        # Factor D: Trend slope / structure alignment [0, 1]
        ema_slope = regime_res.features_used.get("ema_slope_50", 0.0)
        if direction_bias == "LONG":
            f_trend = min(1.0, max(0.0, 0.5 + min(0.5, max(-0.5, ema_slope))))
        elif direction_bias == "SHORT":
            f_trend = min(1.0, max(0.0, 0.5 - min(0.5, max(-0.5, ema_slope))))
        else:
            f_trend = min(1.0, max(0.0, 1.0 - min(1.0, abs(ema_slope) * 5.0)))

        # Weights configuration
        w_prob = 0.40
        w_conf = 0.25
        w_mom = 0.20
        w_trend = 0.15

        predictive_score = (w_prob * f_prob) + (w_conf * f_conf) + (w_mom * f_mom) + (w_trend * f_trend)
        predictive_score = min(1.0, max(0.0, float(predictive_score)))

        # Overall estimation confidence combining regime confidence and sample statistical depth
        sample_depth_factor = min(1.0, matches / 15.0)
        est_confidence = min(1.0, max(0.0, (0.5 * f_conf) + (0.5 * sample_depth_factor)))

        features_used = {
            "matched_historical_samples": float(matches),
            "favorable_historical_samples": float(successes),
            "factor_continuation_prob": f_prob,
            "factor_regime_confidence": f_conf,
            "factor_momentum_alignment": f_mom,
            "factor_trend_alignment": f_trend,
            "weight_continuation_prob": w_prob,
            "weight_regime_confidence": w_conf,
            "weight_momentum": w_mom,
            "weight_trend": w_trend,
            "contribution_continuation_prob": w_prob * f_prob,
            "contribution_regime_confidence": w_conf * f_conf,
            "contribution_momentum": w_mom * f_mom,
            "contribution_trend": w_trend * f_trend,
            "horizon_bars": float(h),
            "regime_features": regime_res.features_used,
        }

        return PredictiveResult(
            timestamp=last_ts,
            probability_continuation=p_continuation,
            probability_reversal=p_reversal,
            predictive_score=predictive_score,
            confidence=est_confidence,
            regime_context=current_regime.value if isinstance(current_regime, MarketRegime) else str(current_regime),
            direction_bias=direction_bias,
            features_used=features_used,
        )

    def evaluate_series(self, df: pd.DataFrame, warmup_bars: int = 40) -> list[PredictiveResult]:
        """Evaluates predictive probability results sequentially bar-by-bar across a dataset.

        Parameters:
        - df: OHLCV DataFrame.
        - warmup_bars: Minimum candles required before evaluating probabilities.

        Returns:
        - List of PredictiveResult objects from warmup_bars to end of dataset.
        """
        if df.empty or len(df) < warmup_bars:
            return []

        candles = df.copy()
        candles["timestamp"] = pd.to_datetime(candles["timestamp"], utc=True)
        candles = candles.sort_values("timestamp").reset_index(drop=True)

        results: list[PredictiveResult] = []
        total_bars = len(candles)

        for t_idx in range(warmup_bars - 1, total_bars):
            sub_df = candles.iloc[: t_idx + 1]
            res = self.evaluate(sub_df)
            results.append(res)

        return results
