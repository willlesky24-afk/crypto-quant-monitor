"""v3.2 idea verifier: test a user's rule honestly, with real costs.

The verdict can reject an idea or say it deserves more study. It never says an
idea works: a good sample is not proof. Same discipline as v3.0:
- The last part of the data is reserved and never used while exploring.
- Every attempt tightens the bar (Bonferroni), so trying variants until one
  wins does not pay.
- The idea must beat random entries with the same exit, side and costs.

Project choices, no published source: 80% explore share, 100 trades minimum,
beating the best of the random runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .backtest_engine import BacktestEngine
from .backtest_models import BacktestConfig
from .evidence_evaluation import PERIODS, bootstrap_mean_ci
from .indicators import TechnicalIndicators
from .parquet_store import ParquetStore
from .signal_candidates import CANDIDATES, signal_random, signals_to_events

EXPLORE_SHARE = 0.8
MIN_TRADES = 100
ALPHA = 0.05
ENTRIES = (
    "trend_ema",
    "momentum_rsi",
    "volume_direction",
    "profile_value_area",
    "donchian_20",
    "tsmom_180",
    "bollinger_20_2",
    "reversion_rsi",
)
SIDES = ("LONG", "SHORT", "AMBOS")
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_INDICES = ("SPX500", "NAS100", "US30")


class IdeaVerifierError(ValueError):
    """The idea cannot be tested as stated."""


@dataclass(frozen=True)
class IdeaSpec:
    symbol: str
    interval: str
    entry: str
    side: str
    sl_atr: float
    tp_atr: float
    max_bars: int


def load_history(
    symbol: str, interval: str, data_dir: Path = DATA_DIR
) -> pd.DataFrame | None:
    """Multi-year local candles with indicators, or None if none are stored."""
    base = symbol.removesuffix("=X")
    folder, source = "evidence", "OANDA" if symbol.endswith("=X") else "BINANCE"
    if base in _INDICES:
        folder = "indices"
    raw = ParquetStore(data_dir / folder).load_dataset(f"{base}_{source}", interval)
    if raw.empty:
        return None
    # The v3.0 test period stays unseen until a method is fixed in advance.
    protected = pd.Timestamp(PERIODS["test"][0], tz="UTC")
    raw = raw[pd.to_datetime(raw["timestamp"], utc=True) < protected]
    if raw.empty:
        return None
    return TechnicalIndicators().calculate_all(raw.copy()).reset_index(drop=True)


def ci_level(attempts: int) -> float:
    return 1.0 - ALPHA / attempts


def config_for(symbol: str, side: str, **exits: Any) -> BacktestConfig:
    """Same market model as the evidence runs: spot long, or margin with spread."""
    if side not in SIDES:
        raise IdeaVerifierError(f"Lado no reconocido: {side}")
    if symbol.endswith("=X"):
        direction = "BOTH" if side == "AMBOS" else side
        return BacktestConfig(
            market_type="MARGIN_1X",
            direction=direction,
            taker_fee_pct=0.0,
            slippage_pct=0.0,
            **exits,
        )
    if side == "SHORT":
        raise IdeaVerifierError("En cripto spot solo se puede probar en largo.")
    return BacktestConfig(**exits)


def verdict_from(
    r_values: list[float], random_means: list[float], attempts: int
) -> dict[str, Any]:
    """Classify the net R of the trades against zero and against random entries."""
    if len(r_values) < MIN_TRADES:
        return {
            "code": "POCAS_OPERACIONES",
            "text": f"Solo {len(r_values)} operaciones: no alcanza para concluir.",
            "ci": None,
        }
    low, high = bootstrap_mean_ci(r_values, level=ci_level(attempts))
    mean = float(np.mean(r_values))
    if high < 0:
        code = "PIERDE"
        text = "Pierde después de costos, con margen suficiente para descartar azar."
    elif low > 0 and mean > max(random_means):
        code = "MERECE_ESTUDIO"
        text = (
            "Merece más estudio: supera al azar en estos datos. No es una prueba "
            "de que siga ocurriendo."
        )
    else:
        code = "NO_SE_DISTINGUE"
        text = "No se distingue del azar con estos datos."
    return {"code": code, "text": text, "ci": (low, high)}


def _net_r(trades: list[Any]) -> list[float]:
    return [
        float(t.net_r_multiple)
        for t in trades
        if t.net_r_multiple is not None and np.isfinite(t.net_r_multiple)
    ]


def verify_idea(
    df: pd.DataFrame, spec: IdeaSpec, attempts: int, n_random: int = 8
) -> dict[str, Any]:
    if spec.entry not in ENTRIES:
        raise IdeaVerifierError(f"Entrada no disponible: {spec.entry}")
    config = config_for(
        spec.symbol,
        spec.side,
        sl_atr_multiple=spec.sl_atr,
        tp_atr_multiple=spec.tp_atr,
        max_holding_bars=spec.max_bars,
    )
    cut = int(len(df) * EXPLORE_SHARE)
    explore = df.iloc[:cut].reset_index(drop=True)
    explore.attrs = {}

    def run(signal: pd.Series) -> list[Any]:
        events = signals_to_events(explore, signal, spec.symbol, spec.interval)
        return BacktestEngine(config=config).run(explore, events)[0]

    trades = run(CANDIDATES[spec.entry](explore))
    r_values = _net_r(trades)
    random_means = []
    for seed in range(n_random):
        sample = _net_r(run(signal_random(explore, seed=seed)))
        if sample:
            random_means.append(float(np.mean(sample)))
    verdict = verdict_from(r_values, random_means or [0.0], attempts)
    return {
        **verdict,
        "trades": len(trades),
        "mean_r": float(np.mean(r_values)) if r_values else None,
        "win_pct": (
            100.0 * sum(t.net_pnl > 0 for t in trades) / len(trades) if trades else None
        ),
        "random_best": max(random_means) if random_means else None,
        "attempts": attempts,
        "last_entry": max(t.entry_timestamp for t in trades) if trades else None,
        "reserved_bars": len(df) - cut,
    }
