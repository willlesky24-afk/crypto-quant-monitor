from __future__ import annotations

import pandas as pd

from src.ai_agent.models import MarketContext, RiskMetrics, SignalInfo
from src.anomaly_detection.detector import MarketAnomalyDetector
from src.anomaly_detection.models import AlertSeverity, AnomalyType, MarketAlert


def _create_context(
    regime: str = "TRENDING_BULL",
    atr: float = 1000.0,
    volume: float = 50000.0,
    quant_score: float = 80.0,
    predictive_score: float = 0.80,
) -> MarketContext:
    return MarketContext(
        timestamp=pd.Timestamp("2026-09-20 12:00:00", tz="UTC"),
        symbol="BTCUSDT",
        timeframe="1h",
        current_price=64000.0,
        market_regime=regime,
        predictive_score=predictive_score,
        quant_score=quant_score,
        signal=SignalInfo(
            action="BUY",
            direction="LONG",
            confidence=0.80,
        ),
        risk=RiskMetrics(
            stop_loss=62000.0,
            take_profit=68000.0,
            atr=atr,
        ),
        technical_indicators={"volume": volume},
        volume_profile={},
    )


def test_market_alert_model():
    alert = MarketAlert(
        alert_id="alt-1",
        anomaly_type=AnomalyType.REGIME_CHANGE,
        severity=AlertSeverity.WARNING,
        symbol="BTCUSDT",
        timeframe="1h",
        headline="Regime changed",
        reason="Market shifted",
        current_value=85.0,
        reference_value=50.0,
    )
    d = alert.to_dict()
    assert d["anomaly_type"] == "REGIME_CHANGE"
    assert d["severity"] == "WARNING"
    assert "OBSERVATION ONLY" in alert.disclaimer


def test_anomaly_detector_no_alerts_when_stable():
    detector = MarketAnomalyDetector()
    curr = _create_context()
    prev = _create_context()

    alerts = detector.evaluate(curr, prev)
    assert len(alerts) == 0


def test_anomaly_detector_regime_change():
    detector = MarketAnomalyDetector()
    prev = _create_context(regime="CONSOLIDATION")
    curr = _create_context(regime="HIGH_VOLATILITY_EXPANSION")

    alerts = detector.evaluate(curr, prev)
    regime_alerts = [a for a in alerts if a.anomaly_type == AnomalyType.REGIME_CHANGE]
    assert len(regime_alerts) == 1
    assert regime_alerts[0].severity == AlertSeverity.CRITICAL


def test_anomaly_detector_atr_expansion():
    detector = MarketAnomalyDetector(atr_expansion_threshold=0.30)
    prev = _create_context(atr=1000.0)
    curr = _create_context(atr=1450.0)  # +45%

    alerts = detector.evaluate(curr, prev)
    vol_alerts = [a for a in alerts if a.anomaly_type == AnomalyType.VOLATILITY_EXPANSION]
    assert len(vol_alerts) == 1
    assert vol_alerts[0].current_value == 1450.0


def test_anomaly_detector_volume_surge():
    detector = MarketAnomalyDetector(volume_surge_threshold=2.0)
    prev = _create_context(volume=10000.0)
    curr = _create_context(volume=25000.0)  # 2.5x

    alerts = detector.evaluate(curr, prev)
    surge_alerts = [a for a in alerts if a.anomaly_type == AnomalyType.VOLUME_SURGE]
    assert len(surge_alerts) == 1
    assert surge_alerts[0].current_value == 25000.0


def test_anomaly_detector_score_divergence():
    detector = MarketAnomalyDetector(score_divergence_threshold=0.40)
    # Quant score 90 (norm 0.90), Predictive score 0.20 -> spread 0.70 >= 0.40
    curr = _create_context(quant_score=90.0, predictive_score=0.20)

    alerts = detector.evaluate(curr, None)
    div_alerts = [a for a in alerts if a.anomaly_type == AnomalyType.SCORE_DIVERGENCE]
    assert len(div_alerts) == 1
    assert "Divergence" in div_alerts[0].headline