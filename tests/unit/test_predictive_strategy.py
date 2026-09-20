from __future__ import annotations

import json

import pytest

from src.constants import (
    DECISION_FAVORABLE,
    DECISION_WAIT_CONFIRMATION,
    DECISION_WEAK_CONTEXT,
    RISK_HIGH,
    RISK_LOW,
)
from src.decision_engine import DecisionEngine
from src.predictive_engine import PredictiveResult
from src.regime_classifier import MarketRegime
from src.strategy_optimizer import OptimizedParameters


def make_mock_inputs(
    confidence: float = 75.0,
    adjustment: float = 0.0,
    risk_level: str = RISK_LOW,
    predictive_score: float = 0.85,
    direction_bias: str = "LONG",
    regime: str = MarketRegime.TRENDING_BULL.value,
) -> tuple[dict, dict, dict, PredictiveResult]:
    signal = {
        "state": "BULLISH_IMPULSE",
        "confidence": confidence,
        "positives": ["Soporte validado"],
        "risks": ["Volatilidad media"],
        "quant_score": confidence,
    }
    risk = {
        "level": risk_level,
        "adjustment": adjustment,
        "risks": ["Spread normal"],
    }
    intelligence = {
        "state": "TRENDING",
    }
    predictive = PredictiveResult(
        timestamp=None,
        probability_continuation=predictive_score,
        probability_reversal=1.0 - predictive_score,
        predictive_score=predictive_score,
        confidence=0.90,
        regime_context=regime,
        direction_bias=direction_bias,
        features_used={"regime": regime},
    )
    return signal, risk, intelligence, predictive


def test_predictive_strategy_critical_legacy_vs_predictive_mode_false():
    """Mandatory critical test:

    legacy_mode=True vs. predictive_mode=False MUST produce
    the exact 100% identical decision on identical data.
    """
    engine = DecisionEngine(technical_weight=0.60, predictive_weight=0.40)
    signal, risk, intel, predictive = make_mock_inputs(confidence=85.0)

    res_legacy = engine.evaluate(
        signal,
        risk,
        intel,
        predictive=predictive,
        legacy_mode=True,
    )
    res_pred_false = engine.evaluate(
        signal,
        risk,
        intel,
        predictive=predictive,
        predictive_mode=False,
    )

    assert res_legacy.decision == res_pred_false.decision
    assert res_legacy.confidence == res_pred_false.confidence
    assert res_legacy.final_score == res_pred_false.final_score
    assert res_legacy.tp_multiplier == res_pred_false.tp_multiplier
    assert res_legacy.sl_multiplier == res_pred_false.sl_multiplier
    assert res_legacy.direction == res_pred_false.direction
    assert res_legacy.to_dict() == res_pred_false.to_dict()


def test_predictive_strategy_legacy_backward_compatibility():
    """Validates that calling evaluate without predictive args behaves exactly like v1.8."""
    engine = DecisionEngine()
    signal = {"confidence": 85.0, "positives": ["ok"], "risks": ["none"]}
    risk = {"adjustment": 0.0, "level": RISK_LOW, "risks": []}
    intel = {"state": "market"}

    res = engine.evaluate(signal, risk, intel)
    assert res.decision == DECISION_FAVORABLE
    assert res.confidence == 85.0
    assert res.tp_multiplier == 2.0
    assert res.sl_multiplier == 1.0
    assert res["decision"] == DECISION_FAVORABLE
    assert res["warnings"] == ["none"]
    assert res["market_state"] == "market"


def test_predictive_strategy_controlled_difference_technical_vs_predictive():
    """Evaluates how predictive score elevates or dampens marginal technical signals."""
    engine = DecisionEngine(technical_weight=0.60, predictive_weight=0.40)

    # 1. Marginal signal elevated by strong predictive probability
    # Tech confidence = 70.0 (normally WAIT_CONFIRMATION).
    # Predictive score = 0.95 (95.0 confidence).
    # Weighted: 0.60 * 70 + 0.40 * 95 = 42 + 38 = 80.0 -> Elevated to FAVORABLE!
    signal, risk, intel, predictive_strong = make_mock_inputs(
        confidence=70.0,
        risk_level=RISK_LOW,
        predictive_score=0.95,
    )

    res_enhanced = engine.evaluate(signal, risk, intel, predictive=predictive_strong)
    res_pure_tech = engine.evaluate(signal, risk, intel, legacy_mode=True)

    assert res_pure_tech.decision == DECISION_WAIT_CONFIRMATION
    assert res_enhanced.decision == DECISION_FAVORABLE
    assert res_enhanced.confidence > res_pure_tech.confidence

    # 2. Strong technical signal dampened by adverse predictive probability
    # Tech confidence = 85.0 (normally FAVORABLE).
    # Predictive score = 0.20 (20.0 confidence).
    # Weighted: 0.60 * 85 + 0.40 * 20 = 51 + 8 = 59.0 -> Dampened to WEAK_CONTEXT!
    signal_strong, risk_low, intel, predictive_weak = make_mock_inputs(
        confidence=85.0,
        risk_level=RISK_LOW,
        predictive_score=0.20,
    )

    res_dampened = engine.evaluate(signal_strong, risk_low, intel, predictive=predictive_weak)
    res_tech_favorable = engine.evaluate(signal_strong, risk_low, intel, legacy_mode=True)

    assert res_tech_favorable.decision == DECISION_FAVORABLE
    assert res_dampened.decision == DECISION_WEAK_CONTEXT
    assert res_dampened.confidence < res_tech_favorable.confidence


