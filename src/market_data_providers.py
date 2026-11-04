"""Pluggable Forex / metals candle providers (v2.2).

Every provider returns the same frame contract as the historical Yahoo loader:
columns ``timestamp`` (UTC), ``open``, ``high``, ``low``, ``close``, ``volume``,
sorted ascending, closed candles only, plus ``DataFrame.attrs`` provenance:

- ``provider``: provider id (``twelvedata``, ``oanda``, ``yahoo``).
- ``provider_symbol``: symbol actually requested from the provider.
- ``volume_kind``: ``none`` (no volume published), ``tick`` (tick count) or
  ``reported`` (provider-reported volume). Forex has no centralized volume, so
  ``none`` volume is stored as 0.0 and must not be read as traded volume.

Endpoint shapes follow each provider's public REST documentation
(Twelve Data ``/time_series``; OANDA v20 ``/v3/instruments/{instrument}/candles``).
They are mocked offline in tests; verify against live docs before production.
"""

from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd


class ForexDataError(RuntimeError):
    """Forex candles could not be used for operational analysis."""


class ForexProviderUnavailableError(ForexDataError):
    """The Forex price provider could not supply a response."""


class ForexInvalidDataError(ForexDataError):
    """The Forex price provider returned missing or invalid candles."""


INTERVAL_DURATION: dict[str, timedelta] = {
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
}

_MAX_COUNT = 5000


def canonical_pair(symbol: str) -> str:
    """Return the 6-letter pair (``EURUSD``) from ``EURUSD=X``, ``EUR/USD`` or ``EUR_USD``."""
    clean = symbol.strip().upper().replace("=X", "").replace("/", "").replace("_", "")
    if len(clean) != 6 or not clean.isalpha():
        raise ForexInvalidDataError(f"Simbolo forex/metal no reconocido: {symbol!r}")
    return clean


def provider_symbol(symbol: str, provider: str) -> str:
    pair = canonical_pair(symbol)
    base, quote = pair[:3], pair[3:]
    if provider == "twelvedata":
        return f"{base}/{quote}"
    if provider == "oanda":
        return f"{base}_{quote}"
    if provider == "yahoo":
        return f"{pair}=X"
    raise ForexProviderUnavailableError(f"Proveedor desconocido: {provider!r}")


def build_candle_frame(
    records: list[dict[str, Any]],
    symbol: str,
    *,
    provider: str,
    provider_sym: str,
    volume_kind: str,
) -> pd.DataFrame:
    """Validate parsed candles with the same OHLC rules for every provider."""
    if not records:
        raise ForexInvalidDataError(f"No Forex candles returned for {symbol}")
    fields = ("open", "high", "low", "close", "volume")
    clean: list[dict[str, Any]] = []
    for index, rec in enumerate(records):
        try:
            timestamp = pd.to_datetime(rec["timestamp"], utc=True)
            values = {field: float(rec[field]) for field in fields}
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ForexInvalidDataError(
                f"Invalid Forex candle at index {index} for {symbol}"
            ) from exc
        if pd.isna(timestamp) or not all(np.isfinite(v) for v in values.values()):
            raise ForexInvalidDataError(
                f"Non-finite Forex candle at index {index} for {symbol}"
            )
        if (
            any(values[f] <= 0 for f in ("open", "high", "low", "close"))
            or values["volume"] < 0
            or values["high"] < max(values["open"], values["close"])
            or values["low"] > min(values["open"], values["close"])
        ):
            raise ForexInvalidDataError(
                f"Inconsistent Forex candle at index {index} for {symbol}"
            )
        clean.append({"timestamp": timestamp, **values})

    df = pd.DataFrame(clean).sort_values("timestamp").reset_index(drop=True)
    if df["timestamp"].duplicated().any():
        raise ForexInvalidDataError(f"Duplicate Forex timestamps for {symbol}")
    df.attrs.update(
        {
            "provider": provider,
            "provider_symbol": provider_sym,
            "volume_kind": volume_kind,
        }
    )
    return df


