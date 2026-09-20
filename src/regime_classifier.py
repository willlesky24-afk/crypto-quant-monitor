from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

from .indicators import TechnicalIndicators


class MarketRegime(str, Enum):
    """Enumeration of market structural regimes."""

    TRENDING_BULL = "TRENDING_BULL"
    TRENDING_BEAR = "TRENDING_BEAR"
    RANGING_CONSOLIDATION = "RANGING_CONSOLIDATION"
    HIGH_VOLATILITY_EXPANSION = "HIGH_VOLATILITY_EXPANSION"


@dataclass(frozen=True)
class RegimeResult:
    """Immutable report of a causal market regime classification."""

    timestamp: pd.Timestamp
    regime: MarketRegime
    confidence: float
    features_used: dict[str, float]

    def to_dict(self) -> dict:
        return {
            "timestamp": str(self.timestamp),
            "regime": self.regime.value if isinstance(self.regime, MarketRegime) else str(self.regime),
            "confidence": round(float(self.confidence), 4),
            "features_used": {
                k: round(float(v), 6) if isinstance(v, (int, float, np.floating, np.integer)) else v
                for k, v in self.features_used.items()
            },
        }


class RegimeClassifier:
    """Causal, deterministic market regime classifier.

    Evaluates structural market state (Bullish Trend, Bearish Trend, Consolidation,
    or Volatility Expansion) strictly using information available up to candle T (t <= T).
    Guarantees zero look-ahead bias and fully reproducible probability features.
    """

    def __init__(self, indicators: TechnicalIndicators | None = None, min_bars: int = 30):
        self.indicators = indicators or TechnicalIndicators()
        self.min_bars = min_bars

    def classify(self, df: pd.DataFrame) -> RegimeResult:
        """Classifies the market regime for the latest closed candle in the DataFrame.

        Parameters:
        - df: OHLCV DataFrame up to candle T.

        Returns:
        - RegimeResult containing regime label, confidence in [0.0, 1.0], and feature dictionary.
        """
        if df.empty:
            raise ValueError("No se puede clasificar un DataFrame vacío")

        required_cols = {"timestamp", "high", "low", "close", "volume"}
        missing = required_cols.difference(set(df.columns))
        if missing:
            missing_str = ", ".join(sorted(missing))
            raise ValueError(f"Faltan columnas requeridas para clasificar régimen: {missing_str}")

        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            candles = df.copy()
            candles["timestamp"] = pd.to_datetime(candles["timestamp"], utc=True)
            candles = candles.sort_values("timestamp").reset_index(drop=True)
        else:
            candles = df

        last_ts = candles["timestamp"].iloc[-1]

        if len(candles) < self.min_bars:
            return RegimeResult(
                timestamp=last_ts,
                regime=MarketRegime.RANGING_CONSOLIDATION,
                confidence=0.0,
                features_used={"bars_count": float(len(candles)), "min_required": float(self.min_bars)},
            )

        # Enrich technical indicators if not already computed
        if not {"rsi", "atr", "ema_50", "ema_200", "volume_average"}.issubset(set(candles.columns)):
            enriched = self.indicators.calculate_all(candles)
        else:
            enriched = candles

        last_row = enriched.iloc[-1]
        price = float(last_row["close"])
        ema_50 = float(last_row["ema_50"])
        ema_200 = float(last_row["ema_200"])
        rsi = float(last_row["rsi"]) if not np.isnan(last_row["rsi"]) else 50.0
        atr = float(last_row["atr"]) if not np.isnan(last_row["atr"]) else price * 0.01
        volume = float(last_row["volume"])
        vol_ma = float(last_row["volume_average"]) if not np.isnan(last_row["volume_average"]) else volume

        # ATR rolling baseline over available causal history (up to 50 bars)
        atr_window = min(50, len(enriched))
        atr_ma = float(enriched["atr"].tail(atr_window).mean())
        if np.isnan(atr_ma) or atr_ma <= 0:
            atr_ma = atr

        # Causal slope of EMA 50 over last 5 bars
        slope_lookback = min(5, len(enriched) - 1)
        ema_50_prev = float(enriched["ema_50"].iloc[-1 - slope_lookback])
        ema_slope_50 = (ema_50 - ema_50_prev) / (slope_lookback * max(atr, 1e-6))

        # Normalized feature metrics
        atr_ratio = atr / max(atr_ma, 1e-6)
        vol_ratio = volume / max(vol_ma, 1e-6)
        ema_spread = (ema_50 - ema_200) / max(ema_200, 1e-6)
        price_vs_ema200 = (price - ema_200) / max(ema_200, 1e-6)
        price_vs_ema50 = (price - ema_50) / max(ema_50, 1e-6)

        features = {
            "price": price,
            "ema_50": ema_50,
            "ema_200": ema_200,
            "rsi": rsi,
            "atr": atr,
            "atr_ma_50": atr_ma,
            "atr_ratio": atr_ratio,
            "vol_ratio": vol_ratio,
            "ema_slope_50": ema_slope_50,
            "ema_spread": ema_spread,
            "price_vs_ema200": price_vs_ema200,
            "price_vs_ema50": price_vs_ema50,
        }

        # -----------------------------------------------------------------
        # Classification Engine (Ordered and Deterministic)
        # -----------------------------------------------------------------

        # 1. High Volatility Expansion
        if (atr_ratio >= 1.4 and vol_ratio >= 1.25) or atr_ratio >= 1.65:
            regime = MarketRegime.HIGH_VOLATILITY_EXPANSION
            conf = 0.60 + min(0.40, (atr_ratio - 1.4) * 0.4 + max(0.0, vol_ratio - 1.25) * 0.2)

        # 2. Trending Bullish
        elif price > ema_200 and ema_50 > ema_200 and ema_slope_50 > 0.05 and rsi >= 50.0:
            regime = MarketRegime.TRENDING_BULL
            rsi_factor = (rsi - 50.0) / 50.0
            slope_factor = min(1.0, max(0.0, ema_slope_50 / 0.5))
            spread_factor = min(1.0, max(0.0, ema_spread / 0.05))
            conf = 0.50 + (0.25 * rsi_factor) + (0.15 * slope_factor) + (0.10 * spread_factor)

        # 3. Trending Bearish
        elif price < ema_200 and ema_50 < ema_200 and ema_slope_50 < -0.05 and rsi <= 50.0:
            regime = MarketRegime.TRENDING_BEAR
            rsi_factor = (50.0 - rsi) / 50.0
            slope_factor = min(1.0, max(0.0, abs(ema_slope_50) / 0.5))
            spread_factor = min(1.0, max(0.0, abs(ema_spread) / 0.05))
            conf = 0.50 + (0.25 * rsi_factor) + (0.15 * slope_factor) + (0.10 * spread_factor)

        # 4. Ranging / Consolidation
        else:
            regime = MarketRegime.RANGING_CONSOLIDATION
            rsi_neutrality = max(0.0, 1.0 - (abs(rsi - 50.0) / 30.0))
            atr_stability = max(0.0, 1.0 - abs(atr_ratio - 1.0))
            slope_flatness = max(0.0, 1.0 - (abs(ema_slope_50) / 0.1))
            conf = 0.50 + (0.25 * rsi_neutrality) + (0.15 * atr_stability) + (0.10 * slope_flatness)

        clamped_confidence = min(1.0, max(0.0, float(conf)))

        return RegimeResult(
            timestamp=last_ts,
            regime=regime,
            confidence=clamped_confidence,
            features_used=features,
        )

    def classify_series(self, df: pd.DataFrame, warmup_bars: int = 50) -> list[RegimeResult]:
        """Classifies market regime sequentially bar-by-bar across the entire dataset.

        Parameters:
        - df: OHLCV DataFrame.
        - warmup_bars: Minimum candles required before evaluating regimes.

        Returns:
        - List of RegimeResult objects from warmup_bars to end of dataset.
        """
        if df.empty or len(df) < warmup_bars:
            return []

        candles = df.copy()
        candles["timestamp"] = pd.to_datetime(candles["timestamp"], utc=True)
        candles = candles.sort_values("timestamp").reset_index(drop=True)

        enriched = self.indicators.calculate_all(candles)
        results: list[RegimeResult] = []

        total_bars = len(enriched)
        for t_idx in range(warmup_bars - 1, total_bars):
            sub_df = enriched.iloc[: t_idx + 1]
            res = self.classify(sub_df)
            results.append(res)

        return results
