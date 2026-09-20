from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from .backtest_metrics import BacktestMetricsCalculator
from .backtest_models import (
    BacktestConfig,
    EquityPoint,
    Position,
    SignalEvent,
    TradeExitReason,
    TradeResult,
)

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Chronological event-driven simulation engine for trading strategies.

    Executes entries at Open(T+1) strictly after signal confirmation at Close(T),
    models taker/maker transaction fees and execution slippage, tracks MFE/MAE excursions,
    and applies conservative worst-case intrabar stop resolution.
    """

    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()

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
        if df.empty:
            return [], []

        required_cols = {"timestamp", "open", "high", "low", "close"}
        if not required_cols.issubset(set(df.columns)):
            raise ValueError(f"El DataFrame debe contener las columnas: {required_cols}")

        candles = df.copy()
        candles["timestamp"] = pd.to_datetime(candles["timestamp"], utc=True)
        candles = candles.sort_values("timestamp").reset_index(drop=True)

        # Build lookup map of valid signals by timestamp
        signals_map: dict[pd.Timestamp, SignalEvent] = {}
        if signals:
            for s in signals:
                signals_map[pd.to_datetime(s.candle_timestamp, utc=True)] = s

        current_cash = float(self.config.initial_capital)
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
                entry_price = bar_open * (1.0 + slip)

                # Position sizing based on available cash
                allocated_cash = current_cash * max(0.0, min(1.0, self.config.position_size_pct))
                if allocated_cash > 0 and entry_price > 0:
                    fee_entry = allocated_cash * self.config.taker_fee_pct
                    actual_capital_invested = allocated_cash - fee_entry
                    size_units = actual_capital_invested / entry_price

                    # Multipliers based on signal ATR
                    atr_val = max(pending_signal.atr, entry_price * 0.005)  # Safe fallback if ATR is 0
                    tp_price = entry_price + (self.config.tp_atr_multiple * atr_val)
                    sl_price = entry_price - (self.config.sl_atr_multiple * atr_val)

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

                # Optional Trailing Stop / Break-Even adjustment
                if self.config.enable_trailing_stop:
                    initial_risk = active_position.entry_price - (
                        active_position.entry_price - (self.config.sl_atr_multiple * max(active_position.signal.atr, 1e-6))
                    )
                    if bar_high >= active_position.entry_price + (self.config.trailing_stop_activation_r * initial_risk):
                        active_position.sl_price = max(active_position.sl_price, active_position.entry_price)

                exit_triggered = False
                exit_price = bar_close
                exit_reason = TradeExitReason.TIME_HORIZON.value

                # Case A: Intrabar conflict (Both SL and TP touched) -> Worst-case: SL executed first
                if bar_low <= active_position.sl_price and bar_high >= active_position.tp_price:
                    exit_triggered = True
                    exit_price = active_position.sl_price * (1.0 - self.config.slippage_pct)
                    exit_reason = TradeExitReason.STOP_LOSS.value

                # Case B: Stop Loss touched
                elif bar_low <= active_position.sl_price:
                    exit_triggered = True
                    # If opened below SL (gap down), execute at open with slippage
                    effective_sl = min(bar_open, active_position.sl_price)
                    exit_price = effective_sl * (1.0 - self.config.slippage_pct)
                    exit_reason = TradeExitReason.STOP_LOSS.value

                # Case C: Take Profit touched
                elif bar_high >= active_position.tp_price:
                    exit_triggered = True
                    effective_tp = max(bar_open, active_position.tp_price)
                    exit_price = effective_tp * (1.0 - self.config.slippage_pct)
                    exit_reason = TradeExitReason.TAKE_PROFIT.value

                # Case D: Time Horizon expired (Max holding bars reached or end of series)
                elif active_position.bars_held >= self.config.max_holding_bars or i == total_bars - 1:
                    exit_triggered = True
                    exit_price = bar_close * (1.0 - self.config.slippage_pct)
                    exit_reason = TradeExitReason.TIME_HORIZON.value

                if exit_triggered:
                    notional_exit = active_position.size_units * exit_price
                    fee_exit = notional_exit * self.config.taker_fee_pct
                    gross_pnl = notional_exit - active_position.notional_entry
                    net_pnl = gross_pnl - active_position.fee_entry - fee_exit

                    current_cash += notional_exit - fee_exit

                    # Performance ratios
                    initial_risk = active_position.entry_price - (
                        active_position.entry_price - (self.config.sl_atr_multiple * max(active_position.signal.atr, 1e-6))
                    )
                    r_multiple = ((exit_price - active_position.entry_price) / initial_risk) if initial_risk > 0 else 0.0
                    net_return_pct = (net_pnl / active_position.notional_entry * 100.0) if active_position.notional_entry > 0 else 0.0

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

                    trade_result = TradeResult(
                        trade_id=f"trade-{len(closed_trades) + 1}",
                        symbol=active_position.signal.symbol,
                        timeframe=active_position.signal.timeframe,
                        direction=self.config.direction,
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
                    )
                    closed_trades.append(trade_result)
                    active_position = None

            # -----------------------------------------------------------------
            # 3. Record Mark-to-Market Equity Point
            # -----------------------------------------------------------------
            unrealized_notional = 0.0
            if active_position is not None:
                unrealized_notional = active_position.size_units * bar_close
                estimated_exit_fee = unrealized_notional * self.config.taker_fee_pct
                unrealized_notional -= estimated_exit_fee

            bar_equity = current_cash + unrealized_notional
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
        dd_series, _, _, _ = BacktestMetricsCalculator.calculate_drawdown_series(equity_values)

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
        if signal.direction.upper() != self.config.direction.upper():
            return False
        if signal.quant_score < self.config.min_quant_score:
            return False
        if self.config.require_favorable_decision and signal.decision != "FAVORABLE":
            return False
        return True
