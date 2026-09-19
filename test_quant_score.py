from src.quant_score import QuantScore


analysis = {

    "trend": "Alcista",

    "momentum": "Positivo",

    "volume": "Inferior al promedio",

    "profile": "Por encima del área de valor"

}


signal = {

    "confidence": 95

}


risk = {

    "level": "Medio"

}


engine = QuantScore()


result = engine.calculate(
    analysis,
    signal,
    risk
)


print(result)