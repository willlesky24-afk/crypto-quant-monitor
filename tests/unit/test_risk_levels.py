from __future__ import annotations

import math

import pytest

from src.constants import (
    DECISION_FAVORABLE,
    DECISION_WAIT_CONFIRMATION,
    DECISION_WEAK_CONTEXT,
)
from src.risk_engine import RiskEngine


@pytest.mark.parametrize(
    ("direction", "entry", "stop", "target"),
    [
        ("LONG", 100.0, 95.0, 110.0),
        ("SHORT", 100.0, 105.0, 90.0),
    ],
)
def test_valid_levels_calculate_gross_r_from_effective_prices(
    direction, entry, stop, target
):
    levels = RiskEngine().calculate_levels(entry, stop, target, direction)

    assert levels["reason"] is None
    assert levels["entry_price"] == entry
    assert levels["stop_loss"] == stop
    assert levels["take_profit"] == target
    assert levels["risk_distance"] == 5.0
    assert levels["reward_distance"] == 10.0
    assert levels["gross_risk_reward"] == 2.0


@pytest.mark.parametrize(
    ("direction", "stop"),
    [("LONG", 101.0), ("SHORT", 99.0)],
)
def test_stop_on_wrong_side_rejects_all_levels(direction, stop):
    levels = RiskEngine().calculate_levels(
        100.0, stop, 110.0 if direction == "LONG" else 90.0, direction
    )

    assert "Stop Loss" in levels["reason"]
    assert levels["stop_loss"] is None
    assert levels["gross_risk_reward"] is None


@pytest.mark.parametrize(
    ("direction", "target"),
    [("LONG", 99.0), ("SHORT", 101.0)],
)
def test_target_on_wrong_side_rejects_all_levels(direction, target):
    levels = RiskEngine().calculate_levels(
        100.0, 95.0 if direction == "LONG" else 105.0, target, direction
    )

    assert "Take Profit" in levels["reason"]
    assert levels["take_profit"] is None
    assert levels["gross_risk_reward"] is None


def test_entry_equal_to_stop_has_no_r():
    levels = RiskEngine().calculate_levels(100.0, 100.0, 110.0, "LONG")

    assert "Stop Loss" in levels["reason"]
    assert levels["risk_distance"] is None
    assert levels["gross_risk_reward"] is None


@pytest.mark.parametrize(
    ("entry", "stop", "target"),
    [(None, 95.0, 110.0), (100.0, None, 110.0), (100.0, 95.0, None)],
)
def test_missing_prices_have_explicit_reason_and_no_r(entry, stop, target):
    levels = RiskEngine().calculate_levels(entry, stop, target, "LONG")

    assert "Faltan" in levels["reason"]
    assert levels["gross_risk_reward"] is None


@pytest.mark.parametrize(
    ("entry", "stop", "target"),
    [
        (math.nan, 95.0, 110.0),
        (100.0, math.inf, 110.0),
        (100.0, 95.0, -math.inf),
    ],
)
def test_non_finite_prices_have_no_levels(entry, stop, target):
    levels = RiskEngine().calculate_levels(entry, stop, target, "LONG")

    assert "finitos" in levels["reason"]
    assert levels["gross_risk_reward"] is None


def test_neutral_direction_has_no_trade_levels():
    levels = RiskEngine().calculate_levels(100.0, 95.0, 110.0, "NEUTRAL")

    assert "Dirección" in levels["reason"]
    assert levels["gross_risk_reward"] is None


def test_favorable_decision_with_no_operable_direction_has_no_levels():
    plan = RiskEngine().plan_from_decision(
        decision=DECISION_FAVORABLE,
        direction="NEUTRAL",
        reference_price=100.0,
        atr=2.0,
        sl_multiplier=1.5,
        tp_multiplier=3.0,
    )

    assert plan["status"] == "NO DISPONIBLE"
    assert plan["direction"] == "SIN OPERACIÓN"
    assert plan["stop_loss"] is None
    assert plan["gross_risk_reward"] is None


