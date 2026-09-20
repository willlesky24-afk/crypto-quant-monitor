import _bootstrap  # noqa: F401

from src.analyzer import MarketAnalyzer

analysis = {
    "trend": "Alcista",
    "momentum": "Fuerte pero extendido",
    "volume": "Inferior al promedio",
    "profile": "Dentro del área de valor",
    "score": 4
}


analyzer = MarketAnalyzer()


result = analyzer.generate_summary(
    analysis
)


print(result)