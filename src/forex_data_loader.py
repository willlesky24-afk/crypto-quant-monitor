from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

FOREX_PAIRS: dict[str, str] = {
    "💶 EUR / USD (Euro / Dólar)": "EURUSD=X",
    "💷 GBP / USD (Libra / Dólar)": "GBPUSD=X",
    "💴 USD / JPY (Dólar / Yen)": "USDJPY=X",
    "🇦🇺 AUD / USD (Dólar Australiano)": "AUDUSD=X",
    "🇨🇦 USD / CAD (Dólar Canadiense)": "USDCAD=X",
    "🇨🇭 USD / CHF (Dólar / Franco Suizo)": "USDCHF=X",
    "🇳🇿 NZD / USD (Dólar Neozelandés)": "NZDUSD=X",
    "🇬🇧 EUR / GBP (Euro / Libra)": "EURGBP=X",
}

INTERVAL_MAP: dict[str, str] = {
    "15m": "15m",
    "1h": "1h",
    "4h": "1h",  # Resampled from 1h if needed
    "1d": "1d",
}


class ForexDataLoader:
    """Historical and live candle data loader for global foreign exchange (Forex) pairs."""

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds

    def get_klines(
        self,
        symbol: str = "EURUSD=X",
        interval: str = "1h",
        limit: int = 300,
        include_open_candle: bool = False,
    ) -> pd.DataFrame:
        """Alias compatible with BinanceDataLoader interface for cross-market scanners."""
        return self.get_forex_klines(symbol=symbol, interval=interval, limit=limit)

    def get_forex_klines(
        self,
        symbol: str = "EURUSD=X",
        interval: str = "1h",
        limit: int = 300,
    ) -> pd.DataFrame:
        """Fetch standardized OHLCV candles for a Forex pair via global market API."""
        sym = symbol.strip().upper()
        if not sym.endswith("=X") and "/" not in sym and len(sym) == 6:
            sym = f"{sym}=X"
        elif "/" in sym:
            clean = sym.replace("/", "")
            sym = f"{clean}=X"

        yf_interval = INTERVAL_MAP.get(interval.lower(), "1h")

        # Range calculation based on limit and interval
        if yf_interval == "15m":
            range_str = "1mo"
        elif yf_interval == "1d":
            range_str = "1y"
        else:
            range_str = "3mo" if limit > 200 else "1mo"

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={yf_interval}&range={range_str}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            chart = data.get("chart", {})
            results = chart.get("result")
            if not results:
                err = chart.get("error", {}).get("description", "No result found")
                logger.warning(f"Forex fetch failed for {sym}: {err}")
                return self._generate_fallback_candles(sym, limit)

            res = results[0]
            timestamps = res.get("timestamp", [])
            indicators = res.get("indicators", {}).get("quote", [{}])[0]

            opens = indicators.get("open", [])
            highs = indicators.get("high", [])
            lows = indicators.get("low", [])
            closes = indicators.get("close", [])
            volumes = indicators.get("volume", [])

            if not timestamps or not closes:
                return self._generate_fallback_candles(sym, limit)

            records: list[dict[str, Any]] = []
            for i in range(len(timestamps)):
                val_c = closes[i]
                if val_c is None or np.isnan(val_c):
                    continue
                val_o = opens[i] if opens[i] is not None and not np.isnan(opens[i]) else val_c
                val_h = highs[i] if highs[i] is not None and not np.isnan(highs[i]) else max(val_o, val_c)
                val_l = lows[i] if lows[i] is not None and not np.isnan(lows[i]) else min(val_o, val_c)
                val_v = volumes[i] if (volumes and i < len(volumes) and volumes[i] is not None and not np.isnan(volumes[i])) else 1000.0

                records.append({
                    "timestamp": pd.to_datetime(timestamps[i], unit="s", utc=True),
                    "open": float(val_o),
                    "high": float(val_h),
                    "low": float(val_l),
                    "close": float(val_c),
                    "volume": float(val_v) if float(val_v) > 0 else 1000.0,
                })

            df = pd.DataFrame(records)
            if df.empty:
                return self._generate_fallback_candles(sym, limit)

            df = df.sort_values("timestamp").reset_index(drop=True)

            # If 4h was requested, resample from 1h
            if interval.lower() == "4h" and len(df) > 10:
                df = (
                    df.set_index("timestamp")
                    .resample("4h")
                    .agg({
                        "open": "first",
                        "high": "max",
                        "low": "min",
                        "close": "last",
                        "volume": "sum",
                    })
                    .dropna()
                    .reset_index()
                )

            # Return requested limit
            if len(df) > limit:
                df = df.iloc[-limit:].reset_index(drop=True)

            return df

        except Exception as exc:
            logger.warning(f"Error fetching live Forex data for {sym}: {exc}. Using fallback.")
            return self._generate_fallback_candles(sym, limit)

    def _generate_fallback_candles(self, symbol: str, limit: int = 150) -> pd.DataFrame:
        """Deterministic baseline candle generator if network is restricted."""
        base_prices = {
            "EURUSD=X": 1.0850,
            "GBPUSD=X": 1.2950,
            "USDJPY=X": 152.40,
            "AUDUSD=X": 0.6550,
            "USDCAD=X": 1.3850,
            "USDCHF=X": 0.8850,
            "EURGBP=X": 0.8350,
        }
        center = base_prices.get(symbol, 1.0000)
        rng = np.random.default_rng(42)
        returns = rng.normal(0.00005, 0.0015, limit)
        prices = center * np.cumprod(1 + returns)

        now = pd.Timestamp.now(tz="UTC")
        timestamps = [now - pd.Timedelta(hours=limit - i) for i in range(limit)]

        records = []
        for i in range(limit):
            close = float(prices[i])
            spread = close * 0.0008
            val_o = close - (spread * 0.2)
            val_h = max(val_o, close) + (spread * 0.5)
            val_l = min(val_o, close) - (spread * 0.5)
            val_v = float(rng.integers(500, 5000))
            records.append({
                "timestamp": timestamps[i],
                "open": round(val_o, 5 if center < 10 else 3),
                "high": round(val_h, 5 if center < 10 else 3),
                "low": round(val_l, 5 if center < 10 else 3),
                "close": round(close, 5 if center < 10 else 3),
                "volume": val_v,
            })

        return pd.DataFrame(records)
