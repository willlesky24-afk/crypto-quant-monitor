from __future__ import annotations

import pytest

from src.quant_score import QuantScore


def calculate(analysis_factory, **overrides):
    analysis = analysis_factory(**overrides)
    return QuantScore().calculate(
        analysis,
        signal={"state": "🟡 Señal moderada"},
        risk={"level": "Bajo"},
    )


@pytest.mark.parametrize(
    ("trend", "points"),
    [("Alcista", 25), ("Lateral", 0), ("Bajista", -25)],
)
def test_trend_breakdown(analysis_factory, trend, points):
    assert calculate(analysis_factory, trend=trend)["breakdown"]["trend"] == points


@pytest.mark.parametrize(
    ("momentum", "points"),
    [
        ("Positivo", 20),
        ("Fuerte pero extendido", 5),
        ("Débil", 5),
        ("Presión bajista", -20),
    ],
)
def test_momentum_breakdown(analysis_factory, momentum, points):
    assert calculate(analysis_factory, momentum=momentum)["breakdown"]["momentum"] == points


def test_below_value_area_is_penalized_regression(analysis_factory):
    result = calculate(analysis_factory, profile="Por debajo del área de valor")
    assert result["breakdown"]["profile"] == -15


@pytest.mark.parametrize(
    ("level", "points"), [("Bajo", 0), ("Medio", -10), ("Alto", -25)]
)
def test_risk_breakdown(analysis_factory, level, points):
    result = QuantScore().calculate(
        analysis_factory(), {"state": "irrelevant"}, {"level": level}
    )
    assert result["breakdown"]["risk"] == points


def test_score_contract_and_limits(analysis_factory):
    strong = QuantScore().calculate(
        analysis_factory(profile="Por encima del área de valor"), {}, {"level": "Bajo"}
    )
    weak = QuantScore().calculate(
        analysis_factory(
            trend="Bajista",
            momentum="Presión bajista",
            volume="Inferior al promedio",
            profile="Por debajo del área de valor",
        ),
        {},
        {"level": "Alto"},
    )
    assert set(strong) == {"score", "label", "breakdown"}
    assert strong["score"] == 100
    assert weak["score"] == 0

