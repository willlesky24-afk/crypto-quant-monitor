"""v3.2 idea verifier: test a user's rule honestly, with real costs.

The verdict can reject an idea or say it deserves more study. It never says an
idea works: a good sample is not proof. Same discipline as v3.0:
- The last part of the data is reserved and never used while exploring.
- Every attempt tightens the bar (Bonferroni), so trying variants until one
  wins does not pay.
- The idea must beat random entries with the same exit, side and costs.

Project choices, no published source: 80% explore share, 100 trades minimum.

Random control (approved 2026-11-14, plan v5 C10): many random runs that enter
as many times as the rule, with the same side, exits and costs. The rule must
beat them with an empirical p <= ALPHA / attempts, where
p = (1 + runs at or above the rule) / (runs + 1)
(North, Curtis & Sham 2002, Am. J. Hum. Genet. 71:439-441). Runs: at least 200
and enough for the bar to be reachable (2 / level), capped at 1000 for time.
"""

from __future__ import annotations

import math
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .backtest_engine import BacktestEngine
from .backtest_models import BacktestConfig
from .evidence_evaluation import PERIODS
from .indicators import TechnicalIndicators
from .parquet_store import ParquetStore
from .signal_candidates import CANDIDATES, WARMUP_BARS, signals_to_events

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


BLOCK_REPS = 5000
BLOCK_SEED = 20261101


def block_mean_ci(values: list[float], level: float) -> tuple[float, float]:
    """Percentile interval of the mean that respects runs of related trades.

    Approved 2026-11-14 (plan v5, C13). Trades in the same market regime are
    not independent, so resampling them one by one gives an interval that is
    too narrow. The stationary bootstrap (Politis and Romano 1994) resamples
    blocks; the block length follows Politis and White (2004, Econometric
    Reviews 23(1):53-70) with the correction of Patton, Politis and White
    (2009, Econometric Reviews 28(4):372-375), as implemented in the `arch`
    package (arch.bootstrap.optimal_block_length).
    """
    from arch.bootstrap import StationaryBootstrap, optimal_block_length

    data = np.asarray(values, dtype=float)
    block = max(1.0, float(optimal_block_length(data)["stationary"].iloc[0]))
    rng = np.random.default_rng(BLOCK_SEED)
    boot = StationaryBootstrap(block, data, seed=rng)
    low, high = boot.conf_int(np.mean, reps=BLOCK_REPS, method="percentile", size=level)
    return float(low[0]), float(high[0])


MIN_RANDOM_RUNS = 200
MAX_RANDOM_RUNS = 1000


def empirical_p(observed: float, random_means: list[float]) -> float:
    """Share of random runs at least as good, counting the rule itself."""
    at_least = sum(m >= observed for m in random_means)
    return (1 + at_least) / (len(random_means) + 1)


def random_runs_for(attempts: int) -> int:
    """Smallest p is 1/(runs+1): need at least 2/level runs to reach the bar."""
    needed = math.ceil(2 * attempts / ALPHA)
    return min(MAX_RANDOM_RUNS, max(MIN_RANDOM_RUNS, needed))


