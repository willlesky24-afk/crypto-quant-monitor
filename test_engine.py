from src.data_loader import BinanceDataLoader
from src.indicators import TechnicalIndicators
from src.volume_profile import VolumeProfile
from src.engine import MarketEngine


loader = BinanceDataLoader()


df = loader.get_klines(
    symbol="BTCUSDT",
    interval="1h",
    limit=200
)


indicators = TechnicalIndicators()

df = indicators.calculate_all(df)


vp = VolumeProfile()

profile = vp.calculate(df)


engine = MarketEngine()

result = engine.analyze(
    df,
    profile
)


print(result)