def test_predictive_strategy_adaptive_weights_formula():
    """Validates the configurable weights formula: FinalScore = W_tech * Tech + W_pred * Pred."""
    engine = DecisionEngine(technical_weight=0.70, predictive_weight=0.30)
    signal, risk, intel, predictive = make_mock_inputs(
        confidence=80.0,
        risk_level=RISK_LOW,
        predictive_score=0.90,  # 90.0
    )

    res = engine.evaluate(signal, risk, intel, predictive=predictive, technical_score=80.0)
    # Expected: 0.70 * 80.0 + 0.30 * 90.0 = 56.0 + 27.0 = 83.0
    assert res.confidence == pytest.approx(83.0)
    assert res.final_score == pytest.approx(83.0)


def test_predictive_strategy_direction_long_and_short():
    """Validates correct directional identification (LONG vs. SHORT)."""
    engine = DecisionEngine()

    # LONG in TRENDING_BULL
    sig_bull, risk_low, intel, pred_bull = make_mock_inputs(
        confidence=85.0,
        direction_bias="LONG",
        regime=MarketRegime.TRENDING_BULL.value,
    )
    res_bull = engine.evaluate(
        sig_bull,
        risk_low,
        intel,
        predictive=pred_bull,
        regime=MarketRegime.TRENDING_BULL,
    )
    assert res_bull.direction == "LONG"
    assert res_bull.decision == DECISION_FAVORABLE

    # SHORT in TRENDING_BEAR
    sig_bear, risk_low, intel, pred_bear = make_mock_inputs(
        confidence=85.0,
        direction_bias="SHORT",
        regime=MarketRegime.TRENDING_BEAR.value,
    )
    res_bear = engine.evaluate(
        sig_bear,
        risk_low,
        intel,
        predictive=pred_bear,
        regime=MarketRegime.TRENDING_BEAR,
    )
    assert res_bear.direction == "SHORT"
    assert res_bear.decision == DECISION_FAVORABLE


def test_predictive_strategy_optimized_parameters_integration():
    """Validates that calibrated ATR TP/SL from StrategyOptimizer are integrated."""
    engine = DecisionEngine()
    signal, risk, intel, predictive = make_mock_inputs(confidence=80.0)

    # With OptimizedParameters
    opt_params = OptimizedParameters(
        regime=MarketRegime.TRENDING_BULL.value,
        volatility_state="NORMAL",
        atr_tp_multiplier=4.25,
        atr_sl_multiplier=1.75,
        expected_rr=2.43,
        sample_size=30,
        confidence=0.85,
        validation_period={},
    )

    res = engine.evaluate(
        signal,
        risk,
        intel,
        predictive=predictive,
        optimized_params=opt_params,
    )
    assert res.tp_multiplier == 4.25
    assert res.sl_multiplier == 1.75

    # Fallback when optimized_params is None
    res_default = engine.evaluate(signal, risk, intel, predictive=predictive, optimized_params=None)
    assert res_default.tp_multiplier == 3.0
    assert res_default.sl_multiplier == 1.5


def test_predictive_strategy_determinism_and_serialization():
    engine = DecisionEngine()
    signal, risk, intel, predictive = make_mock_inputs(confidence=82.0, predictive_score=0.78)

    res1 = engine.evaluate(signal, risk, intel, predictive=predictive)
    res2 = engine.evaluate(signal, risk, intel, predictive=predictive)

    assert res1.to_dict() == res2.to_dict()
    assert res1.confidence == pytest.approx(res2.confidence)

    d = res1.to_dict()
    assert "decision" in d
    assert "technical_score" in d
    assert "predictive_score" in d
    assert "tp_multiplier" in d
    assert "sl_multiplier" in d
    assert "reasoning" in d

    json_str = json.dumps(d)
    assert isinstance(json_str, str)


def test_predictive_strategy_invalid_weights_and_edge_cases():
    with pytest.raises(ValueError, match="technical_weight"):
        DecisionEngine(technical_weight=-0.1)

    with pytest.raises(ValueError, match="predictive_weight"):
        DecisionEngine(predictive_weight=1.5)

    # Weights summing to 0 fallback
    engine_zero = DecisionEngine(technical_weight=0.0, predictive_weight=0.0)
    assert engine_zero.technical_weight == 1.0
    assert engine_zero.predictive_weight == 0.0

    # Risk high degrades decision
    signal, risk_high, intel, predictive = make_mock_inputs(
        confidence=90.0,
        risk_level=RISK_HIGH,
        predictive_score=0.90,
    )
    res_high_risk = engine_zero.evaluate(signal, risk_high, intel, predictive=predictive)
    assert res_high_risk.decision == DECISION_WAIT_CONFIRMATION
    assert res_high_risk.get("decision") == DECISION_WAIT_CONFIRMATION
    assert res_high_risk.get("non_existent", "default") == "default"
    assert "decision" in res_high_risk

    # Legacy branch: tech_confidence between 60 and 80
    signal_mid = {"confidence": 65.0, "positives": [], "risks": []}
    res_legacy_mid = DecisionEngine().evaluate(signal_mid, {"adjustment": 0, "level": RISK_LOW, "risks": []}, {"state": ""})
    assert res_legacy_mid.decision == DECISION_WAIT_CONFIRMATION

    signal_low = {"confidence": 40.0, "positives": [], "risks": []}
    res_legacy_low = DecisionEngine().evaluate(signal_low, {"adjustment": 0, "level": RISK_LOW, "risks": []}, {"state": ""})
    assert res_legacy_low.decision == DECISION_WEAK_CONTEXT


