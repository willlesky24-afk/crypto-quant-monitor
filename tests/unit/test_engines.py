from __future__ import annotations

import pandas as pd
import pytest

from src.decision_engine import DecisionEngine
from src.engine import MarketEngine
from src.risk_engine import RiskEngine
from src.signal_engine import SignalEngine


def _market_row(**overrides):
    row = {
        "close": 105.0,
        "rsi": 60.0,
        "atr": 1.0,
        "volume": 120.0,
        "volume_average": 100.0,
        "ema_50": 102.0,
        "ema_200": 100.0,
    }
    row.update(overrides)
    return pd.DataFrame([row])


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ({}, "Alcista"),
        ({"close": 95, "ema_50": 98, "ema_200": 100}, "Bajista"),
        ({"close": 101, "ema_50": 100, "ema_200": 102}, "Lateral"),
    ],
)
def test_market_engine_trend_classification(values, expected):
    assert MarketEngine().analyze(_market_row(**values))["trend"] == expected


@pytest.mark.parametrize(
    ("rsi", "expected"),
    [
        (70, "Fuerte pero extendido"),
        (50, "Positivo"),
        (30, "Débil"),
        (29.99, "Presión bajista"),
    ],
)
def test_market_engine_momentum_boundaries(rsi, expected):
    assert MarketEngine().analyze(_market_row(rsi=rsi))["momentum"] == expected


@pytest.mark.parametrize(
    ("atr", "expected"), [(2.11, "Alta"), (1.06, "Moderada"), (1.05, "Baja")]
)
def test_market_engine_volatility_boundaries(atr, expected):
    # price=105, therefore boundaries are 1.05 (1%) and 2.10 (2%).
    assert MarketEngine().analyze(_market_row(atr=atr))["volatility"] == expected


def test_market_engine_public_contract(profile):
    result = MarketEngine().analyze(_market_row(), profile)
    assert {
        "trend",
        "momentum",
        "volatility",
        "volume",
        "profile",
        "score",
        "market_context",
        "price",
        "rsi",
        "atr",
        "poc",
        "vah",
        "val",
    } == set(result)
    assert result["profile"] == "Por encima del área de valor"


@pytest.mark.parametrize(
    ("overrides", "state", "score"),
    [
        ({}, "🟢 Señal alcista", 4),
        ({"trend": "Lateral"}, "🟢 Señal alcista", 3),
        (
            {
                "momentum": "Débil",
                "volume": "Inferior al promedio",
                "price": 100,
            },
            "🟡 Señal moderada",
            1,
        ),
        (
            {
                "trend": "Bajista",
                "momentum": "Débil",
                "volume": "Inferior al promedio",
                "price": 90,
            },
            "🔴 Señal débil",
            -2,
        ),
    ],
)
def test_signal_engine_branches(analysis_factory, profile, overrides, state, score):
    result = SignalEngine().evaluate(analysis_factory(**overrides), profile)
    assert result["state"] == state
    assert result["score"] == score
    assert 0 <= result["confidence"] <= 100
    assert set(result) == {"state", "confidence", "positives", "risks", "score"}


@pytest.mark.parametrize(
    ("overrides", "level", "risk_score"),
    [
        ({"price": 101, "rsi": 50}, "Bajo", 0),
        ({"price": 101, "rsi": 75}, "Medio", 1),
        (
            {
                "price": 110,
                "rsi": 75,
                "volume": "Inferior al promedio",
                "atr": 2,
            },
            "Alto",
            3,
        ),
    ],
)
def test_risk_engine_branches(
    analysis_factory, profile, overrides, level, risk_score
):
    result = RiskEngine().evaluate(analysis_factory(**overrides), profile)
    assert result["level"] == level
    assert result["risk_score"] == risk_score
    assert 0 <= result["final_confidence"] <= 100


@pytest.mark.parametrize(
    ("confidence", "risk_level", "adjustment", "expected"),
    [
        (90, "Bajo", 0, "🟢 Condición favorable"),
        (80, "Medio", 10, "🟡 Esperar confirmación"),
        (70, "Alto", 20, "🔴 Contexto débil"),
    ],
)
def test_decision_engine_branches(confidence, risk_level, adjustment, expected):
    signal = {
        "confidence": confidence,
        "positives": ["ok"],
        "risks": ["signal"],
    }
    risk = {
        "adjustment": adjustment,
        "level": risk_level,
        "risks": ["risk"],
    }
    result = DecisionEngine().evaluate(signal, risk, {"state": "market"})
    assert result["decision"] == expected
    assert result["warnings"] == ["signal", "risk"]
    assert result["market_state"] == "market"


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        (None, "Sin datos"),
        ({"poc": 103, "vah": 110, "val": 100}, "Dentro del área de valor"),
        ({"poc": 108, "vah": 112, "val": 106}, "Por debajo del área de valor"),
    ],
)
def test_market_engine_profile_states(profile, expected):
    assert MarketEngine().analyze(_market_row(), profile)["profile"] == expected


def test_risk_engine_covers_oversold_branch(analysis_factory, profile):
    result = RiskEngine().evaluate(
        analysis_factory(price=101, rsi=25),
        profile,
    )
    assert result["risk_score"] == 1
    assert "RSI bajo" in result["risks"][0]
