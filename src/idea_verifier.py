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
# Plain-language gallery. Exits are project choices sized to each style, not
# recommendations, and using one counts as an attempt like any other.
METHODS = (
    {
        "entry": "trend_ema",
        "name": "Seguir la tendencia",
        "idea": "Entrar a favor cuando el precio y sus medias apuntan al mismo lado.",
        "suffers": "el mercado va de lado y cambia de dirección seguido.",
        "sl_atr": 2.0,
        "tp_atr": 6.0,
        "max_bars": 120,
    },
    {
        "entry": "donchian_20",
        "name": "Comprar rupturas",
        "idea": "Entrar cuando el precio rompe el máximo de las últimas 20 velas.",
        "suffers": "las rupturas fallan y el precio vuelve al rango.",
        "sl_atr": 2.0,
        "tp_atr": 6.0,
        "max_bars": 120,
    },
    {
        "entry": "reversion_rsi",
        "name": "Comprar caídas",
        "idea": "Entrar cuando el precio cayó mucho, esperando un rebote.",
        "suffers": "la caída continúa: lo barato se pone más barato.",
        "sl_atr": 1.5,
        "tp_atr": 3.0,
        "max_bars": 48,
    },
    {
        "entry": "momentum_rsi",
        "name": "Montarse en el impulso",
        "idea": "Entrar cuando la fuerza reciente del precio es positiva.",
        "suffers": "el impulso se agota justo al entrar.",
        "sl_atr": 2.0,
        "tp_atr": 4.0,
        "max_bars": 60,
    },
)
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


def worst_streak(pnls: list[float]) -> int:
    """Longest run of consecutive losing trades."""
    worst = current = 0
    for pnl in pnls:
        current = current + 1 if pnl < 0 else 0
        worst = max(worst, current)
    return worst


def past_story(result: dict[str, Any]) -> str:
    """Past tense on purpose: a backtest describes what happened, not what will."""
    if not result.get("trades"):
        return "Esta regla no habría operado en estos datos."
    capital = result["capital"]
    return (
        f"Entre {result['first_date']} y {result['last_date']}, con "
        f"${capital:,.0f} habrías terminado con ${result['final_capital']:,.0f}. "
        f"Tu peor racha habría sido de {result['worst_streak']} pérdidas seguidas y "
        f"habrías llegado a estar {result['max_drawdown_pct']:.1f} % por debajo de "
        f"tu máximo. Comprar y mantener habría dejado ${result['hold_final']:,.0f}. "
        "Esto describe el pasado: no indica lo que pasará."
    )


def _net_r(trades: list[Any]) -> list[float]:
    return [
        float(t.net_r_multiple)
        for t in trades
        if t.net_r_multiple is not None and np.isfinite(t.net_r_multiple)
    ]


def verify_idea(
    df: pd.DataFrame,
    spec: IdeaSpec,
    attempts: int,
    n_random: int = 8,
    capital: float = 1000.0,
) -> dict[str, Any]:
    if spec.entry not in ENTRIES:
        raise IdeaVerifierError(f"Entrada no disponible: {spec.entry}")
    config = config_for(
        spec.symbol,
        spec.side,
        sl_atr_multiple=spec.sl_atr,
        tp_atr_multiple=spec.tp_atr,
        max_holding_bars=spec.max_bars,
        initial_capital=capital,
    )
    cut = int(len(df) * EXPLORE_SHARE)
    explore = df.iloc[:cut].reset_index(drop=True)
    explore.attrs = {}

    def run(signal: pd.Series) -> tuple[list[Any], list[Any]]:
        events = signals_to_events(explore, signal, spec.symbol, spec.interval)
        return BacktestEngine(config=config).run(explore, events)

    trades, equity = run(CANDIDATES[spec.entry](explore))
    r_values = _net_r(trades)
    random_means = []
    for seed in range(n_random):
        sample = _net_r(run(signal_random(explore, seed=seed))[0])
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
        "capital": capital,
        "final_capital": capital + sum(t.net_pnl for t in trades),
        "worst_streak": worst_streak([t.net_pnl for t in trades]),
        "max_drawdown_pct": max((p.drawdown_pct for p in equity), default=0.0),
        "hold_final": capital
        * float(explore["close"].iloc[-1])
        / float(explore["close"].iloc[0]),
        "first_date": str(explore["timestamp"].iloc[0])[:10],
        "last_date": str(explore["timestamp"].iloc[-1])[:10],
        "last_entry": max(t.entry_timestamp for t in trades) if trades else None,
        "reserved_bars": len(df) - cut,
    }
