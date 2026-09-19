from src.report import MarketReport


analysis = {

    "price": 81000,

    "trend": "Alcista",

    "momentum": "Positivo",

    "volatility": "Baja",

    "volume": "Inferior al promedio",

    "score": 3,

    "profile": "Por encima del área de valor"

}


report = MarketReport()


result = report.generate(
    "BTCUSDT",
    analysis
)


print(result)