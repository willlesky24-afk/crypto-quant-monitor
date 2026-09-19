from src.risk_engine import RiskEngine


analysis = {

    "rsi": 78,

    "volume": "Inferior al promedio",

    "price": 81000,

    "atr": 400

}


profile = {

    "poc": 77000

}


engine = RiskEngine()


result = engine.evaluate(
    analysis,
    profile
)


print(result)