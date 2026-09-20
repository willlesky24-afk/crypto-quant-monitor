import _bootstrap  # noqa: F401

from src.decision_engine import DecisionEngine

signal = {

    "confidence": 95,

    "positives": [

        "Tendencia alcista",

        "Momentum positivo"

    ],

    "risks": []

}


risk = {

    "level": "Medio",

    "adjustment": 20,

    "risks": [

        "Precio alejado del POC"

    ]

}


intelligence = {

    "state": "🟢 Alta confluencia"

}


engine = DecisionEngine()


result = engine.evaluate(
    signal,
    risk,
    intelligence
)


print(result)