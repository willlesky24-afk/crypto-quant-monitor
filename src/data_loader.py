import time

import pandas as pd
import requests


class BinanceDataLoader:
    def __init__(self):
        self.base_url = "https://data-api.binance.vision/api/v3"

    def get_klines(
        self,
        symbol="BTCUSDT",
        interval="1h",
        limit=200,
        include_open_candle=False,
    ):
        """Descarga velas OHLCV desde Binance Public REST API.

        Por defecto, `include_open_candle=False` descarta la última vela si está
        en curso (no cerrada), garantizando que las señales e indicadores se calculen
        exclusivamente sobre datos confirmados.
        """
        mirrors = [
            self.base_url,
            "https://api.binance.com/api/v3",
            "https://api1.binance.com/api/v3",
            "https://api3.binance.com/api/v3",
        ]

        if limit > self.MAX_LIMIT:
            # Binance serves at most 1000 klines per request: page backwards with
            # endTime until ``limit`` candles (+1 to absorb a dropped open one).
            candles = []
            end_time = None
            while len(candles) < limit + 1:
                chunk = self._fetch_raw(
                    mirrors,
                    {
                        "symbol": symbol,
                        "interval": interval,
                        "limit": min(self.MAX_LIMIT, limit + 1 - len(candles)),
                        **({"endTime": end_time} if end_time is not None else {}),
                    },
                )
                if not chunk:
                    break
                candles = chunk + candles
                end_time = int(chunk[0][0]) - 1
            return self._to_frame(candles, include_open_candle, keep_last=limit)

        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }
        return self._to_frame(
            self._fetch_raw(mirrors, params), include_open_candle, keep_last=None
        )

    MAX_LIMIT = 1000

    @staticmethod
    def _fetch_raw(mirrors, params):
        candles = None
        last_error = None

        for base in mirrors:
            try:
                endpoint = f"{base}/klines"
                response = requests.get(
                    endpoint,
                    params=params,
                    timeout=10,
                )
                response.raise_for_status()
                data = response.json()
                if isinstance(data, list):
                    candles = data
                    break
            except Exception as exc:
                last_error = exc
                continue

        if candles is None:
            if last_error:
                raise last_error
            candles = []
        return candles

    @staticmethod
    def _to_frame(candles, include_open_candle, keep_last):
        if not candles:
            return pd.DataFrame(
                columns=["timestamp", "open", "high", "low", "close", "volume"]
            )

        if not include_open_candle and len(candles) > 0:
            now_ms = int(time.time() * 1000)
            last_close_time = int(candles[-1][6])
            if last_close_time > now_ms:
                candles = candles[:-1]
        if keep_last is not None:
            candles = candles[-keep_last:]

        if not candles:
            return pd.DataFrame(
                columns=["timestamp", "open", "high", "low", "close", "volume"]
            )

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
                "ignore",
            ],
        )

        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            unit="ms",
        )

        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        df[numeric_columns] = df[numeric_columns].astype(float)

        return df[
            [
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        ]
