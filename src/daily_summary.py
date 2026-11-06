"""v3.1 market summary in plain language, built only from engine figures.

Describes the market state and never suggests an action. Every number shown is
also returned in ``figures`` so it can be traced. ATR is read from the candles,
not from the rounded ``analysis`` dict, which loses forex precision.

Volatility is compared with the market's own recent history instead of fixed
ATR% bands, which label almost every forex bar "low". The 300-bar window is the
system's ANALYSIS_WINDOW_BARS; the 20/80 percentile bands are project choices.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

try:
    from .constants import (
        ANALYSIS_WINDOW_BARS,
        PROFILE_ABOVE_VALUE_AREA,
        PROFILE_BELOW_VALUE_AREA,
        PROFILE_INSIDE_VALUE_AREA,
        VOLUME_ABOVE_AVERAGE,
    )
    from .regime_classifier import MarketRegime
except ImportError:  # Streamlit execution with ``src`` on sys.path.
    from constants import (
        ANALYSIS_WINDOW_BARS,
        PROFILE_ABOVE_VALUE_AREA,
        PROFILE_BELOW_VALUE_AREA,
        PROFILE_INSIDE_VALUE_AREA,
        VOLUME_ABOVE_AVERAGE,
    )
    from regime_classifier import MarketRegime

MIN_PERCENTILE_BARS = 30
CALM_PERCENTILE = 20.0
AGITATED_PERCENTILE = 80.0

_REGIME_TEXT = {
    MarketRegime.TRENDING_BULL: "viene en tendencia alcista",
    MarketRegime.TRENDING_BEAR: "viene en tendencia bajista",
    MarketRegime.RANGING_CONSOLIDATION: "se mueve de lado, sin tendencia clara",
    MarketRegime.HIGH_VOLATILITY_EXPANSION: "está en una expansión de volatilidad",
}
_PROFILE_TEXT = {
    PROFILE_ABOVE_VALUE_AREA: "por encima de su zona de valor",
    PROFILE_BELOW_VALUE_AREA: "por debajo de su zona de valor",
    PROFILE_INSIDE_VALUE_AREA: "dentro de su zona de valor",
}


def format_price(value: float) -> str:
    return f"{value:,.2f}" if value >= 100 else f"{value:.5f}"


def _own_percentile(series: pd.Series) -> float | None:
    """Share of the prior window's values below the current value."""
    window = series.dropna().tail(ANALYSIS_WINDOW_BARS)
    if len(window) < MIN_PERCENTILE_BARS:
        return None
    return float((window.iloc[:-1] < window.iloc[-1]).mean() * 100.0)


def atr_percentile(df: pd.DataFrame) -> float | None:
    return _own_percentile(df["atr"] / df["close"])


def market_conditions(df: pd.DataFrame) -> dict[str, Any]:
    """Traffic light for how demanding the market is, never for what to do.

    Each market is compared with itself, so no absolute threshold is invented:
    volatility is ATR%, and cost is spread/ATR, the share of a typical move
    that the spread consumes. Elevated uses the summary's 80th-percentile band.
    Green means nothing is elevated, not that a trade is good.
    """
    volatility = atr_percentile(df)
    if volatility is None:
        return {
            "level": "NO_DISPONIBLE",
            "text": "No hay historia suficiente para medir las condiciones.",
            "spread_checked": False,
            "volatility_percentile": None,
            "spread_percentile": None,
        }
    spread = None
    if "spread" in df.columns:
        spread = _own_percentile(df["spread"] / df["atr"])
    reasons = []
    if volatility >= AGITATED_PERCENTILE:
        reasons.append("volatilidad alta")
    if spread is not None and spread >= AGITATED_PERCENTILE:
        reasons.append("spread caro frente al movimiento típico")
    level = ("VERDE", "AMARILLO", "ROJO")[len(reasons)]
    if reasons:
        text = "Condiciones exigentes: " + " y ".join(reasons) + "."
    else:
        text = "Sin condiciones elevadas frente a la historia de este mercado."
    if spread is None:
        text += " Este proveedor no da spread: no se midió ese costo."
    return {
        "level": level,
        "text": text,
        "spread_checked": spread is not None,
        "volatility_percentile": volatility,
        "spread_percentile": spread,
    }


def _change_24h_pct(df: pd.DataFrame) -> float | None:
    last = df.iloc[-1]
    past = df[df["timestamp"] <= last["timestamp"] - pd.Timedelta(hours=24)]
    if past.empty:
        return None
    return float((last["close"] / past["close"].iloc[-1] - 1.0) * 100.0)


def build_market_summary(
    symbol: str,
    df: pd.DataFrame,
    analysis: dict[str, Any],
    profile: dict[str, Any],
    regime: MarketRegime,
) -> dict[str, Any]:
    last = df.iloc[-1]
    price = float(last["close"])
    atr_pct = 100.0 * float(last["atr"]) / price
    change = _change_24h_pct(df)
    percentile = atr_percentile(df)
    spread_pct = None
    if "spread" in df.columns and math.isfinite(float(last["spread"])):
        spread_pct = 100.0 * float(last["spread"]) / price

    lines = [f"{symbol} está en {format_price(price)} y {_REGIME_TEXT[regime]}."]
    if change is not None:
        lines.append(f"En las últimas 24 h cambió {change:+.2f} %.")

    move = f"Su movimiento típico por vela (ATR) es {atr_pct:.2f} % del precio"
    if percentile is None:
        lines.append(f"{move}.")
    elif percentile >= AGITATED_PERCENTILE:
        lines.append(f"{move}: más agitado de lo normal para este mercado.")
    elif percentile <= CALM_PERCENTILE:
        lines.append(f"{move}: más tranquilo de lo normal para este mercado.")
    else:
        lines.append(f"{move}: dentro de lo normal para este mercado.")

    zone = _PROFILE_TEXT.get(analysis["profile"])
    if zone is not None:
        lines.append(
            f"El precio está {zone} "
            f"({format_price(float(profile['val']))} a "
            f"{format_price(float(profile['vah']))})."
        )
    volume = (
        "por encima" if analysis["volume"] == VOLUME_ABOVE_AVERAGE else "por debajo"
    )
    lines.append(f"El volumen de la última vela está {volume} de su promedio.")
    if spread_pct is not None:
        lines.append(f"El spread cuesta {spread_pct:.3f} % del precio.")

    return {
        "lines": lines,
        "figures": {
            "price": price,
            "change_24h_pct": change,
            "atr_pct": atr_pct,
            "atr_percentile": percentile,
            "spread_pct": spread_pct,
            "poc": float(profile["poc"]),
            "vah": float(profile["vah"]),
            "val": float(profile["val"]),
        },
    }
