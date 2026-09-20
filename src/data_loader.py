import pandas as pd
import requests


class BinanceDataLoader:
    def __init__(self):
        self.base_url =  "https://data-api.binance.vision/api/v3"
    def get_klines(
        self,
        symbol="BTCUSDT",
        interval="1h",
        limit=200
    ):
        """
        Descarga velas OHLCV desde Binance Public REST API.
        """

        endpoint = f"{self.base_url}/klines"

        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }

        response = requests.get(
            endpoint,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        candles = response.json()

        df = pd.DataFrame(
            candles,
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_volume",
                "trades",
                "taker_buy_base",
                "taker_buy_quote",
                "ignore"
            ]
        )

        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            unit="ms"
        )

        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume"
        ]

        df[numeric_columns] = df[numeric_columns].astype(float)

        return df[
            [
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume"
            ]
        ]