import _bootstrap  # noqa: F401

from src.data_loader import BinanceDataLoader
from src.volume_profile import VolumeProfile

loader = BinanceDataLoader()


df = loader.get_klines(
    symbol="BTCUSDT",
    interval="1h",
    limit=200
)


vp = VolumeProfile()


result = vp.calculate(df)


print(result)