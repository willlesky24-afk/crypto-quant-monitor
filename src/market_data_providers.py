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
        row = {"timestamp": timestamp, **values}
        if "spread" in rec:
            try:
                spread = float(rec["spread"])
            except (TypeError, ValueError) as exc:
                raise ForexInvalidDataError(
                    f"Invalid spread at index {index} for {symbol}"
                ) from exc
            if not np.isfinite(spread) or spread < 0:
                raise ForexInvalidDataError(
                    f"Invalid spread at index {index} for {symbol}: {spread}"
                )
            row["spread"] = spread
        clean.append(row)

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


# Spot FX and spot metals trade 24/5: the weekly session closes Friday 17:00
# New York time and reopens Sunday 17:00 New York time (the industry "NY close"
# rollover convention; it absorbs US daylight-saving changes, i.e. 21:00 UTC in
# summer and 22:00 UTC in winter). Bars a provider publishes inside that window
# are not interbank trading and would contaminate ATR/RSI/EMA.
_NY_TZ = "America/New_York"
_WEEKLY_CLOSE_HOUR_NY = 17


def drop_weekend_closure(df: pd.DataFrame) -> pd.DataFrame:
    """Remove bars that start inside the weekly closure; count them in attrs."""
    attrs = dict(df.attrs)
    if df.empty:
        out = df.copy()
        out.attrs.update({**attrs, "weekend_bars_removed": 0})
        return out
    ny = df["timestamp"].dt.tz_convert(_NY_TZ)
    dow, hour = ny.dt.dayofweek, ny.dt.hour
    closed = (
        ((dow == 4) & (hour >= _WEEKLY_CLOSE_HOUR_NY))
        | (dow == 5)
        | ((dow == 6) & (hour < _WEEKLY_CLOSE_HOUR_NY))
    )
    out = df[~closed].reset_index(drop=True)
    out.attrs.update({**attrs, "weekend_bars_removed": int(closed.sum())})
    return out


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
                # Extra rows absorb the open candle and removed weekend bars.
                "outputsize": min(int(limit) * 3 // 2 + 50, _MAX_COUNT),
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
        df.attrs.update(attrs)
        df = drop_weekend_closure(df)
        attrs = dict(df.attrs)
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
                # Mid for analysis plus bid/ask for the executable spread (v2.3 D2).
                "price": "MBA",
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
            rec = {
                "timestamp": c.get("time"),
                "open": mid.get("o"),
                "high": mid.get("h"),
                "low": mid.get("l"),
                "close": mid.get("c"),
                "volume": c.get("volume"),
            }
            bid, ask = c.get("bid"), c.get("ask")
            if isinstance(bid, dict) and isinstance(ask, dict):
                # Candle spread: mean of the observed open and close bid/ask
                # spreads (OANDA publishes no intrabar spread path).
                try:
                    rec["spread"] = (
                        (float(ask["o"]) - float(bid["o"]))
                        + (float(ask["c"]) - float(bid["c"]))
                    ) / 2.0
                except (KeyError, TypeError, ValueError) as exc:
                    raise ForexInvalidDataError(
                        f"Invalid bid/ask spread for {sym}"
                    ) from exc
            records.append(rec)
        with_spread = sum("spread" in r for r in records)
        if 0 < with_spread < len(records):
            raise ForexInvalidDataError(
                f"bid/ask spread incompleto para {sym}: {with_spread}/{len(records)} velas"
            )
        df = build_candle_frame(
            records, symbol, provider=self.name, provider_sym=sym, volume_kind="tick"
        )
        df.attrs["spread_kind"] = (
            "bid_ask_open_close_mean" if "spread" in df.columns else "none"
        )
        df = drop_weekend_closure(df)
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


class CachedCandleSource:
    """Incremental Parquet cache in front of one provider.

    Why: free tiers are rate-limited (Twelve Data ~8 requests/minute), and closed
    candles do not change, so they are downloaded once and reused. The cache is
    keyed by provider (``EURUSD_OANDA``) so different sources are never mixed.

    The cache is fresh while the next candle after the last cached one has not
    closed yet. Otherwise the provider is queried and merged; when a provider
    re-publishes a cached candle with different values the newest values win and
    the count is reported in ``attrs["revised_bars"]`` instead of hidden.
    """

    _PRICE_FIELDS = ("open", "high", "low", "close", "volume")

    def __init__(
        self,
        provider: Any,
        cache_dir: str | Any,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        try:
            from .parquet_store import ParquetStore
        except ImportError:  # Streamlit execution with ``src`` on sys.path.
            from parquet_store import ParquetStore
        self.provider = provider
        self.store = ParquetStore(cache_dir)
        self._now = now or (lambda: datetime.now(timezone.utc))

    def _key(self, symbol: str) -> str:
        return f"{canonical_pair(symbol)}_{self.provider.name.upper()}"

    def get_klines(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        key = _check_interval(interval, {k: k for k in INTERVAL_DURATION})
        dur = INTERVAL_DURATION[key]
        cache_key = self._key(symbol)
        cached = self.store.load_dataset(cache_key, key)
        manifest = self.store.read_manifest(cache_key, key) or {}
        meta = manifest.get("extra_metadata", {})
        now = pd.Timestamp(self._now())

        if (
            not cached.empty
            and len(cached) >= int(limit)
            and cached["timestamp"].iloc[-1] + 2 * dur > now
        ):
            out = cached.iloc[-int(limit) :].reset_index(drop=True)
            out.attrs.update(
                {
                    "provider": meta.get("provider", self.provider.name),
                    "provider_symbol": meta.get("provider_symbol"),
                    "volume_kind": meta.get("volume_kind"),
                    "cache": "HIT",
                    "revised_bars": 0,
                }
            )
            return out

        fresh = self.provider.get_klines(symbol, key, limit)
        attrs = dict(fresh.attrs)
        revised = 0
        if not cached.empty and ("spread" in cached.columns) != (
            "spread" in fresh.columns
        ):
            # Column set changed (e.g. bid/ask spread added in v2.3): never mix
            # rows with and without spread; the cache restarts from fresh data.
            cached = cached.iloc[0:0]
        if cached.empty:
            merged = fresh
        else:
            overlap = cached.merge(fresh, on="timestamp", suffixes=("_old", "_new"))
            if not overlap.empty:
                changed = pd.Series(False, index=overlap.index)
                for f in self._PRICE_FIELDS:
                    changed |= ~(
                        (overlap[f"{f}_old"] - overlap[f"{f}_new"]).abs() <= 1e-12
                    )
                revised = int(changed.sum())
            merged = (
                pd.concat([cached, fresh], ignore_index=True)
                .drop_duplicates(subset=["timestamp"], keep="last")
                .sort_values("timestamp")
                .reset_index(drop=True)
            )
        if not merged.empty:
            cols = ["timestamp", *self._PRICE_FIELDS]
            if "spread" in merged.columns:
                cols.append("spread")
            self.store.save_dataset(
                merged[cols],
                cache_key,
                key,
                source=attrs.get("provider", self.provider.name),
                extra_manifest_metadata={
                    "provider": attrs.get("provider"),
                    "provider_symbol": attrs.get("provider_symbol"),
                    "volume_kind": attrs.get("volume_kind"),
                },
            )
        out = merged.iloc[-int(limit) :].reset_index(drop=True)
        out.attrs.update(
            {
                **attrs,
                "cache": "REFRESH" if not cached.empty else "MISS",
                "revised_bars": revised,
            }
        )
        return out
