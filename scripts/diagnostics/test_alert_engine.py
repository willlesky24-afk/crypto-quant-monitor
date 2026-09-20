import _bootstrap  # noqa: F401

from src.alert_engine import AlertEngine

analysis = {

    "price": 81000,

    "rsi": 78,

    "volume": "Inferior al promedio"

}


profile = {

    "vah": 80000,

    "val": 76000

}


engine = AlertEngine()


alerts = engine.check(
    analysis,
    profile
)


print(alerts)