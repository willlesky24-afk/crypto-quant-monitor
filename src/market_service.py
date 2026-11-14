"""v4 market service: the Hoy screen as data, for any interface.

Streamlit computed this inside the page. The new web interface needs the same
numbers through the API, so the calculation lives here once and both can use
it. Nothing is computed differently: every figure still comes from the engine
modules, and a missing value is None (shown as N/D), never zero.
"""

from __future__ import annotations

import math
import os
from collections.abc import Callable
from typing import Any

import pandas as pd

from .constants import LIVE_HISTORY_BARS
from .daily_summary import (
    AGITATED_PERCENTILE,
    CALM_PERCENTILE,
    build_market_summary,
    market_conditions,
)
from .engine import MarketEngine
from .indicators import TechnicalIndicators
from .regime_classifier import RegimeClassifier
from .ui_theme import value_area_position, zone_scale
from .volume_profile import VolumeProfile

CHART_BARS = 300


class MarketDataError(RuntimeError):
    """The market could not be loaded; the reason is shown to the user."""


def level(percentile: float | None, high: str, low: str) -> dict[str, str]:
    """Plain-language level against the market's own history."""
    if percentile is None:
        return {"status": "Sin dato", "tone": ""}
    if percentile >= AGITATED_PERCENTILE:
        return {"status": high, "tone": "warn"}
    if percentile <= CALM_PERCENTILE:
        return {"status": low, "tone": "good"}
    return {"status": "Normal", "tone": ""}


def source_name(symbol: str) -> str:
    if symbol.endswith("=X"):
        return os.getenv("FOREX_PROVIDER", "yahoo").upper()
    return "BINANCE"


def load_candles(
    symbol: str, interval: str, bars: int = LIVE_HISTORY_BARS
) -> pd.DataFrame:
    """Closed candles from the configured provider, with indicators."""
    try:
        if symbol.endswith("=X"):
            from .forex_data_loader import ForexDataLoader

            raw = ForexDataLoader().get_forex_klines(
                symbol=symbol, interval=interval, limit=bars
            )
        else:
            from .data_loader import BinanceDataLoader

            raw = BinanceDataLoader().get_klines(
                symbol=symbol, interval=interval, limit=bars, include_open_candle=False
            )
    except Exception as exc:  # reported to the user, never replaced by sample data
        raise MarketDataError(f"No se pudo cargar {symbol}: {exc}") from exc
    if raw.empty or len(raw) < 35:
        raise MarketDataError(f"{symbol}: datos insuficientes para analizar.")
    df = TechnicalIndicators().calculate_all(raw.copy()).reset_index(drop=True)
    df.attrs = {}
    return df


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def today_payload(
    df: pd.DataFrame,
    symbol: str,
    interval: str,
    funding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Everything the Hoy screen shows, as plain data."""
    profile = VolumeProfile().calculate(df)
    analysis = MarketEngine().analyze(df, profile)
    regime = RegimeClassifier().classify(df).regime
    summary = build_market_summary(symbol, df, analysis, profile, regime)
    figures = summary["figures"]
    conditions = market_conditions(df)

    volatility = conditions.get("volatility_percentile")
    cost = conditions.get("spread_percentile")
    position = value_area_position(figures["price"], figures["val"], figures["vah"])
    span, mark = zone_scale(figures["price"], figures["val"], figures["vah"])
    if position is None:
        zone_status = "Sin dato"
    elif position > 100:
        zone_status = "Encima"
    elif position < 0:
        zone_status = "Debajo"
    else:
        zone_status = "Dentro"

    tail = df.tail(CHART_BARS)
    candles = [
        {
            "time": int(pd.Timestamp(row.timestamp).timestamp()),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
        }
        for row in tail.itertuples()
    ]
    return {
        "symbol": symbol,
        "interval": interval,
        "source": source_name(symbol),
        "last_close_time": pd.Timestamp(df["timestamp"].iloc[-1]).isoformat(),
        "price": figures["price"],
        "change_24h_pct": figures["change_24h_pct"],
        "regime": regime.value,
        "volatility": {
            "percentile": volatility,
            "atr_pct": figures["atr_pct"],
            **level(volatility, "Agitado", "Tranquilo"),
        },
        "cost": {
            "spread_pct": figures["spread_pct"],
            "percentile": cost,
            **(
                level(cost, "Caro", "Barato")
                if figures["spread_pct"] is not None
                else {"status": "Sin dato", "tone": ""}
            ),
        },
        "zone": {
            "val": figures["val"],
            "vah": figures["vah"],
            "poc": figures["poc"],
            "status": zone_status,
            "span": list(span) if span else None,
            "mark": mark,
        },
        "funding": funding,
        "summary": summary["lines"],
        "conditions": {"level": conditions["level"], "text": conditions["text"]},
        "candles": candles,
        "ema_50": _finite(df["ema_50"].iloc[-1]),
        "ema_200": _finite(df["ema_200"].iloc[-1]),
    }


def funding_for(
    symbol: str, fetch: Callable[[str], Any] | None = None
) -> dict[str, Any] | None:
    """Funding snapshot for crypto; None for other markets, an error dict if it fails."""
    if symbol.endswith("=X"):
        return None
    from .funding_rates import (
        FundingSource,
        FundingUnavailableError,
        funding_snapshot,
        provider_from_env,
    )

    try:
        series = (fetch or FundingSource(provider_from_env()).fetch)(symbol)
    except (FundingUnavailableError, OSError, ValueError) as exc:
        return {"error": str(exc)}
    return {"provider": provider_from_env().upper(), **funding_snapshot(series)}
