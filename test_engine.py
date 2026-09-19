from src.data_loader import BinanceDataLoader
from src.indicators import TechnicalIndicators
from src.engine import MarketEngine


loader = BinanceDataLoader()

df = loader.get_klines(
    symbol="BTCUSDT",
    interval="1h",
    limit=100
)


indicators = TechnicalIndicators()

df = indicators.calculate_all(df)


engine = MarketEngine()

result = engine.analyze(df)


print(result)