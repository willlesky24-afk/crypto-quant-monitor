"""v3.0 screening: each piece of the model and classic methods as lone signals.

Why: the combined Quant Score lost in 2024, but that does not say which piece
adds and which subtracts. Every candidate here enters through the same engine,
with the same exit and costs, so differences come from the entry alone.

Fixed parameters (declared before seeing results, not optimised):
- trend, RSI bands, value area, regime: as defined in the existing model.
- Donchian 20: the classic 4-week channel of 20 trading sessions.
- Time-series momentum: sign of past return (Moskowitz, Ooi, Pedersen 2012).
  180 4h bars is about one month; on these bars it is a project choice, not a
  value taken from the paper.
- Bollinger 20/2: the standard settings published by John Bollinger.
- RSI 30/70 reversion: the standard bands published by Welles Wilder.

A signal at bar T uses only data up to T; the engine enters at T+1 open.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from .backtest_models import SignalEvent, TradeDirection
from .regime_classifier import MarketRegime, RegimeClassifier
from .volume_profile import VolumeProfile

WARMUP_BARS = 200  # same warm-up as the model: 200 EMA samples observed
CONTROL_SEED = 20261101


def _as_signal(long_mask: pd.Series, short_mask: pd.Series) -> pd.Series:
    out = pd.Series(0, index=long_mask.index, dtype=int)
    out[long_mask.fillna(False).astype(bool)] = 1
    out[short_mask.fillna(False).astype(bool)] = -1
    return out


def signal_trend(df: pd.DataFrame) -> pd.Series:
    c, fast, slow = df["close"], df["ema_50"], df["ema_200"]
    return _as_signal((c > fast) & (fast > slow), (c < fast) & (fast < slow))


def signal_rsi_momentum(df: pd.DataFrame) -> pd.Series:
    rsi = df["rsi"]
    return _as_signal((rsi >= 50) & (rsi < 70), rsi < 30)


def signal_rsi_reversion(df: pd.DataFrame) -> pd.Series:
    rsi = df["rsi"]
    return _as_signal(rsi < 30, rsi > 70)


def signal_volume_direction(df: pd.DataFrame) -> pd.Series:
    """Volume has no direction; the candle body supplies it."""
    loud = df["volume"] > df["volume_average"]
    return _as_signal(
        loud & (df["close"] > df["open"]), loud & (df["close"] < df["open"])
    )


def signal_donchian(df: pd.DataFrame, window: int = 20) -> pd.Series:
    upper = df["high"].shift(1).rolling(window).max()
    lower = df["low"].shift(1).rolling(window).min()
    return _as_signal(df["close"] > upper, df["close"] < lower)


def signal_tsmom(df: pd.DataFrame, lookback: int = 180) -> pd.Series:
    past = df["close"].shift(lookback)
    return _as_signal(df["close"] > past, df["close"] < past)


def signal_bollinger(df: pd.DataFrame, window: int = 20, k: float = 2.0) -> pd.Series:
    rolling = df["close"].rolling(window)
    mid, std = rolling.mean(), rolling.std(ddof=0)
    return _as_signal(df["close"] < mid - k * std, df["close"] > mid + k * std)


def signal_random(df: pd.DataFrame, seed: int = CONTROL_SEED) -> pd.Series:
    """Control: coin-flip entries show what costs and exits do with no skill."""
    rng = np.random.default_rng(seed)
    return pd.Series(rng.choice([-1, 1], size=len(df)), index=df.index, dtype=int)


def signal_profile(df: pd.DataFrame) -> pd.Series:
    vp = VolumeProfile()
    out = pd.Series(0, index=df.index, dtype=int)
    for i in range(WARMUP_BARS - 1, len(df)):
        sub = df.iloc[: i + 1]
        profile = vp.calculate(sub)
        price = float(sub["close"].iloc[-1])
        if price > profile["vah"]:
            out.iloc[i] = 1
        elif price < profile["val"]:
            out.iloc[i] = -1
    return out


def signal_regime(df: pd.DataFrame) -> pd.Series:
    out = pd.Series(0, index=df.index, dtype=int)
    results = RegimeClassifier().classify_series(df, warmup_bars=25)
    for offset, res in enumerate(results):
        if res.regime == MarketRegime.TRENDING_BULL:
            out.iloc[offset + 24] = 1
        elif res.regime == MarketRegime.TRENDING_BEAR:
            out.iloc[offset + 24] = -1
    return out


def signal_predictive(df: pd.DataFrame) -> pd.Series:
    """The predictive engine's own bias, reproducing the runner's causal cut."""
    from .predictive_engine import PredictiveEngine

    engine = PredictiveEngine()
    regimes = RegimeClassifier().classify_series(df, warmup_bars=25)
    values = np.array([r.regime.value for r in regimes], dtype=object)
    out = pd.Series(0, index=df.index, dtype=int)
    for i in range(WARMUP_BARS - 1, len(df)):
        offset = i - 24
        cutoff = max(0, offset - engine.horizon_bars + 1)
        res = engine.evaluate(
            df.iloc[: i + 1],
            current_regime_res=regimes[offset],
            precomputed_past_regimes=regimes[:cutoff],
            precomputed_past_regime_values=values[:cutoff],
        )
        if res.direction_bias == "LONG":
            out.iloc[i] = 1
        elif res.direction_bias == "SHORT":
            out.iloc[i] = -1
    return out


CANDIDATES: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
    "trend_ema": signal_trend,
    "momentum_rsi": signal_rsi_momentum,
    "volume_direction": signal_volume_direction,
    "profile_value_area": signal_profile,
    "regime": signal_regime,
    "predictive": signal_predictive,
    "donchian_20": signal_donchian,
    "tsmom_180": signal_tsmom,
    "bollinger_20_2": signal_bollinger,
    "reversion_rsi": signal_rsi_reversion,
    "control_random": signal_random,
}


def signals_to_events(
    df: pd.DataFrame, signal: pd.Series, symbol: str, interval: str
) -> list[SignalEvent]:
    """Non-flat bars after warm-up with a usable ATR become engine signals."""
    events = []
    for i in range(WARMUP_BARS, len(df)):
        value = int(signal.iloc[i])
        atr = float(df["atr"].iloc[i])
        if value == 0 or not np.isfinite(atr) or atr <= 0:
            continue
        price = float(df["close"].iloc[i])
        events.append(
            SignalEvent(
                signal_id=f"cand-{symbol}-{interval}-{i}",
                symbol=symbol,
                timeframe=interval,
                candle_timestamp=df["timestamp"].iloc[i],
                price_at_signal=price,
                signal_state="SCREENING",
                confidence=100.0,
                decision="SCREENING",
                quant_score=100.0,
                risk_level="N/A",
                atr=atr,
                poc=price,
                vah=price,
                val=price,
                direction=(
                    TradeDirection.LONG.value
                    if value > 0
                    else TradeDirection.SHORT.value
                ),
            )
        )
    return events
