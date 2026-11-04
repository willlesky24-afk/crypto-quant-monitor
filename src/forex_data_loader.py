from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

import numpy as np
import pandas as pd

try:
    from .market_data_providers import (
        CachedCandleSource,
        ForexDataError,
        ForexInvalidDataError,
        ForexProviderUnavailableError,
        OandaProvider,
        TwelveDataProvider,
        canonical_pair,
    )
except ImportError:  # Streamlit execution with ``src`` on sys.path.
    from market_data_providers import (
        CachedCandleSource,
        ForexDataError,
        ForexInvalidDataError,
        ForexProviderUnavailableError,
        OandaProvider,
        TwelveDataProvider,
        canonical_pair,
    )

__all__ = [
    "FOREX_PAIRS",
    "METAL_PAIRS",
    "ForexDataError",
    "ForexDataLoader",
    "ForexInvalidDataError",
    "ForexProviderUnavailableError",
]

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

# Spot metals are only offered by providers that quote them as spot (XAU/USD,
# XAG/USD). Yahoo only exposes futures (GC=F, SI=F), a different instrument,
# so metals are not offered through the Yahoo development provider.
METAL_PAIRS: dict[str, str] = {
    "🥇 XAU / USD (Oro)": "XAUUSD=X",
    "🥈 XAG / USD (Plata)": "XAGUSD=X",
}
_METAL_CODES = {canonical_pair(s) for s in METAL_PAIRS.values()}

PROVIDERS = ("yahoo", "twelvedata", "oanda")

INTERVAL_MAP: dict[str, str] = {
    "15m": "15m",
    "1h": "1h",
    "4h": "1h",  # Resampled from 1h if needed
    "1d": "1d",
}


class ForexDataLoader:
    """Historical and live candle data loader for global foreign exchange (Forex) pairs."""

    def __init__(
        self, timeout_seconds: float = 10.0, provider: str | None = None
    ) -> None:
        """Select the provider from ``provider`` or ``FOREX_PROVIDER`` (default yahoo).

        A configured provider without credentials fails here, loudly, instead of
        silently falling back to another source.
        """
        self.timeout_seconds = timeout_seconds
        name = (provider or os.getenv("FOREX_PROVIDER", "yahoo")).strip().lower()
        if name not in PROVIDERS:
            raise ForexProviderUnavailableError(
                f"FOREX_PROVIDER={name!r} no soportado; opciones: {PROVIDERS}."
            )
        self.provider_name = name
        self._provider: TwelveDataProvider | OandaProvider | None = None
        if name == "twelvedata":
            self._provider = TwelveDataProvider(
                api_key=os.getenv("TWELVEDATA_API_KEY", "").strip(),
                timeout_seconds=timeout_seconds,
            )
        elif name == "oanda":
            self._provider = OandaProvider(
                token=os.getenv("OANDA_API_TOKEN", "").strip(),
                environment=os.getenv("OANDA_ENVIRONMENT", "practice"),
                timeout_seconds=timeout_seconds,
            )
        cache_dir = os.getenv("FOREX_CACHE_DIR", "").strip()
        self._source = (
            CachedCandleSource(self._provider, cache_dir)
            if self._provider is not None and cache_dir
            else self._provider
        )

    def available_pairs(self) -> dict[str, str]:
        """Pairs this provider can actually serve (metals only with spot quotes)."""
        if self._provider is not None and self._provider.supports_metals:
            return {**FOREX_PAIRS, **METAL_PAIRS}
        return dict(FOREX_PAIRS)

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
        """Fetch standardized OHLCV candles for a Forex pair or spot metal."""
        if self._provider is not None:
            return self._source.get_klines(symbol, interval, limit)
        if canonical_pair(symbol) in _METAL_CODES:
            raise ForexProviderUnavailableError(
                f"{symbol}: los metales al contado requieren Twelve Data u OANDA "
                "(FOREX_PROVIDER). Yahoo solo ofrece futuros."
            )
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
                payload = resp.read()
        except Exception as exc:
            raise ForexProviderUnavailableError(
                f"Forex provider unavailable for {sym}"
            ) from exc

        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ForexInvalidDataError(f"Invalid Forex response for {sym}") from exc

        chart = data.get("chart") if isinstance(data, dict) else None
        if not isinstance(chart, dict):
            raise ForexInvalidDataError(f"Missing Forex chart for {sym}")
        if chart.get("error"):
            raise ForexProviderUnavailableError(
                f"Forex provider returned an error for {sym}: {chart['error']}"
            )

        results = chart.get("result")
        if (
            not isinstance(results, list)
            or not results
            or not isinstance(results[0], dict)
        ):
            raise ForexInvalidDataError(f"No Forex candles returned for {sym}")
        result = results[0]
        timestamps = result.get("timestamp")
        indicators = result.get("indicators")
        quotes = indicators.get("quote") if isinstance(indicators, dict) else None
        if (
            not isinstance(timestamps, list)
            or not timestamps
            or not isinstance(quotes, list)
            or not quotes
            or not isinstance(quotes[0], dict)
        ):
            raise ForexInvalidDataError(f"Missing Forex candle fields for {sym}")

        quote = quotes[0]
        fields = ("open", "high", "low", "close", "volume")
        if any(
            not isinstance(quote.get(field), list)
            or len(quote[field]) != len(timestamps)
            for field in fields
        ):
            raise ForexInvalidDataError(f"Incomplete Forex candle fields for {sym}")

        records: list[dict[str, Any]] = []
        for index, raw_timestamp in enumerate(timestamps):
            try:
                timestamp = pd.to_datetime(raw_timestamp, unit="s", utc=True)
                values = {field: float(quote[field][index]) for field in fields}
            except (TypeError, ValueError, OverflowError) as exc:
                raise ForexInvalidDataError(
                    f"Invalid Forex candle at index {index} for {sym}"
                ) from exc

            if pd.isna(timestamp) or not all(
                np.isfinite(value) for value in values.values()
            ):
                raise ForexInvalidDataError(
                    f"Non-finite Forex candle at index {index} for {sym}"
                )
            if (
                any(values[field] <= 0 for field in ("open", "high", "low", "close"))
                or values["volume"] < 0
                or values["high"] < max(values["open"], values["close"])
                or values["low"] > min(values["open"], values["close"])
            ):
                raise ForexInvalidDataError(
                    f"Inconsistent Forex candle at index {index} for {sym}"
                )

            records.append({"timestamp": timestamp, **values})

        df = pd.DataFrame(records).sort_values("timestamp").reset_index(drop=True)
        if df["timestamp"].duplicated().any():
            raise ForexInvalidDataError(f"Duplicate Forex timestamps for {sym}")

        # If 4h was requested, resample from 1h.
        if interval.lower() == "4h" and len(df) > 10:
            df = (
                df.set_index("timestamp")
                .resample("4h")
                .agg(
                    {
                        "open": "first",
                        "high": "max",
                        "low": "min",
                        "close": "last",
                        "volume": "sum",
                    }
                )
                .dropna()
                .reset_index()
            )

        if len(df) > limit:
            df = df.iloc[-limit:].reset_index(drop=True)

        df.attrs.update(
            {"provider": "yahoo", "provider_symbol": sym, "volume_kind": "reported"}
        )
        return df
