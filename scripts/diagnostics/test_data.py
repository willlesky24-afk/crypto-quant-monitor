import _bootstrap  # noqa: F401

from src.data_loader import BinanceDataLoader

loader = BinanceDataLoader()

data = loader.get_klines(
    symbol="BTCUSDT",
    interval="1h",
    limit=10
)

print(data)