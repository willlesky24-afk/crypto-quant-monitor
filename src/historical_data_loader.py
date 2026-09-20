from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import pandas as pd
import requests

from .candle_validator import INTERVAL_TIMEDELTAS

DEFAULT_BASE_URL = "https://data-api.binance.vision/api/v3"
MAX_CHUNK_SIZE = 1000


class HistoricalDataLoader:
    """Downloads historical OHLCV klines from Binance Public REST API in paginated chunks

    with adaptive rate limiting, exponential backoff, and strict closed-candle integrity.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        chunk_size: int = MAX_CHUNK_SIZE,
        request_delay: float = 0.05,
        max_retries: int = 3,
    ):
        self.base_url = base_url
        self.chunk_size = min(chunk_size, MAX_CHUNK_SIZE)
        self.request_delay = request_delay
        self.max_retries = max_retries

    @staticmethod
    def _to_timestamp_ms(value: str | int | float | datetime | pd.Timestamp) -> int:
        """Converts any standard date/time representation into UTC epoch milliseconds."""
        if isinstance(value, (int, float)):
            # If already millisecond epoch
            if value > 1e11:
                return int(value)
            # Seconds epoch
            return int(value * 1000)

        ts = pd.to_datetime(value, utc=True)
        return int(ts.value // 1_000_000)

    @staticmethod
    def _interval_to_ms(interval: str) -> int:
        td = INTERVAL_TIMEDELTAS.get(interval.lower())
        if td is None:
            raise ValueError(f"Intervalo '{interval}' no soportado.")
        return int(td.total_seconds() * 1000)

    def _fetch_chunk_with_retry(
        self,
        symbol: str,
        interval: str,
        start_ms: int,
        end_ms: int | None = None,
        limit: int = MAX_CHUNK_SIZE,
    ) -> list[list[Any]]:
        endpoint = f"{self.base_url}/klines"
        params: dict[str, Any] = {
            "symbol": symbol.strip().upper(),
            "interval": interval.strip().lower(),
            "startTime": start_ms,
            "limit": limit,
        }
        if end_ms is not None:
            params["endTime"] = end_ms

        delay = self.request_delay
        for attempt in range(self.max_retries):
            try:
                response = requests.get(endpoint, params=params, timeout=10)

                # Check Binance API weight header if available
                used_weight = response.headers.get("x-mbx-used-weight-1m")
                if used_weight and int(used_weight) > 1000:
                    time.sleep(1.0)  # Throttling when approaching 1200 weight limit

                response.raise_for_status()
                return response.json()
            except (requests.RequestException, requests.HTTPError) as exc:
                if attempt == self.max_retries - 1:
                    raise exc
                time.sleep(delay * (2**attempt))

        return []

    def get_historical_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "1h",
        start_time: str | datetime | pd.Timestamp | int = "2024-01-01",
        end_time: str | datetime | pd.Timestamp | int | None = None,
        include_open_candle: bool = False,
    ) -> pd.DataFrame:
        """Downloads full paginated history for given symbol, timeframe and date range."""
        start_ms = self._to_timestamp_ms(start_time)
        end_ms = self._to_timestamp_ms(end_time) if end_time is not None else int(time.time() * 1000)
        interval_ms = self._interval_to_ms(interval)

        if start_ms > end_ms:
            raise ValueError(f"start_time ({start_ms}) no puede ser posterior a end_time ({end_ms})")

        all_candles: list[list[Any]] = []
        current_start = start_ms

        while current_start <= end_ms:
            chunk = self._fetch_chunk_with_retry(
                symbol=symbol,
                interval=interval,
                start_ms=current_start,
                end_ms=end_ms,
                limit=self.chunk_size,
            )

            if not chunk:
                break

            all_candles.extend(chunk)

            last_open_time = int(chunk[-1][0])
            next_start = last_open_time + interval_ms

            # Termination condition: no progress or reached beyond target
            if next_start <= current_start or next_start > end_ms or len(chunk) < self.chunk_size:
                break

            current_start = next_start
            if self.request_delay > 0:
                time.sleep(self.request_delay)

        if not all_candles:
            return pd.DataFrame(
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
                ]
            )

        # Discard open candle if not requested
        if not include_open_candle and len(all_candles) > 0:
            now_ms = int(time.time() * 1000)
            last_close_time = int(all_candles[-1][6])
            if last_close_time > now_ms:
                all_candles = all_candles[:-1]

        if not all_candles:
            return pd.DataFrame(
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
                ]
            )

        df = pd.DataFrame(
            all_candles,
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

        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)

        numeric_cols = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_volume",
            "taker_buy_base",
            "taker_buy_quote",
        ]
        df[numeric_cols] = df[numeric_cols].astype(float)
        df["trades"] = df["trades"].astype(int)

        # Drop duplicates by timestamp
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

        return df[
            [
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
            ]
        ]
