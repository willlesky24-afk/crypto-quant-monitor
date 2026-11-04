"""v3.0 D1: Quant Score measured in the trade's own direction.

Point values come from src/quant_score.py (base 40; trend +/-25; momentum
+20/-20/+5; volume +15/+5; profile +15/-15/+10; risk 0/-10/-25), mirrored
for SHORT. Expected totals are summed by hand in each test.
"""

from __future__ import annotations

import pytest

from src.constants import (
    MOMENTUM_BEARISH_PRESSURE,
    MOMENTUM_POSITIVE,
    MOMENTUM_WEAK,
    PROFILE_ABOVE_VALUE_AREA,
    PROFILE_BELOW_VALUE_AREA,
    PROFILE_INSIDE_VALUE_AREA,
    RISK_LOW,
    RISK_MEDIUM,
    TREND_BEARISH,
    TREND_BULLISH,
    TREND_SIDEWAYS,
    VOLUME_ABOVE_AVERAGE,
    VOLUME_BELOW_AVERAGE,
)
from src.decision_engine import DecisionEngine
from src.quant_score import QuantScore


def _a(trend, momentum, volume, profile):
    return {"trend": trend, "momentum": momentum, "volume": volume, "profile": profile}


def test_perfect_bearish_setup_scores_high_for_short():
    # LONG: 40 - 25 - 20 + 15 - 15 + 0 = -5 -> 0 ; SHORT: 40 + 25 + 20 + 15 + 15 = 115 -> 100
    a = _a(
        TREND_BEARISH,
        MOMENTUM_BEARISH_PRESSURE,
        VOLUME_ABOVE_AVERAGE,
        PROFILE_BELOW_VALUE_AREA,
    )
    r = QuantScore().calculate(a, {}, {"level": RISK_LOW})
    assert r["score"] == 0
    assert r["score_short"] == 100


def test_perfect_bullish_setup_is_mirror():
    a = _a(
        TREND_BULLISH, MOMENTUM_POSITIVE, VOLUME_ABOVE_AVERAGE, PROFILE_ABOVE_VALUE_AREA
    )
    r = QuantScore().calculate(a, {}, {"level": RISK_LOW})
    assert r["score"] == 100
    assert r["score_short"] == 0


def test_neutral_setup_scores_equal_both_ways():
    # 40 + 0 + 5 + 5 + 10 - 10 = 50 in both directions
    a = _a(
        TREND_SIDEWAYS, MOMENTUM_WEAK, VOLUME_BELOW_AVERAGE, PROFILE_INSIDE_VALUE_AREA
    )
    r = QuantScore().calculate(a, {}, {"level": RISK_MEDIUM})
    assert r["score"] == 50
    assert r["score_short"] == 50


def test_long_score_is_unchanged_for_existing_callers():
    a = _a(
        TREND_BULLISH, MOMENTUM_WEAK, VOLUME_BELOW_AVERAGE, PROFILE_INSIDE_VALUE_AREA
    )
    r = QuantScore().calculate(a, {}, {"level": RISK_LOW})
    # 40 + 25 + 5 + 5 + 10 + 0 = 85
    assert r["score"] == 85
    assert set(r) >= {"score", "label", "breakdown", "score_short"}


class _Pred:
    def __init__(self, score, bias):
        self.predictive_score = score
        self.direction_bias = bias
        self.features_used = {}


def _evaluate(pred, tech_long, tech_short, regime="TRENDING_BEAR"):
    return DecisionEngine().evaluate(
        {"confidence": 60.0, "positives": [], "risks": [], "state": ""},
        {"level": RISK_LOW, "adjustment": 0.0, "risks": []},
        {"state": ""},
        predictive=pred,
        regime=regime,
        technical_score=tech_long,
        technical_score_short=tech_short,
        predictive_mode=True,
    )


def test_short_decision_uses_short_score():
    # SHORT chosen (bias SHORT + bear regime). final = 0.60 x 100 + 0.40 x 70 = 88
    d = _evaluate(_Pred(0.70, "SHORT"), tech_long=0.0, tech_short=100.0)
    assert d.direction == "SHORT"
    assert d.final_score == pytest.approx(88.0)
    assert d.technical_score == pytest.approx(100.0)


def test_long_decision_keeps_long_score():
    # LONG: final = 0.60 x 80 + 0.40 x 70 = 76
    d = _evaluate(
        _Pred(0.70, "LONG"), tech_long=80.0, tech_short=10.0, regime="TRENDING_BULL"
    )
    assert d.direction == "LONG"
    assert d.final_score == pytest.approx(76.0)


def test_short_without_short_score_keeps_previous_behaviour():
    # Legacy callers (no technical_score_short): final = 0.60 x 20 + 0.40 x 70 = 40
    d = DecisionEngine().evaluate(
        {"confidence": 60.0, "positives": [], "risks": [], "state": ""},
        {"level": RISK_LOW, "adjustment": 0.0, "risks": []},
        {"state": ""},
        predictive=_Pred(0.70, "SHORT"),
        regime="TRENDING_BEAR",
        technical_score=20.0,
        predictive_mode=True,
    )
    assert d.direction == "SHORT"
    assert d.final_score == pytest.approx(40.0)
