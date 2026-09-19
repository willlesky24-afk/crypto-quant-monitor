from src.signal_engine import SignalEngine


analysis = {

    "trend": "Alcista",

    "momentum": "Positivo",

    "volume": "Inferior al promedio",

    "price": 81000

}


profile = {

    "vah": 80000,

    "val": 76000

}


engine = SignalEngine()


result = engine.evaluate(
    analysis,
    profile
)


print(result)