def _fetch_json(req: urllib.request.Request, timeout: float, symbol: str) -> Any:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
    except Exception as exc:
        raise ForexProviderUnavailableError(
            f"Forex provider unavailable for {symbol}"
        ) from exc
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ForexInvalidDataError(f"Invalid Forex response for {symbol}") from exc


def _check_interval(interval: str, mapping: dict[str, str]) -> str:
    key = interval.strip().lower()
    if key not in mapping:
        raise ForexInvalidDataError(
            f"intervalo {interval!r} no soportado; disponibles: {sorted(mapping)}"
        )
    return key


class TwelveDataProvider:
    """Twelve Data REST ``/time_series`` (free tier requires an API key)."""

    name = "twelvedata"
    supports_metals = True
    BASE_URL = "https://api.twelvedata.com/time_series"
    INTERVALS = {"15m": "15min", "1h": "1h", "4h": "4h", "1d": "1day"}

    def __init__(
        self,
        api_key: str,
        timeout_seconds: float = 10.0,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if not api_key:
            raise ForexProviderUnavailableError(
                "Twelve Data requiere TWELVEDATA_API_KEY en el entorno (.env)."
            )
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self._now = now or (lambda: datetime.now(timezone.utc))

    def get_klines(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        key = _check_interval(interval, self.INTERVALS)
        sym = provider_symbol(symbol, self.name)
        query = urllib.parse.urlencode(
            {
                "symbol": sym,
                "interval": self.INTERVALS[key],
                "outputsize": min(int(limit) + 1, _MAX_COUNT),
                "timezone": "UTC",
                "order": "asc",
                "apikey": self.api_key,
            }
        )
        req = urllib.request.Request(f"{self.BASE_URL}?{query}", method="GET")
        data = _fetch_json(req, self.timeout_seconds, sym)
        if not isinstance(data, dict):
            raise ForexInvalidDataError(f"Invalid Forex response for {sym}")
        if data.get("status") == "error":
            raise ForexProviderUnavailableError(
                f"Twelve Data error for {sym}: {data.get('message', 'sin detalle')}"
            )
        values = data.get("values")
        if not isinstance(values, list):
            raise ForexInvalidDataError(f"No Forex candles returned for {sym}")
        records = [
            {
                "timestamp": v.get("datetime") if isinstance(v, dict) else None,
                "open": v.get("open") if isinstance(v, dict) else None,
                "high": v.get("high") if isinstance(v, dict) else None,
                "low": v.get("low") if isinstance(v, dict) else None,
                "close": v.get("close") if isinstance(v, dict) else None,
                "volume": 0.0,
            }
            for v in values
        ]
        df = build_candle_frame(
            records, symbol, provider=self.name, provider_sym=sym, volume_kind="none"
        )
        # Keep only candles whose period has ended (anti-repainting).
        cutoff = pd.Timestamp(self._now()) - INTERVAL_DURATION[key]
        attrs = dict(df.attrs)
        df = df[df["timestamp"] <= cutoff].reset_index(drop=True)
        df = df.iloc[-int(limit) :].reset_index(drop=True)
        df.attrs.update(attrs)
        return df


class OandaProvider:
    """OANDA v20 REST candles (practice account is free)."""

    name = "oanda"
    supports_metals = True
    HOSTS = {
        "practice": "https://api-fxpractice.oanda.com",
        "live": "https://api-fxtrade.oanda.com",
    }
    INTERVALS = {"15m": "M15", "1h": "H1", "4h": "H4", "1d": "D"}

    def __init__(
        self, token: str, environment: str = "practice", timeout_seconds: float = 10.0
    ) -> None:
        if not token:
            raise ForexProviderUnavailableError(
                "OANDA requiere OANDA_API_TOKEN en el entorno (.env)."
            )
        env = (environment or "").strip().lower()
        if env not in self.HOSTS:
            raise ForexProviderUnavailableError(
                f"OANDA_ENVIRONMENT debe ser 'practice' o 'live', no {environment!r}."
            )
        self.token = token
        self.host = self.HOSTS[env]
        self.timeout_seconds = timeout_seconds

    def get_klines(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        key = _check_interval(interval, self.INTERVALS)
        sym = provider_symbol(symbol, self.name)
        query = urllib.parse.urlencode(
            {
                "granularity": self.INTERVALS[key],
                "count": min(int(limit) + 1, _MAX_COUNT),
                "price": "M",
            }
        )
        req = urllib.request.Request(
            f"{self.host}/v3/instruments/{sym}/candles?{query}",
            headers={"Authorization": f"Bearer {self.token}"},
            method="GET",
        )
        data = _fetch_json(req, self.timeout_seconds, sym)
        candles = data.get("candles") if isinstance(data, dict) else None
        if not isinstance(candles, list):
            msg = data.get("errorMessage") if isinstance(data, dict) else None
            if msg:
                raise ForexProviderUnavailableError(f"OANDA error for {sym}: {msg}")
            raise ForexInvalidDataError(f"No Forex candles returned for {sym}")
        records = []
        for c in candles:
            if not isinstance(c, dict):
                raise ForexInvalidDataError(f"Invalid Forex candle for {sym}")
            if c.get("complete") is not True:
                continue  # only closed candles (anti-repainting)
            mid = c.get("mid")
            if not isinstance(mid, dict):
                raise ForexInvalidDataError(f"Missing mid prices for {sym}")
            records.append(
                {
                    "timestamp": c.get("time"),
                    "open": mid.get("o"),
                    "high": mid.get("h"),
                    "low": mid.get("l"),
                    "close": mid.get("c"),
                    "volume": c.get("volume"),
                }
            )
        df = build_candle_frame(
            records, symbol, provider=self.name, provider_sym=sym, volume_kind="tick"
        )
        attrs = dict(df.attrs)
        df = df.iloc[-int(limit) :].reset_index(drop=True)
        df.attrs.update(attrs)
        return df


def compare_sources(
    a: pd.DataFrame,
    b: pd.DataFrame,
    *,
    tolerance_pct: float,
    min_overlap: int,
) -> dict[str, Any]:
    """Compare closes of two providers on shared timestamps.

    ``tolerance_pct`` and ``min_overlap`` are deliberately required: the
    acceptable disagreement depends on instrument, spread and interval and is a
    user decision, not a library default. Relative difference is measured
    against source ``a``.
    """
    if (
        not isinstance(tolerance_pct, (int, float))
        or not math.isfinite(tolerance_pct)
        or tolerance_pct <= 0
    ):
        raise ValueError("tolerance_pct debe ser un numero finito positivo.")
    if int(min_overlap) < 1:
        raise ValueError("min_overlap debe ser >= 1.")
    merged = pd.merge(
        a[["timestamp", "close"]],
        b[["timestamp", "close"]],
        on="timestamp",
        suffixes=("_a", "_b"),
    )
    overlap = len(merged)
    result: dict[str, Any] = {
        "overlap": overlap,
        "tolerance_pct": float(tolerance_pct),
        "max_close_diff_pct": None,
        "worst_timestamp": None,
        "provider_a": a.attrs.get("provider"),
        "provider_b": b.attrs.get("provider"),
    }
    if overlap < int(min_overlap):
        result["status"] = "INSUFFICIENT_OVERLAP"
        return result
    diff = (merged["close_b"] - merged["close_a"]).abs() / merged["close_a"] * 100.0
    worst = int(diff.idxmax())
    result["max_close_diff_pct"] = float(diff.iloc[worst])
    result["worst_timestamp"] = merged["timestamp"].iloc[worst]
    result["status"] = (
        "AGREE" if result["max_close_diff_pct"] <= tolerance_pct else "DISAGREE"
    )
    return result
