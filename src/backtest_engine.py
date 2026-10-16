from __future__ import annotations

import logging
import math
from typing import Any

import pandas as pd

from .backtest_metrics import BacktestMetricsCalculator
from .backtest_models import (
    BacktestConfig,
    BacktestValidationError,
    EquityPoint,
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

    def validate_config(self) -> None:
        """Only the SPOT LONG 1x cash ledger is supported in this phase."""
        cfg = self.config
        market = str(cfg.market_type).strip().upper()
        direction = str(cfg.direction).strip().upper()
        if market != MarketType.SPOT.value:
            raise BacktestValidationError(
                f"market_type={cfg.market_type!r} no disponible: PERP y otros instrumentos "
                "requieren un modelo contable validado. Disponible: SPOT LONG 1x."
            )
        if direction != PositionSide.LONG.value:
            raise BacktestValidationError(
                f"direction={cfg.direction!r} no disponible para SPOT: "
                "SHORT y BOTH requieren otro modelo. Disponible: SPOT LONG 1x."
            )
        if not math.isfinite(cfg.leverage) or cfg.leverage != 1.0:
            raise BacktestValidationError(
                f"leverage={cfg.leverage!r} no disponible para SPOT: "
                "no se simula apalancamiento. Disponible: SPOT LONG 1x."
            )
        for name in ("initial_capital", "position_size_pct", "taker_fee_pct", "slippage_pct"):
            value = getattr(cfg, name)
            if not math.isfinite(value):
                raise BacktestValidationError(f"{name} debe ser finito.")
        if cfg.initial_capital <= 0:
            raise BacktestValidationError("initial_capital debe ser positivo.")
        if not 0 <= cfg.position_size_pct <= 1:
            raise BacktestValidationError("position_size_pct debe estar entre 0 y 1.")
        if not 0 <= cfg.taker_fee_pct < 1:
            raise BacktestValidationError("taker_fee_pct debe estar entre 0 y 1 (exclusivo).")
        if not 0 <= cfg.slippage_pct < 1:
            raise BacktestValidationError("slippage_pct debe estar entre 0 y 1 (exclusivo).")

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
        if df.empty:
            return [], []

        required_cols = {"timestamp", "open", "high", "low", "close"}
        if not required_cols.issubset(set(df.columns)):
            raise ValueError(f"El DataFrame debe contener las columnas: {required_cols}")

        candles = df.copy()
        candles["timestamp"] = pd.to_datetime(candles["timestamp"], utc=True)
        candles = candles.sort_values("timestamp").reset_index(drop=True)
        for column in ("open", "high", "low", "close"):
            numeric = pd.to_numeric(candles[column], errors="coerce")
            if not numeric.map(math.isfinite).all() or (numeric <= 0).any():
                raise BacktestValidationError(
                    f"Datos financieros inválidos: {column} debe ser positivo y finito."
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

            # -----------------------------------------------------------------
            # 1. Process Pending Order (Entry on Open of T+1)
            # -----------------------------------------------------------------
            if active_position is None and pending_signal is not None:
                slip = self.config.slippage_pct
                sig_dir = pending_signal.direction.upper()
                if sig_dir != PositionSide.LONG.value:
                    raise BacktestValidationError(
                        f"Señal {sig_dir!r} no disponible para SPOT LONG 1x."
                    )
                is_short = ("SHORT" in sig_dir) or ("SELL" in sig_dir)
                pos_side = PositionSide.SHORT.value if is_short else PositionSide.LONG.value

                if not is_short:
                    entry_price = bar_open * (1.0 + slip)
                else:
                    entry_price = bar_open * (1.0 - slip)
                if not math.isfinite(entry_price) or entry_price <= 0:
                    raise BacktestValidationError("Precio de entrada SPOT no positivo o no finito.")

                # Position sizing based on available cash and leverage
                allocated_cash = current_cash * max(0.0, min(1.0, self.config.position_size_pct))
                lev = max(1.0, float(self.config.leverage))
                if allocated_cash > 0 and entry_price > 0:
                    if not math.isfinite(pending_signal.atr):
                        raise BacktestValidationError("ATR de señal no finito.")
                    fee_entry = (allocated_cash * lev) * self.config.taker_fee_pct
                    actual_capital_invested = (allocated_cash * lev) - fee_entry
                    size_units = actual_capital_invested / entry_price
                    if not math.isfinite(size_units) or size_units <= 0:
                        raise BacktestValidationError("Unidades SPOT no positivas o no finitas.")

                    # Multipliers based on signal ATR (custom signal multiples or config defaults)
                    atr_val = max(pending_signal.atr, entry_price * 0.005)  # Safe fallback if ATR is 0
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
                    if not all(math.isfinite(value) for value in (tp_mult, sl_mult)):
                        raise BacktestValidationError("Multiplicadores de niveles no finitos.")

                    if not is_short:
                        tp_price = entry_price + (tp_mult * atr_val)
                        sl_price = entry_price - (sl_mult * atr_val)
                    else:
                        tp_price = entry_price - (tp_mult * atr_val)
                        sl_price = entry_price + (sl_mult * atr_val)
                    if not all(math.isfinite(level) for level in (tp_price, sl_price)):
                        raise BacktestValidationError("Niveles de salida no finitos.")
                    initial_risk_per_unit = entry_price - sl_price
                    initial_risk_amount = size_units * initial_risk_per_unit
                    if (
                        not math.isfinite(sl_price)
                        or sl_price <= 0
                        or sl_price >= entry_price
                        or not math.isfinite(initial_risk_per_unit)
                        or initial_risk_per_unit <= 0
                        or not math.isfinite(initial_risk_amount)
                        or initial_risk_amount <= 0
                    ):
                        raise BacktestValidationError(
                            "Stop inicial SPOT LONG o riesgo inicial inválido."
                        )

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
                        highest_price=bar_high,
                        lowest_price=bar_low,
                    )
                    current_cash -= allocated_cash
                pending_signal = None

            # -----------------------------------------------------------------
            # 2. Process Active Position Exits & Intrabar Monitoring
            # -----------------------------------------------------------------
            if active_position is not None:
                active_position.bars_held += 1
                active_position.update_excursions(high=bar_high, low=bar_low)
                is_short_pos = active_position.side == PositionSide.SHORT.value

                # A. Apply Perpetual Funding Fees if applicable (every 8h: 00:00, 08:00, 16:00 UTC)
                is_perp = self.config.market_type.upper() == MarketType.PERP.value
                if is_perp and self.config.funding_rate_8h != 0.0:
                    if bar_ts > active_position.entry_timestamp:
                        # Check 8h settlement boundary (00:00, 08:00, 16:00 UTC)
                        if (bar_ts.hour % 8 == 0 and bar_ts.minute == 0) and (
                            active_position.last_funding_time is None or bar_ts > active_position.last_funding_time
                        ):
                            current_notional = active_position.size_units * bar_close
                            if not is_short_pos:
                                funding_fee = current_notional * self.config.funding_rate_8h
                            else:
                                funding_fee = -current_notional * self.config.funding_rate_8h
                            active_position.funding_fees_accumulated += funding_fee
                            active_position.last_funding_time = bar_ts

                # B. Optional Trailing Stop / Break-Even adjustment
                if self.config.enable_trailing_stop:
                    initial_risk = active_position.initial_risk_per_unit
                    if initial_risk is None:
                        raise BacktestValidationError("Riesgo inicial de posición no disponible.")
                    if not is_short_pos:
                        if bar_high >= active_position.entry_price + (self.config.trailing_stop_activation_r * initial_risk):
                            active_position.sl_price = max(active_position.sl_price, active_position.entry_price)
                    else:
                        if bar_low <= active_position.entry_price - (self.config.trailing_stop_activation_r * initial_risk):
                            active_position.sl_price = min(active_position.sl_price, active_position.entry_price)

                exit_triggered = False
                exit_price = bar_close
                exit_reason = TradeExitReason.TIME_HORIZON.value

                if not is_short_pos:
                    # LONG Case A: Intrabar conflict (Both SL and TP touched) -> Worst-case: SL executed first
                    if bar_low <= active_position.sl_price and bar_high >= active_position.tp_price:
                        exit_triggered = True
                        exit_price = active_position.sl_price * (1.0 - self.config.slippage_pct)
                        exit_reason = TradeExitReason.STOP_LOSS.value

                    # LONG Case B: Stop Loss touched
                    elif bar_low <= active_position.sl_price:
                        exit_triggered = True
                        effective_sl = min(bar_open, active_position.sl_price)
                        exit_price = effective_sl * (1.0 - self.config.slippage_pct)
                        exit_reason = TradeExitReason.STOP_LOSS.value

                    # LONG Case C: Take Profit touched
                    elif bar_high >= active_position.tp_price:
                        exit_triggered = True
                        effective_tp = max(bar_open, active_position.tp_price)
                        exit_price = effective_tp * (1.0 - self.config.slippage_pct)
                        exit_reason = TradeExitReason.TAKE_PROFIT.value

                    # LONG Case D: Time Horizon expired (Max holding bars reached or end of series)
                    elif active_position.bars_held >= self.config.max_holding_bars or i == total_bars - 1:
                        exit_triggered = True
                        exit_price = bar_close * (1.0 - self.config.slippage_pct)
                        exit_reason = TradeExitReason.TIME_HORIZON.value

                else:
                    # SHORT Case A: Intrabar conflict (Both SL and TP touched) -> Worst-case: SL executed first
                    if bar_high >= active_position.sl_price and bar_low <= active_position.tp_price:
                        exit_triggered = True
                        exit_price = active_position.sl_price * (1.0 + self.config.slippage_pct)
                        exit_reason = TradeExitReason.STOP_LOSS.value

                    # SHORT Case B: Stop Loss touched
                    elif bar_high >= active_position.sl_price:
                        exit_triggered = True
                        effective_sl = max(bar_open, active_position.sl_price)
                        exit_price = effective_sl * (1.0 + self.config.slippage_pct)
                        exit_reason = TradeExitReason.STOP_LOSS.value

                    # SHORT Case C: Take Profit touched
                    elif bar_low <= active_position.tp_price:
                        exit_triggered = True
                        effective_tp = min(bar_open, active_position.tp_price)
                        exit_price = effective_tp * (1.0 + self.config.slippage_pct)
                        exit_reason = TradeExitReason.TAKE_PROFIT.value

                    # SHORT Case D: Time Horizon expired (Max holding bars reached or end of series)
                    elif active_position.bars_held >= self.config.max_holding_bars or i == total_bars - 1:
                        exit_triggered = True
                        exit_price = bar_close * (1.0 + self.config.slippage_pct)
                        exit_reason = TradeExitReason.TIME_HORIZON.value

                if exit_triggered:
                    notional_exit = active_position.size_units * exit_price
                    fee_exit = notional_exit * self.config.taker_fee_pct

                    if not is_short_pos:
                        gross_pnl = active_position.size_units * (exit_price - active_position.entry_price)
                    else:
                        gross_pnl = active_position.size_units * (active_position.entry_price - exit_price)

                    funding_fee_total = active_position.funding_fees_accumulated
                    net_pnl = gross_pnl - active_position.fee_entry - fee_exit - funding_fee_total
                    if not all(math.isfinite(value) for value in (notional_exit, fee_exit, net_pnl)):
                        raise BacktestValidationError("Liquidación SPOT no finita.")

                    # SPOT: sale proceeds less exit fee. Entry fee was paid inside
                    # the original allocation, so it must not be charged twice.
                    current_cash += notional_exit - fee_exit
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
                    if initial_risk_amount is None or not math.isfinite(initial_risk_amount) or initial_risk_amount <= 0:
                        raise BacktestValidationError("Riesgo inicial de posición no disponible o inválido.")
                    r_multiple = gross_pnl / initial_risk_amount
                    net_r_multiple = net_pnl / initial_risk_amount
                    if not all(math.isfinite(value) for value in (r_multiple, net_r_multiple)):
                        raise BacktestValidationError("R de operación no finito.")

                    net_return_pct = (
                        (net_pnl / active_position.notional_entry * 100.0) if active_position.notional_entry > 0 else 0.0
                    )

                    if not is_short_pos:
                        mfe_pct = (
                            ((active_position.highest_price - active_position.entry_price) / active_position.entry_price * 100.0)
                            if active_position.entry_price > 0
                            else 0.0
                        )
                        mae_pct = (
                            ((active_position.entry_price - active_position.lowest_price) / active_position.entry_price * 100.0)
                            if active_position.entry_price > 0
                            else 0.0
                        )
                    else:
                        mfe_pct = (
                            ((active_position.entry_price - active_position.lowest_price) / active_position.entry_price * 100.0)
                            if active_position.entry_price > 0
                            else 0.0
                        )
                        mae_pct = (
                            ((active_position.highest_price - active_position.entry_price) / active_position.entry_price * 100.0)
                            if active_position.entry_price > 0
                            else 0.0
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
                    )
                    closed_trades.append(trade_result)
                    active_position = None

            # -----------------------------------------------------------------
            # 3. Record Mark-to-Market Equity Point
            # -----------------------------------------------------------------
            unrealized_equity = 0.0
            if active_position is not None:
                # Open SPOT holdings are marked to market, without assuming a sale.
                unrealized_equity = active_position.size_units * bar_close

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
