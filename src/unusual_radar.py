"""v3.1 radar: what is unusual right now, measured against each market's history.

A radar alert says "this is rare and here is what followed before", never what
to do. v3.0 showed no tradable edge, so nothing here claims one.

Rules, fixed before seeing results (project choices, no published source):
- Rare means the current value sits in a tail of share <= 0.05 / number of
  tests (Bonferroni), because scanning many markets makes something look odd.
  Bars overlap, so the true false-alarm rate is higher than this bar implies.
- "Similar cases" are the most extreme 5% of the same measure, grouped into
  episodes. That quantile uses the whole loaded history: it describes the past
  and is not a backtest.
- A "big move" is |close[t+24] - close[t]| > 2 x the median ATR of the last 300
  bars, with no direction. The ATR of the bar itself is not used: it is small
  in a compression, which would make any move look big by construction. The
  baseline is how often that happens on any bar.
- Windows: 30-bar relative return, 60-bar correlation of returns.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

try:
    from .stress_measures import (
        LOOKBACK_BARS,
        bsadf_series,
        explosive_status,
        min_window,
    )
except ImportError:  # Streamlit execution with ``src`` on sys.path.
    from stress_measures import (
        LOOKBACK_BARS,
        bsadf_series,
        explosive_status,
        min_window,
    )

ALPHA = 0.05
MIN_HISTORY_BARS = 500
SIMILAR_SHARE = 0.05
HORIZON_BARS = 24
BIG_MOVE_ATR = 2.0
TYPICAL_ATR_BARS = 300
RELATIVE_BARS = 30
CORRELATION_BARS = 60
EXPLOSIVE_MIN_BARS = LOOKBACK_BARS + int(np.log(LOOKBACK_BARS))
MAX_DOWNLOADS = 6  # polite to the providers; a project choice

_LABELS = {
    "compresion": "Volatilidad inusualmente comprimida",
    "fuerza_relativa": "Se mueve muy distinto a su grupo",
    "correlacion": "Se rompió su relación habitual",
    "explosividad": "Precio en crecimiento explosivo",
}


@dataclass(frozen=True)
class RadarAlert:
    market: str
    measure: str
    tail_pct: float
    cases: int
    big_moves: int
    baseline_pct: float
    text: str


@dataclass(frozen=True)
class RadarResult:
    alerts: list[RadarAlert]
    tests: int
    alpha: float | None
    failed: dict[str, str] = field(default_factory=dict)


def tail_share(
    series: pd.Series, side: str, min_history: int = MIN_HISTORY_BARS
) -> float | None:
    """Share of prior values at least as extreme as the current one."""
    clean = series.dropna()
    if len(clean) <= min_history - 1:
        return None
    prior, current = clean.iloc[:-1], clean.iloc[-1]
    extreme = prior <= current if side == "low" else prior >= current
    return float(extreme.mean())


def first_episodes(mask: pd.Series, gap: int) -> list[int]:
    """Positions of True bars at least ``gap`` bars from the last one kept."""
    kept: list[int] = []
    for pos, flag in enumerate(mask.tolist()):
        if flag and (not kept or pos - kept[-1] >= gap):
            kept.append(pos)
    return kept


def history_from_mask(
    mask: pd.Series,
    close: pd.Series,
    atr: pd.Series,
    horizon: int = HORIZON_BARS,
    k: float = BIG_MOVE_ATR,
) -> dict[str, float]:
    """Episodes with a known outcome, how many moved big, and the usual rate."""
    closes = close.to_numpy(dtype=float)
    atrs = atr.rolling(TYPICAL_ATR_BARS, min_periods=1).median().to_numpy(dtype=float)
    last_known = len(closes) - horizon
    moves = abs(closes[horizon:] - closes[:last_known])
    big = moves > k * atrs[:last_known]
    cases = [p for p in first_episodes(mask, horizon) if p < last_known]
    return {
        "cases": len(cases),
        "big_moves": int(sum(bool(big[p]) for p in cases)),
        "baseline_pct": float(big.mean() * 100.0),
    }


def _frames(markets: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    return {k: v.set_index("timestamp") for k, v in markets.items()}


def iter_measures(
    markets: dict[str, pd.DataFrame],
    groups: list[list[str]],
    pairs: list[tuple[str, str]],
) -> Iterator[tuple[str, str, pd.Series, str]]:
    """Yield (market, measure, series, side). Only markets with data are used."""
    frames = _frames(markets)
    for name, frame in frames.items():
        yield name, "compresion", frame["atr"] / frame["close"], "low"
    for group in groups:
        members = [m for m in group if m in frames]
        if len(members) < 3:  # a median of two is just the other market
            continue
        closes = pd.DataFrame({m: frames[m]["close"] for m in members}).dropna()
        returns = closes / closes.shift(RELATIVE_BARS) - 1.0
        relative = returns.sub(returns.median(axis=1), axis=0).abs()
        for member in members:
            yield member, "fuerza_relativa", relative[member], "high"
    for left, right in pairs:
        if left not in frames or right not in frames:
            continue
        closes = pd.DataFrame(
            {"a": frames[left]["close"], "b": frames[right]["close"]}
        ).dropna()
        changes = closes.pct_change()
        correlation = changes["a"].rolling(CORRELATION_BARS).corr(changes["b"])
        yield f"{left}/{right}", "correlacion", correlation, "low"


def _outcome_market(name: str) -> str:
    return name.split("/")[0]


def similar_mask(series: pd.Series, side: str) -> pd.Series:
    if side == "low":
        return series <= series.quantile(SIMILAR_SHARE)
    return series >= series.quantile(1.0 - SIMILAR_SHARE)


def case_history(series: pd.Series, side: str, frame: pd.DataFrame) -> dict[str, float]:
    clean = series.dropna()
    aligned = frame.loc[clean.index.intersection(frame.index)]
    mask = similar_mask(clean, side).loc[aligned.index]
    return history_from_mask(mask, aligned["close"], aligned["atr"])


def _text(label: str, history: dict[str, float]) -> str:
    cases = history["cases"]
    times = "1 vez" if cases == 1 else f"{cases} veces"
    return (
        f"{label}. Casos parecidos: {times}; en {history['big_moves']} hubo un "
        f"movimiento grande en cualquier dirección (lo normal es "
        f"{history['baseline_pct']:.0f} % de las velas). "
        "Un aviso no indica qué hacer."
    )


def run_radar(
    markets: dict[str, pd.DataFrame],
    groups: list[list[str]],
    pairs: list[tuple[str, str]],
    failed: dict[str, str] | None = None,
) -> RadarResult:
    frames = _frames(markets)
    tested = []
    for market, measure, series, side in iter_measures(markets, groups, pairs):
        tail = tail_share(series, side)
        if tail is not None:
            tested.append((market, measure, series, side, tail))
    explosive_ready = [k for k, v in frames.items() if len(v) >= EXPLOSIVE_MIN_BARS]
    total = len(tested) + len(explosive_ready)
    alpha = ALPHA / total if total else None
    alerts = []
    for market in explosive_ready:
        status = explosive_status(frames[market]["close"], tests=total)
        if status["explosive"]:
            log_close = np.log(frames[market]["close"])
            series = bsadf_series(log_close, LOOKBACK_BARS, min_window(LOOKBACK_BARS))
            history = case_history(series, "high", frames[market])
            alerts.append(
                RadarAlert(
                    market=market,
                    measure="explosividad",
                    tail_pct=(tail_share(series, "high", 2) or 0.0) * 100.0,
                    cases=history["cases"],
                    big_moves=history["big_moves"],
                    baseline_pct=history["baseline_pct"],
                    text=_text(_LABELS["explosividad"], history),
                )
            )
    for market, measure, series, side, tail in tested:
        if tail > alpha:
            continue
        history = case_history(series, side, frames[_outcome_market(market)])
        alerts.append(
            RadarAlert(
                market=market,
                measure=measure,
                tail_pct=tail * 100.0,
                cases=history["cases"],
                big_moves=history["big_moves"],
                baseline_pct=history["baseline_pct"],
                text=_text(_LABELS[measure], history),
            )
        )
    return RadarResult(alerts, total, alpha, failed or {})


def build_markets(
    fetch: Callable[[str], pd.DataFrame], symbols: list[str]
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Fetch each market; a failure is reported, and the scan continues."""
    markets, failed = {}, {}

    def attempt(symbol: str) -> tuple[str, pd.DataFrame | None, str | None]:
        try:
            return symbol, fetch(symbol), None
        except Exception as exc:  # shown to the user, never dropped silently
            return symbol, None, str(exc)

    with ThreadPoolExecutor(max_workers=MAX_DOWNLOADS) as pool:
        for symbol, frame, error in pool.map(attempt, symbols):
            if error is None:
                markets[symbol] = frame
            else:
                failed[symbol] = error
    return markets, failed
