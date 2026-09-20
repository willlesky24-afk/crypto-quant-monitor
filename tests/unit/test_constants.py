from __future__ import annotations

from enum import Enum

import src.constants as constants


def _public_values():
    values = set()
    for name, item in vars(constants).items():
        if name.startswith("_"):
            continue
        if isinstance(item, str):
            values.add(item)
        elif isinstance(item, dict):
            values.update(value for value in item.values() if isinstance(value, str))
        elif isinstance(item, type) and issubclass(item, Enum):
            values.update(member.value for member in item)
    return values


def test_canonical_domain_values_are_centralized():
    expected = {
        "Alcista",
        "Bajista",
        "Lateral",
        "Positivo",
        "Fuerte pero extendido",
        "Débil",
        "Presión bajista",
        "Superior al promedio",
        "Inferior al promedio",
        "Por encima del área de valor",
        "Dentro del área de valor",
        "Por debajo del área de valor",
        "Bajo",
        "Medio",
        "Alto",
        "🟢 Señal alcista",
        "🟡 Señal moderada",
        "🔴 Señal débil",
    }
    assert expected <= _public_values()

