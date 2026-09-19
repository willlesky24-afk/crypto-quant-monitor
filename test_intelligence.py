from src.market_intelligence import MarketIntelligence


analysis = {

    "score": 3,

    "trend": "Alcista",

    "volume": "Inferior al promedio",

    "momentum": "Positivo",

    "profile": "Por encima del área de valor"

}


intel = MarketIntelligence()


result = intel.evaluate(
    analysis
)


print(result)