@pytest.mark.parametrize(
    ("direction", "expected_stop", "expected_target"),
    [("LONG", 97.0, 106.0), ("SHORT", 103.0, 94.0)],
)
def test_atr_plan_is_candidate_without_confirmed_entry(
    direction, expected_stop, expected_target
):
    plan = RiskEngine().plan_from_decision(
        decision=DECISION_FAVORABLE,
        direction=direction,
        reference_price=100.0,
        atr=2.0,
        sl_multiplier=1.5,
        tp_multiplier=3.0,
    )

    assert plan["status"] == "CANDIDATA"
    assert plan["direction"] == direction
    assert plan["reference_price"] == 100.0
    assert plan["entry_price"] == 100.0
    assert plan["entry_confirmed"] is False
    assert plan["stop_loss"] == expected_stop
    assert plan["take_profit"] == expected_target
    assert plan["risk_distance"] == 3.0
    assert plan["reward_distance"] == 6.0
    assert plan["gross_risk_reward"] == 2.0
    assert "ATR" in plan["methodology"]


@pytest.mark.parametrize("atr", [None, 0.0, -1.0, math.nan, math.inf])
def test_missing_or_invalid_atr_has_no_invented_levels(atr):
    plan = RiskEngine().plan_from_decision(
        decision=DECISION_FAVORABLE,
        direction="LONG",
        reference_price=100.0,
        atr=atr,
        sl_multiplier=1.5,
        tp_multiplier=3.0,
    )

    assert plan["status"] == "NO DISPONIBLE"
    assert plan["stop_loss"] is None
    assert plan["take_profit"] is None
    assert plan["gross_risk_reward"] is None
    assert plan["reason"]


@pytest.mark.parametrize("multiplier", [0.0, -1.0, math.nan, math.inf])
def test_invalid_stop_multiplier_cannot_create_r(multiplier):
    plan = RiskEngine().plan_from_decision(
        decision=DECISION_FAVORABLE,
        direction="LONG",
        reference_price=100.0,
        atr=2.0,
        sl_multiplier=multiplier,
        tp_multiplier=3.0,
    )

    assert plan["status"] == "NO DISPONIBLE"
    assert plan["stop_loss"] is None
    assert plan["gross_risk_reward"] is None


@pytest.mark.parametrize(
    ("decision", "status"),
    [
        (DECISION_WAIT_CONFIRMATION, "ESPERANDO CONFIRMACIÓN"),
        (DECISION_WEAK_CONTEXT, "DESCARTADA"),
    ],
)
def test_wait_or_reject_has_no_operable_levels(decision, status):
    plan = RiskEngine().plan_from_decision(
        decision=decision,
        direction="LONG",
        reference_price=100.0,
        atr=2.0,
        sl_multiplier=1.5,
        tp_multiplier=3.0,
    )

    assert plan["status"] == status
    assert plan["direction"] == "SIN OPERACIÓN"
    assert plan["entry_price"] is None
    assert plan["gross_risk_reward"] is None


def test_r_uses_effective_levels_not_multiplier_ratio():
    levels = RiskEngine().calculate_levels(100.0, 97.5, 106.25, "LONG")

    assert levels["risk_distance"] == 2.5
    assert levels["reward_distance"] == 6.25
    assert levels["gross_risk_reward"] == 2.5


def test_invalid_short_target_from_atr_is_not_exposed():
    plan = RiskEngine().plan_from_decision(
        decision=DECISION_FAVORABLE,
        direction="SHORT",
        reference_price=1.0,
        atr=1.0,
        sl_multiplier=1.5,
        tp_multiplier=3.0,
    )

    assert plan["status"] == "NO DISPONIBLE"
    assert plan["entry_price"] is None
    assert plan["gross_risk_reward"] is None
