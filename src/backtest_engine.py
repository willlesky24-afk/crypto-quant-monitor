from __future__ import annotations

import logging
import math
import re
from datetime import date, datetime
from numbers import Number
from typing import Any

import numpy as np
import pandas as pd

from .backtest_metrics import BacktestMetricsCalculator
from .backtest_models import (
    EXCURSION_POLICY_VERSION,
    BacktestConfig,
    BacktestValidationError,
    EquityPoint,
    ExcursionObservability,
    ExecutionPolicyVersion,
    ExecutionTraceStatus,
    MarketType,
    Position,
    PositionSide,
    SignalEvent,
    TradeExitReason,
    TradeResult,
)

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Chronological event-driven simulation engine for trading strategies.

    Executes entries at Open(T+1) strictly after signal confirmation at Close(T),
    models taker transaction fees and execution slippage, tracks MFE/MAE,
    and applies conservative intrabar stop resolution. This phase permits
    only SPOT LONG 1x; SHORT and PERP execution are blocked at entry.

    SPOT LONG 1x cash flows are kept at full float precision. Accounting
    reconciliation uses a tolerance of 1e-8 quote-currency units (plus
    1e-10 relative tolerance); only presentation metrics round to cents.
    """

    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()

    @staticmethod
    def _coherent_ohlc(
        open_price: float, high: float, low: float, close: float
    ) -> bool:
        """Local evidence check; does not change the engine's dataset acceptance policy."""
        return (
            all(
                math.isfinite(value) and value > 0
                for value in (open_price, high, low, close)
            )
            and low <= min(open_price, close) <= max(open_price, close) <= high
        )

    @staticmethod
    def _excursion_evidence(
        position: Position,
        bar_open: float,
        bar_high: float,
        bar_low: float,
        bar_close: float,
        opening_exit: bool,
        intrabar_exit: bool,
        is_short: bool = False,
    ) -> dict[str, float | str | None]:
        """Bound extrema attributable to the position, never inferring intrabar order.

        The fill (including slippage) is the excursion denominator, not an observed
        market high/low. An opening exit sees only Open; a horizon exit sees the
        full bar. For intrabar exits, the current High/Low are possible extrema,
        not necessarily observations made before the exit.
        """
        unknown: dict[str, float | str | None] = {
            "mfe_observability": ExcursionObservability.UNDETERMINED.value,
            "mae_observability": ExcursionObservability.UNDETERMINED.value,
            "mfe_exact_pct": None,
            "mae_exact_pct": None,
            "mfe_lower_bound_pct": None,
            "mfe_upper_bound_pct": None,
            "mae_lower_bound_pct": None,
            "mae_upper_bound_pct": None,
        }
        if (
            not position.excursion_data_valid
            or position.observed_high_price is None
            or position.observed_low_price is None
            or not math.isfinite(position.entry_price)
            or position.entry_price <= 0
        ):
            return unknown
        if not opening_exit and not BacktestEngine._coherent_ohlc(
            bar_open, bar_high, bar_low, bar_close
        ):
            return unknown

        low_high = max(position.observed_high_price, bar_open)
        low_low = min(position.observed_low_price, bar_open)
        if opening_exit:
            high_high, high_low = low_high, low_low
        else:
            high_high = max(low_high, bar_high)
            high_low = min(low_low, bar_low)
            if not intrabar_exit:
                low_high, low_low = high_high, high_low
        entry = position.entry_price
        # low_high/low_low: extrema certainly observed; high_high/high_low: the
        # widest extrema possibly observed. SHORT mirrors LONG (v2.3 D1).
        if not is_short:
            mfe_lower = max(0.0, (low_high - entry) / entry * 100.0)
            mfe_upper = max(0.0, (high_high - entry) / entry * 100.0)
            mae_lower = max(0.0, (entry - low_low) / entry * 100.0)
            mae_upper = max(0.0, (entry - high_low) / entry * 100.0)
        else:
            mfe_lower = max(0.0, (entry - low_low) / entry * 100.0)
            mfe_upper = max(0.0, (entry - high_low) / entry * 100.0)
            mae_lower = max(0.0, (low_high - entry) / entry * 100.0)
            mae_upper = max(0.0, (high_high - entry) / entry * 100.0)

        result = unknown.copy()
        for name, lower, upper in (
            ("mfe", mfe_lower, mfe_upper),
            ("mae", mae_lower, mae_upper),
        ):
            exact = (not intrabar_exit) or math.isclose(
                lower, upper, rel_tol=1e-12, abs_tol=1e-12
            )
            result[f"{name}_observability"] = (
                ExcursionObservability.EXACT_OHLC.value
                if exact
                else ExcursionObservability.BOUNDED_OHLC.value
            )
            result[f"{name}_lower_bound_pct"] = lower
            result[f"{name}_upper_bound_pct"] = upper
            result[f"{name}_exact_pct"] = lower if exact else None
        return result

    @staticmethod
    def validate_chronology(df: pd.DataFrame) -> pd.Series:
        """Return UTC timestamps only when candle order is strict and unambiguous."""
        if "timestamp" not in df.columns:
            raise BacktestValidationError("Falta la columna temporal timestamp.")

        values = df["timestamp"]
        if values.isna().any():
            raise BacktestValidationError("timestamp contiene valores nulos o NaT.")
        for row, value in enumerate(values):
            if isinstance(value, Number):
                raise BacktestValidationError(
                    f"timestamp ambiguo en fila {row}: indicar fecha y zona horaria, "
                    "no un número sin unidad."
                )
            if isinstance(value, str):
                if not re.match(r"^\d{4}[-/]\d{2}[-/]\d{2}(?:[T\s].*)?$", value):
                    raise BacktestValidationError(
                        f"timestamp ambiguo en fila {row}: usar fecha con año primero."
                    )
            elif not isinstance(value, (date, datetime, pd.Timestamp, np.datetime64)):
                raise BacktestValidationError(
                    f"timestamp inválido en fila {row}: {type(value).__name__}."
                )

        try:
            timestamps = pd.to_datetime(
                values, utc=True, format="mixed", errors="raise"
            )
        except (ValueError, TypeError, OverflowError) as exc:
            raise BacktestValidationError(f"timestamp inválido: {exc}") from exc
        if timestamps.isna().any():
            raise BacktestValidationError("timestamp contiene valores nulos o NaT.")
        deltas = timestamps.diff().iloc[1:]
        if (deltas == pd.Timedelta(0)).any():
            raise BacktestValidationError(
                "timestamp duplicado: cada vela requiere un instante distinto."
            )
        if (deltas < pd.Timedelta(0)).any():
            raise BacktestValidationError(
                "timestamp desordenado: se requiere orden estrictamente creciente."
            )
        return timestamps

    def validate_config(self) -> None:
        """Supported ledgers: SPOT LONG 1x and MARGIN_1X (LONG/SHORT, 1x).

        MARGIN_1X models forex/spot-metals CFD-style exposure without leverage:
        the notional is reserved as margin and PnL = units x (exit - entry) x side.
        Crypto SPOT stays LONG-only (no borrowing is modelled); PERP stays blocked.
        """
        cfg = self.config
        market = str(cfg.market_type).strip().upper()
        direction = str(cfg.direction).strip().upper()
        if market not in (MarketType.SPOT.value, MarketType.MARGIN_1X.value):
            raise BacktestValidationError(
                f"market_type={cfg.market_type!r} no disponible: PERP y otros instrumentos "
                "requieren un modelo contable validado. Disponible: SPOT LONG 1x o "
                "MARGIN_1X."
            )
        if market == MarketType.SPOT.value and direction != PositionSide.LONG.value:
            raise BacktestValidationError(
                f"direction={cfg.direction!r} no disponible para SPOT: "
                "SHORT y BOTH requieren MARGIN_1X. Disponible: SPOT LONG 1x."
            )
        if direction not in ("LONG", "SHORT", "BOTH"):
            raise BacktestValidationError(f"direction={cfg.direction!r} no reconocida.")
        if not math.isfinite(cfg.leverage) or cfg.leverage != 1.0:
            raise BacktestValidationError(
                f"leverage={cfg.leverage!r} no disponible: "
                "no se simula apalancamiento. Disponible: 1x."
            )
        for name in (
            "initial_capital",
            "position_size_pct",
            "taker_fee_pct",
            "slippage_pct",
        ):
            value = getattr(cfg, name)
            if not math.isfinite(value):
                raise BacktestValidationError(f"{name} debe ser finito.")
        if cfg.initial_capital <= 0:
            raise BacktestValidationError("initial_capital debe ser positivo.")
        if not 0 <= cfg.position_size_pct <= 1:
            raise BacktestValidationError("position_size_pct debe estar entre 0 y 1.")
        if not 0 <= cfg.taker_fee_pct < 1:
            raise BacktestValidationError(
                "taker_fee_pct debe estar entre 0 y 1 (exclusivo)."
            )
        if not 0 <= cfg.slippage_pct < 1:
            raise BacktestValidationError(
                "slippage_pct debe estar entre 0 y 1 (exclusivo)."
            )

    def run(
        self,
        df: pd.DataFrame,
        signals: list[SignalEvent] | None = None,
    ) -> tuple[list[TradeResult], list[EquityPoint]]:
        """Runs chronological walk-forward backtest simulation across candle series.

        Parameters:
        - df: OHLCV DataFrame sorted chronologically by timestamp.
        - signals: List of SignalEvent objects generated upon fully closed candles.

        Returns:
        - Tuple of (closed_trades, equity_curve).
        """
        self.validate_config()
        if len(df) == 0:
            return [], []

        required_cols = {"timestamp", "open", "high", "low", "close"}
        if not required_cols.issubset(set(df.columns)):
            raise ValueError(
                f"El DataFrame debe contener las columnas: {required_cols}"
            )

        candles = df.copy()
        candles["timestamp"] = self.validate_chronology(candles)
        candles = candles.reset_index(drop=True)
        for column in ("open", "high", "low", "close"):
            numeric = pd.to_numeric(candles[column], errors="coerce")
            if not numeric.map(math.isfinite).all() or (numeric <= 0).any():
                raise BacktestValidationError(
                    f"Datos financieros inválidos: {column} debe ser positivo y finito."
                )

        is_margin = (
            str(self.config.market_type).strip().upper() == MarketType.MARGIN_1X.value
        )
        # v2.3 D2: optional per-candle bid/ask spread (absolute price units).
        # Prices are mid; buys execute at mid + spread/2, sells at mid - spread/2.
        if "spread" in candles.columns:
            spreads = pd.to_numeric(candles["spread"], errors="coerce")
            if not spreads.map(math.isfinite).all() or (spreads < 0).any():
                raise BacktestValidationError(
                    "Datos financieros inválidos: spread debe ser finito y >= 0."
                )
            half_spreads = (spreads / 2.0).tolist()
        else:
            half_spreads = [0.0] * len(candles)
        # v2.3 D4: MARGIN_1X instruments (forex, spot metals) do not trade during
        # the weekly closure; bars published inside it are rejected, not traded.
        if is_margin:
            try:
                from .market_data_providers import drop_weekend_closure
            except ImportError:  # Streamlit execution with ``src`` on sys.path.
                from market_data_providers import drop_weekend_closure
            if drop_weekend_closure(candles[["timestamp"]]).attrs[
                "weekend_bars_removed"
            ]:
                raise BacktestValidationError(
                    "Velas dentro del cierre semanal (viernes 17:00 a domingo 17:00 "
                    "Nueva York): no son negociables en MARGIN_1X."
                )

        # Build lookup map of valid signals by timestamp
        signals_map: dict[pd.Timestamp, SignalEvent] = {}
        if signals:
            for s in signals:
                signals_map[pd.to_datetime(s.candle_timestamp, utc=True)] = s

        current_cash = float(self.config.initial_capital)
        realized_net_pnl = 0.0
        active_position: Position | None = None
        pending_signal: SignalEvent | None = None
        closed_trades: list[TradeResult] = []
        raw_equity_curve: list[dict[str, Any]] = []

        total_bars = len(candles)

        for i in range(total_bars):
            bar = candles.iloc[i]
            bar_ts = bar["timestamp"]
            bar_open = float(bar["open"])
            bar_high = float(bar["high"])
            bar_low = float(bar["low"])
            bar_close = float(bar["close"])
            half_spread = half_spreads[i]

            # -----------------------------------------------------------------
            # 1. Process Pending Order (Entry on Open of T+1)
            # -----------------------------------------------------------------
            if active_position is None and pending_signal is not None:
                slip = self.config.slippage_pct
                sig_dir = pending_signal.direction.upper()
                is_short = ("SHORT" in sig_dir) or ("SELL" in sig_dir)
                if is_short and not is_margin:
                    raise BacktestValidationError(
                        f"Señal {sig_dir!r} no disponible para SPOT LONG 1x."
                    )
                if not is_short and sig_dir != PositionSide.LONG.value:
                    raise BacktestValidationError(f"Señal {sig_dir!r} no reconocida.")
                pos_side = (
                    PositionSide.SHORT.value if is_short else PositionSide.LONG.value
                )
                side_label = "SHORT" if is_short else "LONG"

                # LONG buys at ask, SHORT sells at bid; slippage is always adverse.
                if not is_short:
                    entry_price = (bar_open + half_spread) * (1.0 + slip)
                else:
                    entry_price = (bar_open - half_spread) * (1.0 - slip)
                if not math.isfinite(entry_price) or entry_price <= 0:
                    raise BacktestValidationError(
                        "Precio de entrada no positivo o no finito."
                    )

                allocated_cash = current_cash * max(
                    0.0, min(1.0, self.config.position_size_pct)
                )
                if allocated_cash > 0 and entry_price > 0:
                    if not math.isfinite(pending_signal.atr) or pending_signal.atr <= 0:
                        raise BacktestValidationError(
                            "ATR de señal no positivo o no finito: no se aplica un "
                            "ATR mínimo implícito."
                        )
                    # v2.3 D3: the real ATR, never a hidden floor (a 0.5% floor
                    # widened forex levels ~5x versus the live signal).
                    atr_val = float(pending_signal.atr)
                    tp_mult = (
                        pending_signal.tp_atr_multiple
                        if getattr(pending_signal, "tp_atr_multiple", None) is not None
                        else self.config.tp_atr_multiple
                    )
                    sl_mult = (
                        pending_signal.sl_atr_multiple
                        if getattr(pending_signal, "sl_atr_multiple", None) is not None
                        else self.config.sl_atr_multiple
                    )
                    try:
                        valid_tp_multiplier = not isinstance(
                            tp_mult, bool
                        ) and math.isfinite(tp_mult)
                    except (TypeError, ValueError):
                        valid_tp_multiplier = False
                    if not valid_tp_multiplier:
                        raise BacktestValidationError(
                            f"Multiplicador Take Profit {'SPOT ' if not is_short else ''}"
                            f"{side_label} no numérico o no finito."
                        )
                    if not all(math.isfinite(value) for value in (tp_mult, sl_mult)):
                        raise BacktestValidationError(
                            "Multiplicadores de niveles no finitos."
                        )

                    if not is_short:
                        tp_price = entry_price + (tp_mult * atr_val)
                        sl_price = entry_price - (sl_mult * atr_val)
                        tp_valid = (
                            math.isfinite(tp_price)
                            and tp_price > 0
                            and tp_price > entry_price
                        )
                    else:
                        tp_price = entry_price - (tp_mult * atr_val)
                        sl_price = entry_price + (sl_mult * atr_val)
                        tp_valid = (
                            math.isfinite(tp_price) and 0 < tp_price < entry_price
                        )
                    if not tp_valid:
                        if not is_short:
                            raise BacktestValidationError(
                                "Take Profit SPOT LONG inválido: debe ser finito, "
                                "positivo y superior al precio efectivo de entrada."
                            )
                        raise BacktestValidationError(
                            "Take Profit SHORT inválido: debe ser finito, positivo e "
                            "inferior al precio efectivo de entrada."
                        )
                    if not all(math.isfinite(level) for level in (tp_price, sl_price)):
                        raise BacktestValidationError("Niveles de salida no finitos.")

                    fee_entry = allocated_cash * self.config.taker_fee_pct
                    actual_capital_invested = allocated_cash - fee_entry
                    size_units = actual_capital_invested / entry_price
                    if not math.isfinite(size_units) or size_units <= 0:
                        raise BacktestValidationError(
                            "Unidades SPOT no positivas o no finitas."
                        )
                    if not math.isfinite(size_units * tp_price):
                        raise BacktestValidationError(
                            f"Take Profit {'SPOT ' if not is_short else ''}{side_label} "
                            "inválido: notional de salida no finito."
                        )
                    initial_risk_per_unit = (
                        sl_price - entry_price if is_short else entry_price - sl_price
                    )
                    initial_risk_amount = size_units * initial_risk_per_unit
                    stop_on_wrong_side = (
                        sl_price <= entry_price if is_short else sl_price >= entry_price
                    )
                    if (
                        not math.isfinite(sl_price)
                        or sl_price <= 0
                        or stop_on_wrong_side
                        or not math.isfinite(initial_risk_per_unit)
                        or initial_risk_per_unit <= 0
                        or not math.isfinite(initial_risk_amount)
                        or initial_risk_amount <= 0
                    ):
                        raise BacktestValidationError(
                            f"Stop inicial {'SHORT' if is_short else 'SPOT LONG'} o "
                            "riesgo inicial inválido."
                        )

                    # Observations attributable to the position are executable on
                    # the exit side: bid for LONG, ask for SHORT.
                    exit_adj = half_spread if is_short else -half_spread
                    active_position = Position(
                        position_id=f"pos-{len(closed_trades) + 1}",
                        signal=pending_signal,
                        entry_timestamp=bar_ts,
                        entry_price=entry_price,
                        size_units=size_units,
                        notional_entry=allocated_cash,
                        tp_price=tp_price,
                        sl_price=sl_price,
                        fee_entry=fee_entry,
                        initial_stop_price=sl_price,
                        initial_risk_per_unit=initial_risk_per_unit,
                        initial_risk_amount=initial_risk_amount,
                        side=pos_side,
                        funding_fees_accumulated=0.0,
                        last_funding_time=bar_ts,
                        highest_price=bar_high + exit_adj,
                        lowest_price=bar_low + exit_adj,
                        observed_high_price=bar_open + exit_adj,
                        observed_low_price=bar_open + exit_adj,
                    )
                    current_cash -= allocated_cash
                pending_signal = None

            # -----------------------------------------------------------------
            # 2. Process Active Position Exits & Intrabar Monitoring
            # -----------------------------------------------------------------
            if active_position is not None:
                active_position.bars_held += 1
                is_short_pos = active_position.side == PositionSide.SHORT.value

                # A. Apply Perpetual Funding Fees if applicable (every 8h: 00:00, 08:00, 16:00 UTC)
                is_perp = self.config.market_type.upper() == MarketType.PERP.value
                if is_perp and self.config.funding_rate_8h != 0.0:
                    if bar_ts > active_position.entry_timestamp:
                        # Check 8h settlement boundary (00:00, 08:00, 16:00 UTC)
                        if (bar_ts.hour % 8 == 0 and bar_ts.minute == 0) and (
                            active_position.last_funding_time is None
                            or bar_ts > active_position.last_funding_time
                        ):
                            current_notional = active_position.size_units * bar_close
                            if not is_short_pos:
                                funding_fee = (
                                    current_notional * self.config.funding_rate_8h
                                )
                            else:
                                funding_fee = (
                                    -current_notional * self.config.funding_rate_8h
                                )
                            active_position.funding_fees_accumulated += funding_fee
                            active_position.last_funding_time = bar_ts

                # B. Resolve exits against the stop already effective for this bar.
                # Exit-side executable prices: LONG sells at bid (mid - half
                # spread), SHORT buys back at ask (mid + half spread).
                adj = half_spread if is_short_pos else -half_spread
                ex_open, ex_high = bar_open + adj, bar_high + adj
                ex_low, ex_close = bar_low + adj, bar_close + adj
                active_stop = active_position.sl_price
                active_target = active_position.tp_price
                exit_triggered = False
                opening_exit = False
                exit_price = ex_close
                exit_reason = TradeExitReason.TIME_HORIZON.value
                slip = self.config.slippage_pct
                is_preexisting = bar_ts > active_position.entry_timestamp
                horizon_reached = (
                    active_position.bars_held >= self.config.max_holding_bars
                    or i == total_bars - 1
                )

                if not is_short_pos:
                    # 1. Opening priority for pre-existing positions (Gaps at Open of T)
                    if is_preexisting and ex_open <= active_stop:
                        # Adverse gap down: stop-market exit at Open, adverse slippage
                        exit_triggered = True
                        opening_exit = True
                        exit_price = ex_open * (1.0 - slip)
                        exit_reason = TradeExitReason.STOP_LOSS.value
                    elif is_preexisting and ex_open >= active_target:
                        # Favorable gap up: limit TP filled at target (no improvement)
                        exit_triggered = True
                        opening_exit = True
                        exit_price = active_target
                        exit_reason = TradeExitReason.TAKE_PROFIT.value
                    # 2. Intrabar monitoring; a conflict resolves SL first
                    elif ex_low <= active_stop:
                        exit_triggered = True
                        exit_price = active_stop * (1.0 - slip)
                        exit_reason = TradeExitReason.STOP_LOSS.value
                    elif ex_high >= active_target:
                        # Limit TP: no adverse slippage below the limit
                        exit_triggered = True
                        exit_price = active_target
                        exit_reason = TradeExitReason.TAKE_PROFIT.value
                    elif horizon_reached:
                        exit_triggered = True
                        exit_price = ex_close * (1.0 - slip)
                        exit_reason = TradeExitReason.TIME_HORIZON.value
                else:
                    # SHORT mirrors LONG exactly (v2.3 D1): gaps first, SL first on
                    # conflict, TP as a buy limit without slippage.
                    if is_preexisting and ex_open >= active_stop:
                        exit_triggered = True
                        opening_exit = True
                        exit_price = ex_open * (1.0 + slip)
                        exit_reason = TradeExitReason.STOP_LOSS.value
                    elif is_preexisting and ex_open <= active_target:
                        exit_triggered = True
                        opening_exit = True
                        exit_price = active_target
                        exit_reason = TradeExitReason.TAKE_PROFIT.value
                    elif ex_high >= active_stop:
                        exit_triggered = True
                        exit_price = active_stop * (1.0 + slip)
                        exit_reason = TradeExitReason.STOP_LOSS.value
                    elif ex_low <= active_target:
                        exit_triggered = True
                        exit_price = active_target
                        exit_reason = TradeExitReason.TAKE_PROFIT.value
                    elif horizon_reached:
                        exit_triggered = True
                        exit_price = ex_close * (1.0 + slip)
                        exit_reason = TradeExitReason.TIME_HORIZON.value

                # An opening exit has observed only Open(T); High/Low(T) occur
                # after the position is gone. Other paths retain the OHLC policy.
                if opening_exit:
                    active_position.update_excursions(high=ex_open, low=ex_open)
                else:
                    active_position.update_excursions(high=ex_high, low=ex_low)

                if exit_triggered:
                    # Describe only what the exit candle can establish. A pre-existing
                    # position opening at/beyond a level is resolved immediately at Open;
                    # subsequent intrabar extremes do not override the opening exit.
                    # Levels as (lower, upper) in price terms for either side.
                    lower_level, upper_level = (
                        (active_target, active_stop)
                        if is_short_pos
                        else (active_stop, active_target)
                    )
                    levels_coherent = (
                        0 < active_target < active_position.entry_price <= active_stop
                        if is_short_pos
                        else 0
                        < active_stop
                        <= active_position.entry_price
                        < active_target
                    )
                    if (
                        not all(
                            math.isfinite(level)
                            for level in (active_stop, active_target)
                        )
                        or not levels_coherent
                    ):
                        trace_status = ExecutionTraceStatus.UNDETERMINED.value
                    elif not lower_level < ex_open < upper_level:
                        trace_status = (
                            ExecutionTraceStatus.OPENING_LEVEL_REVIEW.value
                            if bar_ts > active_position.entry_timestamp
                            else ExecutionTraceStatus.UNDETERMINED.value
                        )
                    elif ex_low <= lower_level and ex_high >= upper_level:
                        trace_status = ExecutionTraceStatus.INTRABAR_SL_FIRST.value
                    else:
                        trace_status = ExecutionTraceStatus.NO_IDENTIFIED_CONFLICT.value

                    notional_exit = active_position.size_units * exit_price
                    fee_exit = notional_exit * self.config.taker_fee_pct

                    if not is_short_pos:
                        gross_pnl = active_position.size_units * (
                            exit_price - active_position.entry_price
                        )
                    else:
                        gross_pnl = active_position.size_units * (
                            active_position.entry_price - exit_price
                        )

                    funding_fee_total = active_position.funding_fees_accumulated
                    net_pnl = (
                        gross_pnl
                        - active_position.fee_entry
                        - fee_exit
                        - funding_fee_total
                    )
                    if not all(
                        math.isfinite(value)
                        for value in (notional_exit, fee_exit, net_pnl)
                    ):
                        raise BacktestValidationError("Liquidación SPOT no finita.")

                    # LONG: sale proceeds less exit fee. Entry fee was paid inside
                    # the original allocation, so it must not be charged twice.
                    # SHORT (MARGIN_1X): the reserved margin (units x entry) is
                    # released plus the PnL; a loss beyond it would need a
                    # liquidation model that is not implemented.
                    if not is_short_pos:
                        cash_back = notional_exit - fee_exit
                    else:
                        cash_back = (
                            active_position.size_units * active_position.entry_price
                            + gross_pnl
                            - fee_exit
                        )
                        if cash_back < 0:
                            raise BacktestValidationError(
                                "Pérdida SHORT supera el margen 1x reservado: "
                                "liquidación no modelada."
                            )
                    current_cash += cash_back
                    realized_net_pnl += net_pnl
                    if current_cash < 0 or not math.isclose(
                        current_cash,
                        self.config.initial_capital + realized_net_pnl,
                        rel_tol=1e-10,
                        abs_tol=1e-8,
                    ):
                        raise ArithmeticError("Caja SPOT y PnL realizado no concilian.")

                    # Both R values use the immutable, effective risk at entry.
                    initial_risk_amount = active_position.initial_risk_amount
                    if (
                        initial_risk_amount is None
                        or not math.isfinite(initial_risk_amount)
                        or initial_risk_amount <= 0
                    ):
                        raise BacktestValidationError(
                            "Riesgo inicial de posición no disponible o inválido."
                        )
                    r_multiple = gross_pnl / initial_risk_amount
                    net_r_multiple = net_pnl / initial_risk_amount
                    if not all(
                        math.isfinite(value) for value in (r_multiple, net_r_multiple)
                    ):
                        raise BacktestValidationError("R de operación no finito.")

                    net_return_pct = (
                        (net_pnl / active_position.notional_entry * 100.0)
                        if active_position.notional_entry > 0
                        else 0.0
                    )

                    if not is_short_pos:
                        # Excursions are non-negative by definition (slippage can put the
                        # fill outside the bar range); same floor as the D1B3 exact fields.
                        mfe_pct = max(
                            0.0,
                            (
                                (
                                    (
                                        active_position.highest_price
                                        - active_position.entry_price
                                    )
                                    / active_position.entry_price
                                    * 100.0
                                )
                                if active_position.entry_price > 0
                                else 0.0
                            ),
                        )
                        # Excursions are non-negative by definition (slippage can put the
                        # fill outside the bar range); same floor as the D1B3 exact fields.
                        mae_pct = max(
                            0.0,
                            (
                                (
                                    (
                                        active_position.entry_price
                                        - active_position.lowest_price
                                    )
                                    / active_position.entry_price
                                    * 100.0
                                )
                                if active_position.entry_price > 0
                                else 0.0
                            ),
                        )

                    else:
                        # Excursions are non-negative by definition (slippage can put the
                        # fill outside the bar range); same floor as the D1B3 exact fields.
                        mfe_pct = max(
                            0.0,
                            (
                                (
                                    (
                                        active_position.entry_price
                                        - active_position.lowest_price
                                    )
                                    / active_position.entry_price
                                    * 100.0
                                )
                                if active_position.entry_price > 0
                                else 0.0
                            ),
                        )
                        # Excursions are non-negative by definition (slippage can put the
                        # fill outside the bar range); same floor as the D1B3 exact fields.
                        mae_pct = max(
                            0.0,
                            (
                                (
                                    (
                                        active_position.highest_price
                                        - active_position.entry_price
                                    )
                                    / active_position.entry_price
                                    * 100.0
                                )
                                if active_position.entry_price > 0
                                else 0.0
                            ),
                        )

                    excursion_evidence = self._excursion_evidence(
                        active_position,
                        ex_open,
                        ex_high,
                        ex_low,
                        ex_close,
                        opening_exit=opening_exit,
                        intrabar_exit=(
                            exit_reason != TradeExitReason.TIME_HORIZON.value
                            and not opening_exit
                        ),
                        is_short=is_short_pos,
                    )

                    trade_result = TradeResult(
                        trade_id=f"trade-{len(closed_trades) + 1}",
                        symbol=active_position.signal.symbol,
                        timeframe=active_position.signal.timeframe,
                        direction=active_position.side,
                        signal_timestamp=active_position.signal.candle_timestamp,
                        entry_timestamp=active_position.entry_timestamp,
                        exit_timestamp=bar_ts,
                        entry_price=active_position.entry_price,
                        exit_price=exit_price,
                        size_units=active_position.size_units,
                        notional_entry=active_position.notional_entry,
                        notional_exit=notional_exit,
                        gross_pnl=gross_pnl,
                        fee_entry=active_position.fee_entry,
                        fee_exit=fee_exit,
                        net_pnl=net_pnl,
                        net_return_pct=net_return_pct,
                        r_multiple=r_multiple,
                        bars_held=active_position.bars_held,
                        exit_reason=exit_reason,
                        mfe_pct=mfe_pct,
                        mae_pct=mae_pct,
                        is_win=net_pnl > 0,
                        side=active_position.side,
                        funding_fees=funding_fee_total,
                        tp_price=active_position.tp_price,
                        sl_price=active_position.sl_price,
                        initial_stop_price=active_position.initial_stop_price,
                        initial_risk_per_unit=active_position.initial_risk_per_unit,
                        initial_risk_amount=initial_risk_amount,
                        net_r_multiple=net_r_multiple,
                        execution_trace_status=trace_status,
                        execution_policy_version=(
                            ExecutionPolicyVersion.MARGIN_1X_C1.value
                            if is_margin
                            else ExecutionPolicyVersion.SPOT_LONG_C1.value
                        ),
                        excursion_policy_version=EXCURSION_POLICY_VERSION,
                        atr_entry=active_position.signal.atr,
                        **excursion_evidence,
                    )
                    closed_trades.append(trade_result)
                    active_position = None

                if active_position is not None:
                    if self._coherent_ohlc(ex_open, ex_high, ex_low, ex_close):
                        active_position.update_observed_excursions(ex_high, ex_low)
                    else:
                        active_position.excursion_data_valid = False

                # A surviving position may move to break-even at Close(T), based on
                # this completed candle; the new stop can only execute from T+1.
                if active_position is not None and self.config.enable_trailing_stop:
                    initial_risk = active_position.initial_risk_per_unit
                    if initial_risk is None:
                        raise BacktestValidationError(
                            "Riesgo inicial de posición no disponible."
                        )
                    if not is_short_pos:
                        if ex_high >= active_position.entry_price + (
                            self.config.trailing_stop_activation_r * initial_risk
                        ):
                            active_position.sl_price = max(
                                active_position.sl_price, active_position.entry_price
                            )
                    else:
                        if ex_low <= active_position.entry_price - (
                            self.config.trailing_stop_activation_r * initial_risk
                        ):
                            active_position.sl_price = min(
                                active_position.sl_price, active_position.entry_price
                            )

            # -----------------------------------------------------------------
            # 3. Record Mark-to-Market Equity Point
            # -----------------------------------------------------------------
            unrealized_equity = 0.0
            if active_position is not None:
                # Marked at the exit-side price, without assuming a sale. SHORT:
                # reserved margin (units x entry) plus open PnL units x (entry - ask).
                if active_position.side == PositionSide.SHORT.value:
                    unrealized_equity = active_position.size_units * (
                        2.0 * active_position.entry_price - (bar_close + half_spread)
                    )
                else:
                    unrealized_equity = active_position.size_units * (
                        bar_close - half_spread
                    )

            bar_equity = current_cash + unrealized_equity
            if not math.isfinite(bar_equity) or not math.isfinite(current_cash):
                raise BacktestValidationError("Caja o equity SPOT no finita.")
            raw_equity_curve.append(
                {
                    "timestamp": bar_ts,
                    "equity": bar_equity,
                    "cash": current_cash,
                }
            )

            # -----------------------------------------------------------------
            # 4. Check for New Signal at Close(T) (Candidate for Entry on T+1)
            # -----------------------------------------------------------------
            if bar_ts in signals_map:
                sig = signals_map[bar_ts]
                if self._passes_signal_filters(sig):
                    if active_position is None:
                        pending_signal = sig

        # Build equity curve with accurate running drawdown percentages
        equity_values = [p["equity"] for p in raw_equity_curve]
        dd_series, _, _, _ = BacktestMetricsCalculator.calculate_drawdown_series(
            equity_values, initial_equity=self.config.initial_capital
        )

        equity_curve = [
            EquityPoint(
                timestamp=raw_equity_curve[idx]["timestamp"],
                equity=raw_equity_curve[idx]["equity"],
                cash=raw_equity_curve[idx]["cash"],
                drawdown_pct=dd_series[idx],
            )
            for idx in range(len(raw_equity_curve))
        ]

        return closed_trades, equity_curve

    def _passes_signal_filters(self, signal: SignalEvent) -> bool:
        """Applies configured strategy filters to determine signal viability."""
        sig_dir = signal.direction.upper()
        cfg_dir = self.config.direction.upper()

        if cfg_dir != "BOTH":
            is_short_sig = ("SHORT" in sig_dir) or ("SELL" in sig_dir)
            is_short_cfg = ("SHORT" in cfg_dir) or ("SELL" in cfg_dir)
            if is_short_sig != is_short_cfg:
                return False

        if signal.quant_score < self.config.min_quant_score:
            return False
        if self.config.require_favorable_decision:
            decision_str = str(signal.decision).upper()
            is_favorable = (
                ("FAVORABLE" in decision_str)
                or ("CONDICIÓN FAVORABLE" in decision_str)
                or ("CONDICION FAVORABLE" in decision_str)
            )
            if not is_favorable:
                return False
        return True
