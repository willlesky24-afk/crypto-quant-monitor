from src.data_loader import BinanceDataLoader
from src.indicators import TechnicalIndicators


loader = BinanceDataLoader()

df = loader.get_klines(
    symbol="BTCUSDT",
    interval="1h",
    limit=100
)


indicators = TechnicalIndicators()

df = indicators.calculate_all(df)


print(df.tail())