def matched_positions(
    n_bars: int, k: int, spacing: int, start: int, seed: int
) -> list[int]:
    """k random entry bars in [start, n_bars), at least ``spacing`` apart.

    Spacing keeps trades from overlapping so the run really makes about k
    trades; if the rule trades too often to fit, spacing shrinks to fit.
    """
    available = n_bars - start
    k = min(k, available)
    if k <= 0:
        return []
    step = max(1, min(spacing, available // k))
    rng = np.random.default_rng(seed)
    picks = np.sort(rng.choice(available - (k - 1) * (step - 1), size=k, replace=False))
    return [int(start + v + i * (step - 1)) for i, v in enumerate(picks)]


_POOL_STATE: dict[str, Any] = {}


def _pool_init(
    explore: pd.DataFrame, config: BacktestConfig, symbol: str, interval: str
) -> None:
    _POOL_STATE.update(explore=explore, config=config, symbol=symbol, interval=interval)


def _random_mean(args: tuple[int, int, int, str]) -> float | None:
    seed, k, spacing, side = args
    explore = _POOL_STATE["explore"]
    positions = matched_positions(len(explore), k, spacing, WARMUP_BARS, seed)
    rng = np.random.default_rng(seed + 1_000_003)
    signal = pd.Series(0, index=explore.index, dtype=int)
    for pos in positions:
        if side == "AMBOS":
            signal.iloc[pos] = int(rng.choice([-1, 1]))
        else:
            signal.iloc[pos] = 1 if side == "LONG" else -1
    events = signals_to_events(
        explore, signal, _POOL_STATE["symbol"], _POOL_STATE["interval"]
    )
    trades, _ = BacktestEngine(config=_POOL_STATE["config"]).run(explore, events)
    sample = _net_r(trades)
    return float(np.mean(sample)) if sample else None


def random_control(
    explore: pd.DataFrame, config: BacktestConfig, spec: IdeaSpec, k: int, runs: int
) -> list[float]:
    """Mean net R of ``runs`` matched random runs (in parallel when many)."""
    tasks = [(seed, k, spec.max_bars + 1, spec.side) for seed in range(runs)]
    init = (explore, config, spec.symbol, spec.interval)
    if runs < 50:
        _pool_init(*init)
        means = [_random_mean(t) for t in tasks]
    else:
        workers = max(1, (os.cpu_count() or 2) - 1)
        with ProcessPoolExecutor(
            workers, initializer=_pool_init, initargs=init
        ) as pool:
            means = list(pool.map(_random_mean, tasks, chunksize=8))
    return [m for m in means if m is not None]


def verdict_from(
    r_values: list[float], random_means: list[float], attempts: int
) -> dict[str, Any]:
    """Classify the net R of the trades against zero and against random entries."""
    if len(r_values) < MIN_TRADES:
        return {
            "code": "POCAS_OPERACIONES",
            "text": f"Solo {len(r_values)} operaciones: no alcanza para concluir.",
            "ci": None,
            "mde_r": None,
            "p_random": None,
        }
    low, high = block_mean_ci(r_values, ci_level(attempts))
    mean = float(np.mean(r_values))
    p_random = empirical_p(mean, random_means) if random_means else None
    if high < 0:
        code = "PIERDE"
        text = "Pierde después de costos, con margen suficiente para descartar azar."
    elif low > 0 and p_random is not None and p_random <= ALPHA / attempts:
        code = "MERECE_ESTUDIO"
        text = (
            "Merece más estudio: supera al azar en estos datos. No es una prueba "
            "de que siga ocurriendo."
        )
    else:
        code = "NO_SE_DISTINGUE"
        text = "No se distingue del azar con estos datos."
    # Half the interval: the smallest edge per trade these data could tell apart
    # from zero. Shown so "not distinguishable" is not read as "worthless".
    return {
        "code": code,
        "text": text,
        "ci": (low, high),
        "mde_r": (high - low) / 2.0,
        "p_random": p_random,
    }


def risk_path(
    capital: float, r_values: list[float], risk_pct: float
) -> tuple[float, float]:
    """Capital after compounding risk_pct of equity per trade, and max drawdown %.

    Approved 2026-11-14 (plan v5, C12): the story must risk what the owner would
    risk, not 100 % of equity as the engine does. Each trade multiplies equity by
    (1 + risk_pct/100 * net R).
    """
    equity = peak = capital
    worst = 0.0
    for r in r_values:
        equity *= 1.0 + risk_pct / 100.0 * r
        peak = max(peak, equity)
        worst = max(worst, (peak - equity) / peak * 100.0)
    return equity, worst


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
        f"${capital:,.0f} y arriesgando {result.get('risk_pct', 1.0):g} % por operación "
        f"habrías terminado con ${result['final_capital']:,.0f}. "
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


def spec_key(spec: IdeaSpec) -> str:
    """Identity of a rule on a market, for the one-time use of reserved data."""
    return (
        f"{spec.symbol}|{spec.interval}|{spec.entry}|{spec.side}|"
        f"{spec.sl_atr:g}|{spec.tp_atr:g}|{spec.max_bars}"
    )


def _evaluate(
    segment: pd.DataFrame,
    spec: IdeaSpec,
    attempts: int,
    n_random: int | None,
    capital: float,
    risk_pct: float,
    start: int = 0,
) -> dict[str, Any]:
    """Rule, random control and story on one segment; trades start at ``start``."""
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
    events = signals_to_events(
        segment, CANDIDATES[spec.entry](segment), spec.symbol, spec.interval
    )
    trades, _ = BacktestEngine(config=config).run(segment, events)
    r_values = _net_r(trades)
    runs = random_runs_for(attempts) if n_random is None else n_random
    random_means = (
        random_control(segment, config, spec, len(trades), runs) if trades else []
    )
    verdict = verdict_from(r_values, random_means, attempts)
    final_capital, max_dd = risk_path(capital, r_values, risk_pct)
    traded = segment.iloc[start:]
    return {
        **verdict,
        "trades": len(trades),
        "mean_r": float(np.mean(r_values)) if r_values else None,
        "win_pct": (
            100.0 * sum(t.net_pnl > 0 for t in trades) / len(trades) if trades else None
        ),
        "random_best": max(random_means) if random_means else None,
        "random_runs": len(random_means),
        "attempts": attempts,
        "capital": capital,
        "risk_pct": risk_pct,
        "r_values": r_values,
        "final_capital": final_capital,
        "worst_streak": worst_streak([t.net_pnl for t in trades]),
        "max_drawdown_pct": max_dd,
        "hold_final": capital
        * float(traded["close"].iloc[-1])
        / float(traded["close"].iloc[0]),
        "first_date": str(traded["timestamp"].iloc[0])[:10],
        "last_date": str(traded["timestamp"].iloc[-1])[:10],
        "first_entry": min(t.entry_timestamp for t in trades) if trades else None,
        "last_entry": max(t.entry_timestamp for t in trades) if trades else None,
        "key": spec_key(spec),
    }


def verify_idea(
    df: pd.DataFrame,
    spec: IdeaSpec,
    attempts: int,
    n_random: int | None = None,
    capital: float = 1000.0,
    risk_pct: float = 1.0,
) -> dict[str, Any]:
    """Explore the first 80 %; the reserved 20 % is never touched here."""
    cut = int(len(df) * EXPLORE_SHARE)
    explore = df.iloc[:cut].reset_index(drop=True)
    explore.attrs = {}
    result = _evaluate(explore, spec, attempts, n_random, capital, risk_pct)
    return {**result, "reserved_bars": len(df) - cut}


def verify_holdout(
    df: pd.DataFrame,
    spec: IdeaSpec,
    n_random: int | None = None,
    capital: float = 1000.0,
    risk_pct: float = 1.0,
) -> dict[str, Any]:
    """One confirmatory test on the reserved 20 % (approved 2026-11-14, plan v5 C11).

    The warm-up bars before the cut only feed the indicators: signals start at
    WARMUP_BARS, so every entry is inside data the rule never saw. It is a single
    test decided in advance, so its level is that of attempt 1; the caller must
    allow it once per rule and market.
    """
    cut = int(len(df) * EXPLORE_SHARE)
    segment = df.iloc[max(0, cut - WARMUP_BARS) :].reset_index(drop=True)
    segment.attrs = {}
    start = min(WARMUP_BARS, cut)
    return _evaluate(segment, spec, 1, n_random, capital, risk_pct, start=start)
