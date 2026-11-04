"""v3.1 guided risk calculator: position size from the loss the user accepts.

Fixed-fractional sizing: units = money at risk / loss per unit. Costs are part
of the loss per unit, because a stop hit costs the distance plus the spread and
both commissions. The account is USD and has no leverage, matching MARGIN_1X.

Declared assumptions:
- USDT is treated as USD (1:1).
- max_loss assumes the stop fills at its price. A gap can lose more; the
  interface says so.

This module informs size only: it never suggests a side or an entry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

_USD_QUOTES = ("USD", "USDT")


class PositionSizingError(ValueError):
    """Inputs that cannot produce an honest position size."""


@dataclass(frozen=True)
class PositionPlan:
    units: float
    notional: float  # account currency
    max_loss: float  # account currency, stop filled at its price
    costs: float  # account currency, spread plus both commissions
    stop_distance_pct: float
    limited_by_capital: bool  # the wanted size needed more than the capital


def _require_positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0:
        raise PositionSizingError(f"{name} debe ser positivo y finito.")


def _require_side(side: str) -> None:
    if side not in ("LONG", "SHORT"):
        raise PositionSizingError("side debe ser LONG o SHORT.")


def quote_to_usd(symbol: str, price: float) -> float:
    """USD value of one unit of the quote currency, from this pair's own price."""
    _require_positive("price", price)
    pair = symbol.removesuffix("=X").upper()
    if pair.endswith(_USD_QUOTES):
        return 1.0
    if pair.startswith("USD") and len(pair) == 6:
        return 1.0 / price
    raise PositionSizingError(
        f"{symbol}: hace falta el tipo de cambio de su moneda de cotizacion a USD."
    )


def stop_from_atr(entry_price: float, atr: float, multiple: float, side: str) -> float:
    _require_positive("entry_price", entry_price)
    _require_positive("atr", atr)
    _require_positive("multiple", multiple)
    _require_side(side)
    distance = atr * multiple
    stop = entry_price - distance if side == "LONG" else entry_price + distance
    if stop <= 0:
        raise PositionSizingError("El stop por ATR queda en un precio no positivo.")
    return stop


def compute_position_plan(
    *,
    capital: float,
    risk_pct: float,
    entry_price: float,
    stop_price: float,
    side: str,
    spread: float,
    fee_pct: float,
    quote_to_account: float,
) -> PositionPlan:
    """Size in units; spread is in price units, fee_pct is per side, in percent."""
    _require_side(side)
    for name, value in (
        ("capital", capital),
        ("risk_pct", risk_pct),
        ("entry_price", entry_price),
        ("stop_price", stop_price),
        ("quote_to_account", quote_to_account),
    ):
        _require_positive(name, value)
    if risk_pct > 100:
        raise PositionSizingError("risk_pct no puede superar 100.")
    if not math.isfinite(spread) or spread < 0:
        raise PositionSizingError("spread debe ser finito y >= 0.")
    if not math.isfinite(fee_pct) or fee_pct < 0:
        raise PositionSizingError("fee_pct debe ser finito y >= 0.")
    if (side == "LONG" and stop_price >= entry_price) or (
        side == "SHORT" and stop_price <= entry_price
    ):
        raise PositionSizingError("El stop debe estar del lado de la perdida.")

    distance = abs(entry_price - stop_price)
    cost_per_unit = spread + (fee_pct / 100.0) * (entry_price + stop_price)
    loss_per_unit = (distance + cost_per_unit) * quote_to_account
    unit_value = entry_price * quote_to_account

    units = capital * risk_pct / 100.0 / loss_per_unit
    limited = units * unit_value > capital
    if limited:
        units = capital / unit_value
    return PositionPlan(
        units=units,
        notional=units * unit_value,
        max_loss=units * loss_per_unit,
        costs=units * cost_per_unit * quote_to_account,
        stop_distance_pct=100.0 * distance / entry_price,
        limited_by_capital=limited,
    )
