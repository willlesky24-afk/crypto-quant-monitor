from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.ai_agent.models import MarketContext
from src.anomaly_detection.models import AlertSeverity, AnomalyType, MarketAlert


class MarketAnomalyDetector:
    """Passive market anomaly detection layer.

    Evaluates sequential market snapshots and alerts the human operator on:
    - Regime shifts (e.g. Range Bound -> High Volatility Expansion)
    - Unusual volatility expansion (ATR surge > threshold)
    - Abnormal volume deviations (relative to moving baselines)
    - Predictive score divergence (e.g., strong quant score vs opposite predictive score)

    STRICT CONSTRAINTS:
    - Purely observational.
    - Zero automated trading actions or order generation.
    """

    def __init__(
        self,
        atr_expansion_threshold: float = 0.30,  # 30% increase
        volume_surge_threshold: float = 2.0,    # 2x volume baseline
        score_divergence_threshold: float = 0.40,  # normalized score spread > 40%
    ) -> None:
        self.atr_expansion_threshold = atr_expansion_threshold
        self.volume_surge_threshold = volume_surge_threshold
        self.score_divergence_threshold = score_divergence_threshold

    def evaluate(
        self, current: MarketContext, previous: MarketContext | None = None
    ) -> list[MarketAlert]:
        """Evaluate current market context against previous state and thresholds."""
        alerts: list[MarketAlert] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Regime Change Detection
        if previous is not None and current.market_regime != previous.market_regime:
            severity = (
                AlertSeverity.CRITICAL
                if "VOLATILITY" in current.market_regime or "BEAR" in current.market_regime
                else AlertSeverity.WARNING
            )
            alerts.append(
                MarketAlert(
                    alert_id=f"alt-{uuid.uuid4().hex[:8]}",
                    anomaly_type=AnomalyType.REGIME_CHANGE,
                    severity=severity,
                    symbol=current.symbol,
                    timeframe=current.timeframe,
                    headline=f"{current.symbol} Regime Shift: {previous.market_regime} -> {current.market_regime}",
                    reason=(
                        f"Market regime transitioned from '{previous.market_regime}' to '{current.market_regime}'. "
                        f"Operator should verify risk boundaries."
                    ),
                    current_value=current.quant_score,
                    reference_value=previous.quant_score,
                    timestamp=now_iso,
                    metadata={"from_regime": previous.market_regime, "to_regime": current.market_regime},
                )
            )

        # 2. Volatility (ATR) Expansion Detection
        curr_atr = current.risk.atr
        prev_atr = previous.risk.atr if previous is not None else None
        if curr_atr is not None and prev_atr is not None and prev_atr > 0:
            atr_pct_change = (curr_atr - prev_atr) / prev_atr
            if atr_pct_change >= self.atr_expansion_threshold:
                alerts.append(
                    MarketAlert(
                        alert_id=f"alt-{uuid.uuid4().hex[:8]}",
                        anomaly_type=AnomalyType.VOLATILITY_EXPANSION,
                        severity=AlertSeverity.WARNING,
                        symbol=current.symbol,
                        timeframe=current.timeframe,
                        headline=f"{current.symbol} Volatility Expansion (+{atr_pct_change*100:.1f}%)",
                        reason=f"ATR expanded from {prev_atr:.2f} to {curr_atr:.2f} (+{atr_pct_change*100:.1f}%). Stop boundaries may require adjustment.",
                        current_value=curr_atr,
                        reference_value=prev_atr,
                        timestamp=now_iso,
                        metadata={"atr_change_pct": atr_pct_change},
                    )
                )

        # 3. Volume Surge Detection (via technical_indicators or volume_profile)
        curr_vol = float(current.technical_indicators.get("volume", 0.0) or current.volume_profile.get("total_volume", 0.0))
        prev_vol = float(previous.technical_indicators.get("volume", 0.0) or previous.volume_profile.get("total_volume", 0.0)) if previous is not None else 0.0
        if curr_vol > 0 and prev_vol > 0:
            vol_ratio = curr_vol / prev_vol
            if vol_ratio >= self.volume_surge_threshold:
                alerts.append(
                    MarketAlert(
                        alert_id=f"alt-{uuid.uuid4().hex[:8]}",
                        anomaly_type=AnomalyType.VOLUME_SURGE,
                        severity=AlertSeverity.INFO,
                        symbol=current.symbol,
                        timeframe=current.timeframe,
                        headline=f"{current.symbol} Abnormal Volume Surge ({vol_ratio:.1f}x)",
                        reason=f"Closed candle volume surged to {curr_vol:,.0f} compared to prior candle {prev_vol:,.0f}.",
                        current_value=curr_vol,
                        reference_value=prev_vol,
                        timestamp=now_iso,
                        metadata={"volume_ratio": vol_ratio},
                    )
                )

        # 4. Predictive Score Divergence Detection
        # QuantScore is 0-100 (normalized to 0-1.0), PredictiveScore is 0-1.0
        norm_quant = current.quant_score / 100.0
        norm_pred = current.predictive_score
        spread = abs(norm_quant - norm_pred)
        if spread >= self.score_divergence_threshold:
            alerts.append(
                MarketAlert(
                    alert_id=f"alt-{uuid.uuid4().hex[:8]}",
                    anomaly_type=AnomalyType.SCORE_DIVERGENCE,
                    severity=AlertSeverity.WARNING,
                    symbol=current.symbol,
                    timeframe=current.timeframe,
                    headline=f"{current.symbol} Quantitative vs Predictive Divergence (Spread: {spread:.2f})",
                    reason=(
                        f"Quant Score ({current.quant_score:.1f}/100) diverged significantly from "
                        f"Predictive Score ({current.predictive_score:.2f}). Market dynamics may be decoupling from statistical priors."
                    ),
                    current_value=norm_quant,
                    reference_value=norm_pred,
                    timestamp=now_iso,
                    metadata={"spread": spread},
                )
            )

        return alerts