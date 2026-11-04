from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from src.backtest_models import (
    EXCURSION_POLICY_VERSION,
    CalibrationState,
    ExcursionObservability,
    OptimizationUnavailableError,
)
from src.regime_classifier import MarketRegime, RegimeClassifier

if TYPE_CHECKING:
    from src.backtest_models import BacktestReport, TradeResult


@dataclass(frozen=True)
class OptimizedParameters:
    """Optimized risk management parameters for a given market regime and volatility state."""

    regime: str
    volatility_state: str
    atr_tp_multiplier: float
    atr_sl_multiplier: float
    expected_rr: float
    sample_size: int
    confidence: float
    validation_period: dict[str, Any]
    calibration_state: str = CalibrationState.NOT_REQUESTED.value
    excursion_policy_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MFEMAEDistribution:
    """Statistical summary of empirical MFE and MAE distributions."""

    sample_size: int
    mfe_mean: float
    mfe_median: float
    mfe_p25: float
    mfe_p75: float
    mfe_p90: float
    mae_mean: float
    mae_median: float
    mae_p75: float
    mae_p85: float
    win_rate_pct: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StrategyOptimizer:
    """Empirical parameter optimizer using MFE / MAE distributions and walk-forward validation.

    Calibrates Take Profit and Stop Loss ATR multipliers per market regime without
    introducing look-ahead bias or overfitting, adhering to:
    - Train (2023-2024) vs. Validation (2025) temporal split.
    - Parameter bounds [min_atr, max_atr].
    - Minimum sample size requirements and small-sample confidence penalties.
    - Strict causal separation between observed training data and out-of-sample evaluation.
    """

    # Regime-specific default ATR multipliers for small-sample fallbacks
    REGIME_DEFAULTS: dict[str, dict[str, float]] = {
        MarketRegime.TRENDING_BULL.value: {
            "tp": 3.5,
            "sl": 1.5,
            "volatility": "NORMAL",
        },
        MarketRegime.TRENDING_BEAR.value: {
            "tp": 3.0,
            "sl": 1.8,
            "volatility": "NORMAL",
        },
        MarketRegime.RANGING_CONSOLIDATION.value: {
            "tp": 2.2,
            "sl": 1.2,
            "volatility": "COMPRESSED",
        },
        MarketRegime.HIGH_VOLATILITY_EXPANSION.value: {
            "tp": 4.5,
            "sl": 2.2,
            "volatility": "EXPANDED",
        },
    }

    def __init__(
        self,
        min_sample_size: int = 10,
        min_atr_tp: float = 2.0,
        max_atr_tp: float = 6.0,
        min_atr_sl: float = 1.0,
        max_atr_sl: float = 3.5,
        default_tp: float = 3.0,
        default_sl: float = 1.5,
        train_end: pd.Timestamp | str = "2025-01-01 00:00:00+00:00",
        regime_classifier: RegimeClassifier | None = None,
    ) -> None:
        self.min_sample_size = min_sample_size
        self.min_atr_tp = min_atr_tp
        self.max_atr_tp = max_atr_tp
        self.min_atr_sl = min_atr_sl
        self.max_atr_sl = max_atr_sl
        self.default_tp = default_tp
        self.default_sl = default_sl
        self.train_end = pd.to_datetime(train_end, utc=True)
        self.regime_classifier = regime_classifier or RegimeClassifier()

    def _extract_trade_dict(self, trade: TradeResult | dict[str, Any]) -> dict[str, Any]:
        """Normalizes a TradeResult instance or dictionary into a uniform dictionary."""
        if hasattr(trade, "to_dict"):
            d = trade.to_dict()
        elif isinstance(trade, dict):
            d = trade.copy()
        else:
            d = {
                "trade_id": getattr(trade, "trade_id", ""),
                "symbol": getattr(trade, "symbol", ""),
                "signal_timestamp": getattr(trade, "signal_timestamp", None),
                "entry_timestamp": getattr(trade, "entry_timestamp", None),
                "entry_price": getattr(trade, "entry_price", 0.0),
                "exit_price": getattr(trade, "exit_price", 0.0),
                "mfe_pct": getattr(trade, "mfe_pct", None),
                "mae_pct": getattr(trade, "mae_pct", None),
                "mfe_observability": getattr(trade, "mfe_observability", None),
                "mae_observability": getattr(trade, "mae_observability", None),
                "mfe_exact_pct": getattr(trade, "mfe_exact_pct", None),
                "mae_exact_pct": getattr(trade, "mae_exact_pct", None),
                "excursion_policy_version": getattr(trade, "excursion_policy_version", None),
                "is_win": getattr(trade, "is_win", False),
                "regime": getattr(trade, "regime", ""),
                "atr_entry": getattr(trade, "atr_entry", 0.0),
            }

        # Check for dynamic or extra attributes if not present in d
        if not d.get("regime") and hasattr(trade, "regime"):
            d["regime"] = getattr(trade, "regime")
        if not d.get("atr_entry") and hasattr(trade, "atr_entry"):
            d["atr_entry"] = getattr(trade, "atr_entry")

        # Ensure timestamps are pandas Timestamps in UTC
        for ts_key in ("signal_timestamp", "entry_timestamp", "exit_timestamp"):
            if ts_key in d and d[ts_key] is not None:
                d[ts_key] = pd.to_datetime(d[ts_key], utc=True)

        return d

    def split_walk_forward(
        self,
        trades: list[TradeResult | dict[str, Any]],
        train_end: pd.Timestamp | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Splits trades into In-Sample (TRAIN) and Out-of-Sample (VALIDATION) sets.

        TRAIN: entry_timestamp < train_end (e.g. 2023-2024)
        VALIDATION: entry_timestamp >= train_end (e.g. 2025)
        """
        cutoff = train_end if train_end is not None else self.train_end
        normalized_trades = [self._extract_trade_dict(t) for t in trades]

        train_trades: list[dict[str, Any]] = []
        val_trades: list[dict[str, Any]] = []

        for t in normalized_trades:
            ts = t.get("entry_timestamp") or t.get("signal_timestamp")
            if ts is None:
                continue
            if ts < cutoff:
                train_trades.append(t)
            else:
                val_trades.append(t)

        return train_trades, val_trades

    def _calculate_atr_excursions(
        self,
        trade: dict[str, Any],
    ) -> tuple[float, float]:
        """Normalize independently exact excursions; never impute ATR or a proxy."""
        if trade.get("excursion_policy_version") != EXCURSION_POLICY_VERSION:
            raise OptimizationUnavailableError("Optimización no disponible: versión de excursiones heredada o desconocida.")
        for name in ("mfe", "mae"):
            if trade.get(f"{name}_observability") != ExcursionObservability.EXACT_OHLC.value:
                raise OptimizationUnavailableError(
                    f"Optimización no disponible: cobertura {name.upper()} no es EXACT_OHLC completa."
                )
        try:
            entry_price = float(trade["entry_price"])
            atr_entry = float(trade["atr_entry"])
            mfe_pct = float(trade["mfe_exact_pct"])
            mae_pct = float(trade["mae_exact_pct"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise OptimizationUnavailableError("Optimización no disponible: MFE/MAE exactos o ATR ausentes.") from exc
        if not all(np.isfinite(value) for value in (entry_price, atr_entry, mfe_pct, mae_pct)):
            raise OptimizationUnavailableError("Optimización no disponible: excursión o ATR no finito.")
        if entry_price <= 0 or atr_entry <= 0 or mfe_pct < 0 or mae_pct < 0:
            raise OptimizationUnavailableError("Optimización no disponible: precio, ATR o excursión inválidos.")
        raw_atr_pct = (atr_entry / entry_price) * 100.0
        if not np.isfinite(raw_atr_pct) or raw_atr_pct <= 0:
            raise OptimizationUnavailableError("Optimización no disponible: escala ATR no finita.")
        atr_pct = max(raw_atr_pct, 1e-4)
        mfe_atr = mfe_pct / atr_pct
        mae_atr = mae_pct / atr_pct

        if not all(np.isfinite(value) for value in (mfe_atr, mae_atr)):
            raise OptimizationUnavailableError("Optimización no disponible: múltiplo ATR no finito.")

        return mfe_atr, mae_atr

    def analyze_distribution(
        self,
        trades: list[TradeResult | dict[str, Any]],
    ) -> MFEMAEDistribution:
        """Computes empirical percentiles and summary statistics for MFE / MAE distributions."""
        if not trades:
            raise OptimizationUnavailableError("Optimización no disponible: NO_TRADES.")

        norm_trades = [self._extract_trade_dict(t) for t in trades]
        mfe_list: list[float] = []
        mae_list: list[float] = []
        wins = 0

        for t in norm_trades:
            mfe_atr, mae_atr = self._calculate_atr_excursions(t)
            mfe_list.append(mfe_atr)
            mae_list.append(mae_atr)
            if t.get("is_win", False):
                wins += 1

        n = len(norm_trades)
        mfe_arr = np.array(mfe_list, dtype=float)
        mae_arr = np.array(mae_list, dtype=float)

        return MFEMAEDistribution(
            sample_size=n,
            mfe_mean=float(np.mean(mfe_arr)),
            mfe_median=float(np.median(mfe_arr)),
            mfe_p25=float(np.percentile(mfe_arr, 25)),
            mfe_p75=float(np.percentile(mfe_arr, 75)),
            mfe_p90=float(np.percentile(mfe_arr, 90)),
            mae_mean=float(np.mean(mae_arr)),
            mae_median=float(np.median(mae_arr)),
            mae_p75=float(np.percentile(mae_arr, 75)),
            mae_p85=float(np.percentile(mae_arr, 85)),
            win_rate_pct=float((wins / n) * 100.0) if n > 0 else 0.0,
        )

    def optimize_regime(
        self,
        regime: str | MarketRegime,
        train_trades: list[TradeResult | dict[str, Any]],
        val_trades: list[TradeResult | dict[str, Any]] | None = None,
    ) -> OptimizedParameters:
        """Calibrates optimal ATR TP and ATR SL using empirical MFE/MAE distribution of TRAIN trades.

        Evaluates the resulting parameters out-of-sample against VALIDATION trades.
        """
        regime_str = regime.value if isinstance(regime, MarketRegime) else str(regime)
        defaults = self.REGIME_DEFAULTS.get(
            regime_str,
            {"tp": self.default_tp, "sl": self.default_sl, "volatility": "NORMAL"},
        )
        volatility_state = defaults.get("volatility", "NORMAL")

        norm_train = [self._extract_trade_dict(t) for t in train_trades]
        norm_val = [self._extract_trade_dict(t) for t in val_trades] if val_trades else []
        n_train = len(norm_train)

        # 1. Handling small or insufficient sample sizes (Anti-Overfitting Protection)
        if n_train < self.min_sample_size:
            raise OptimizationUnavailableError(
                f"Optimización no disponible para {regime_str}: muestra {n_train} "
                f"inferior al mínimo {self.min_sample_size}."
            )

        # Validate the entire train/validation cohort before computing any statistics.
        for trade in (*norm_train, *norm_val):
            self._calculate_atr_excursions(trade)

        # 2. Empirical MFE / MAE Optimization on TRAIN trades
        train_dist = self.analyze_distribution(norm_train)

        # Separate winning trades for MAE analysis
        win_trades = [t for t in norm_train if t.get("is_win", False)]
        if len(win_trades) >= 3:
            win_dist = self.analyze_distribution(win_trades)
            # Optimal SL: 80th-85th percentile of MAE for winning trades + 15% buffer
            candidate_sl = win_dist.mae_p85 * 1.15
        else:
            # Fallback: 75th percentile of MAE across all trades
            candidate_sl = train_dist.mae_p75 * 1.10

        # Optimal TP: 60th percentile of MFE (empirically reachable target before exhaustion)
        candidate_tp = train_dist.mfe_median * 1.10

        # Enforce minimum Risk/Reward ratio of 1.2
        if candidate_tp < candidate_sl * 1.2:
            candidate_tp = candidate_sl * 1.25

        # 3. Anti-overfitting clipping to predefined safety bounds
        atr_tp = float(min(self.max_atr_tp, max(self.min_atr_tp, candidate_tp)))
        atr_sl = float(min(self.max_atr_sl, max(self.min_atr_sl, candidate_sl)))
        expected_rr = round(atr_tp / max(atr_sl, 1e-6), 2)

        # 4. Confidence calculation based on sample size and stability
        sample_factor = min(1.0, n_train / 40.0)
        confidence = round(0.50 + 0.50 * sample_factor, 3)

        # 5. Out-of-sample evaluation on VALIDATION trades
        val_info: dict[str, Any] = {
            "train_period": "2023-2024",
            "validation_period": "2025",
            "train_sample_size": n_train,
            "validation_sample_size": len(norm_val),
            "train_win_rate_pct": round(train_dist.win_rate_pct, 2),
        }

        if norm_val:
            val_wins = 0
            val_losses = 0
            for vt in norm_val:
                mfe_atr, mae_atr = self._calculate_atr_excursions(vt)
                # Intrabar conservative logic: if MAE reaches SL, it stops out
                if mae_atr >= atr_sl:
                    val_losses += 1
                elif mfe_atr >= atr_tp:
                    val_wins += 1
                else:
                    # Trailing or horizon exit
                    if mfe_atr > mae_atr:
                        val_wins += 1
                    else:
                        val_losses += 1

            n_val = len(norm_val)
            val_win_rate = (val_wins / n_val) * 100.0 if n_val > 0 else 0.0
            val_info["validation_simulated_win_rate_pct"] = round(val_win_rate, 2)
            val_info["validation_simulated_wins"] = val_wins
            val_info["validation_simulated_losses"] = val_losses
        else:
            val_info["validation_simulated_win_rate_pct"] = None

        return OptimizedParameters(
            regime=regime_str,
            volatility_state=volatility_state,
            atr_tp_multiplier=round(atr_tp, 2),
            atr_sl_multiplier=round(atr_sl, 2),
            expected_rr=expected_rr,
            sample_size=n_train,
            confidence=confidence,
            validation_period=val_info,
            calibration_state=CalibrationState.AVAILABLE.value,
            excursion_policy_version=EXCURSION_POLICY_VERSION,
        )

    def optimize_all_regimes(
        self,
        trades: list[TradeResult | dict[str, Any]],
        train_end: pd.Timestamp | None = None,
        candles: pd.DataFrame | None = None,
    ) -> dict[str, OptimizedParameters]:
        """Groups trades by regime, executes walk-forward split, and optimizes each regime separately."""
        norm_trades = [self._extract_trade_dict(t) for t in trades]

        # If trades lack regime annotation but candles are supplied, classify regimes
        if candles is not None and not candles.empty:
            regime_series = self.regime_classifier.classify_series(candles)
            regime_map = {r.timestamp: r.regime.value for r in regime_series}

            for t in norm_trades:
                if not t.get("regime"):
                    ts = t.get("signal_timestamp") or t.get("entry_timestamp")
                    if ts in regime_map:
                        t["regime"] = regime_map[ts]

        # Perform Walk-Forward split: TRAIN vs VALIDATION
        train_trades, val_trades = self.split_walk_forward(norm_trades, train_end=train_end)

        # Regimes to optimize
        target_regimes = [
            MarketRegime.TRENDING_BULL.value,
            MarketRegime.TRENDING_BEAR.value,
            MarketRegime.RANGING_CONSOLIDATION.value,
            MarketRegime.HIGH_VOLATILITY_EXPANSION.value,
        ]

        results: dict[str, OptimizedParameters] = {}
        for reg in target_regimes:
            train_sub = [t for t in train_trades if t.get("regime") == reg]
            val_sub = [t for t in val_trades if t.get("regime") == reg]

            if not train_sub:
                continue

            opt_params = self.optimize_regime(
                regime=reg,
                train_trades=train_sub,
                val_trades=val_sub,
            )
            results[reg] = opt_params

        if not results:
            raise OptimizationUnavailableError("Optimización no disponible: NO_TRADES de entrenamiento por régimen.")

        return results

    def optimize_from_report(
        self,
        report: BacktestReport,
        candles: pd.DataFrame | None = None,
        train_end: pd.Timestamp | None = None,
    ) -> dict[str, OptimizedParameters]:
        """Convenience entrypoint: extracts closed trades from BacktestReport and optimizes."""
        closed_trades = getattr(report, "trades", None)
        if closed_trades is None:
            closed_trades = getattr(report, "closed_trades", [])
        return self.optimize_all_regimes(closed_trades, train_end=train_end, candles=candles)
