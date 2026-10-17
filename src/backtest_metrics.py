from __future__ import annotations

import math
from typing import Any

import pandas as pd

from .backtest_models import BacktestValidationError, EquityPoint, TradeResult

CRYPTO_24_7_PERIODS: dict[str, int] = {
    "1m": 525_600, "5m": 105_120, "15m": 35_040,
    "1h": 8_760, "4h": 2_190, "1d": 365,
}

# Numeric comparisons of stored quote-currency values and dimensionless R.
# These tolerances check internal arithmetic, not historical authenticity.
R_VERIFY_REL_TOL = 1e-9
R_VERIFY_ABS_TOL = 1e-10


class BacktestMetricsCalculator:
    """Pure, deterministic calculator for quantitative trade performance, risk,

    drawdown dynamics, and trade excursion profiles (MFE/MAE).
    """

    @staticmethod
    def _verified_spot_long_r(trade: TradeResult) -> tuple[float, float] | None:
        """Return gross/net R only for coherent SPOT LONG 1x trade records.

        The runner validates the instrument configuration. A trade alone cannot
        authenticate its external origin, but its direction and cash arithmetic
        can be checked without guessing an absent initial stop or risk.
        """
        if trade.direction != "LONG" or trade.side != "LONG":
            return None
        fields = (
            trade.entry_price, trade.exit_price, trade.size_units,
            trade.initial_stop_price, trade.initial_risk_amount,
            trade.gross_pnl, trade.net_pnl, trade.r_multiple, trade.net_r_multiple,
            trade.fee_entry, trade.fee_exit, trade.funding_fees,
            trade.notional_entry, trade.notional_exit,
        )
        try:
            if any(value is None or not math.isfinite(value) for value in fields):
                return None
        except (TypeError, ValueError):
            return None
        entry = trade.entry_price
        stop = trade.initial_stop_price
        units = trade.size_units
        risk = trade.initial_risk_amount
        if (entry <= 0 or trade.exit_price <= 0 or units <= 0 or stop <= 0
                or stop >= entry or risk <= 0 or trade.fee_entry < 0
                or trade.fee_exit < 0 or trade.funding_fees != 0):
            return None
        risk_per_unit = entry - stop
        def close(actual: float, expected: float) -> bool:
            return math.isclose(
                actual, expected, rel_tol=R_VERIFY_REL_TOL, abs_tol=R_VERIFY_ABS_TOL
            )
        if not close(risk, units * risk_per_unit):
            return None
        if trade.initial_risk_per_unit is not None:
            try:
                if not math.isfinite(trade.initial_risk_per_unit) or not close(
                    trade.initial_risk_per_unit, risk_per_unit
                ):
                    return None
            except (TypeError, ValueError):
                return None
        if not all((
            close(trade.notional_entry, units * entry + trade.fee_entry),
            close(trade.notional_exit, units * trade.exit_price),
            close(trade.gross_pnl, units * (trade.exit_price - entry)),
            close(trade.net_pnl, trade.gross_pnl - trade.fee_entry - trade.fee_exit),
        )):
            return None
        gross_r = trade.gross_pnl / risk
        net_r = trade.net_pnl / risk
        if not all(map(math.isfinite, (gross_r, net_r))):
            return None
        if not close(trade.r_multiple, gross_r) or not close(trade.net_r_multiple, net_r):
            return None
        return gross_r, net_r

    @classmethod
    def _verified_r_summary(cls, trades: list[TradeResult]) -> dict[str, Any]:
        """Equal-weight mean R per valid trade, never a capital-weighted return."""
        total = len(trades)
        verified = [pair for trade in trades if (pair := cls._verified_spot_long_r(trade)) is not None]
        count = len(verified)
        if total == 0:
            status, reason = "NO_TRADES", "No se ejecutaron operaciones."
        elif count == 0:
            status, reason = "NONE_VERIFIED", "Ninguna operación tiene riesgo inicial verificable."
        elif count < total:
            status = "PARTIAL"
            reason = f"Promedio solo del subconjunto verificable ({count} de {total} operaciones)."
        else:
            status, reason = "COMPLETE", None
        return {
            "gross_expectancy_r": sum(pair[0] for pair in verified) / count if count else None,
            "net_expectancy_r": sum(pair[1] for pair in verified) / count if count else None,
            "r_verified_trades": count,
            "r_excluded_trades": total - count,
            "r_coverage_status": status,
            "r_unavailable_reason": reason,
        }

    @staticmethod
    def calculate_drawdown_series(
        equity_values: list[float], initial_equity: float | None = None
    ) -> tuple[list[float], float, float, int]:
        """Return per-bar DD %, maximum DD % and amount, and underwater duration.

        Backtests pass initial_equity explicitly. For legacy callers without it,
        the first observation remains the reference peak; an empty legacy series
        returns zero *observed* drawdown, not evidence of a loss-free period.
        Callers can distinguish no data by the empty series. No synthetic equity
        point is inserted.
        """
        if initial_equity is not None:
            try:
                valid_initial = math.isfinite(initial_equity) and initial_equity > 0
            except (TypeError, ValueError):
                valid_initial = False
            if not valid_initial:
                raise BacktestValidationError("El capital inicial debe ser positivo y finito.")
        for eq in equity_values:
            try:
                valid_equity = math.isfinite(eq) and eq >= 0
            except (TypeError, ValueError):
                valid_equity = False
            if not valid_equity:
                raise BacktestValidationError("La equity debe ser no negativa y finita.")
        if not equity_values:
            return [], 0.0, 0.0, 0

        peak = initial_equity if initial_equity is not None else equity_values[0]
        if peak <= 0:
            raise BacktestValidationError(
                "Se requiere capital inicial positivo si la primera equity es cero."
            )
        dd_pct_series: list[float] = []
        max_dd_pct = 0.0
        max_dd_usd = 0.0

        current_duration = 0
        max_duration = 0

        for eq in equity_values:
            if eq >= peak:
                peak = eq
                current_duration = 0
            else:
                current_duration += 1
                if current_duration > max_duration:
                    max_duration = current_duration

            dd_usd = peak - eq
            dd_pct = dd_usd / peak * 100.0

            dd_pct_series.append(dd_pct)

            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
            if dd_usd > max_dd_usd:
                max_dd_usd = dd_usd

        return dd_pct_series, max_dd_pct, max_dd_usd, max_duration

    @classmethod
    def calculate_metrics(
        cls,
        trades: list[TradeResult],
        equity_curve: list[EquityPoint],
        initial_capital: float = 10_000.0,
        periods_per_year: int | None = None,
        expected_interval: pd.Timedelta | None = None,
        sharpe_unavailable_reason: str | None = None,
    ) -> dict[str, Any]:
        """Calculates comprehensive performance and risk metrics across completed trades."""
        total_trades = len(trades)
        verified_r = cls._verified_r_summary(trades)

        equity_values = [point.equity for point in equity_curve]
        _, max_dd_pct, max_dd_usd, max_dd_duration = cls.calculate_drawdown_series(
            equity_values, initial_equity=initial_capital
        )

        if total_trades == 0:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "expectancy_r": 0.0,
                **verified_r,
                "payoff_ratio": 0.0,
                "max_drawdown_pct": round(max_dd_pct, 2),
                "max_drawdown_usd": round(max_dd_usd, 2),
                "max_drawdown_duration_bars": max_dd_duration,
                "avg_mfe_pct": 0.0,
                "avg_mae_pct": 0.0,
                "avg_bars_held": 0.0,
                "total_gross_pnl": 0.0,
                "total_fees_paid": 0.0,
                "total_net_pnl": 0.0,
                "return_on_capital_pct": 0.0,
                "sharpe_ratio": None,
                "sharpe_unavailable_reason": sharpe_unavailable_reason or "No hay operaciones suficientes.",
                "calmar_ratio": None,
            }

        winning_trades = [t for t in trades if t.net_pnl > 0]
        losing_trades = [t for t in trades if t.net_pnl < 0]
        breakeven_trades = [t for t in trades if t.net_pnl == 0]

        n_wins = len(winning_trades)
        n_losses = len(losing_trades)

        win_rate = (n_wins / total_trades) * 100.0

        # PnL sums
        gross_wins = sum(t.net_pnl for t in winning_trades)
        gross_losses = abs(sum(t.net_pnl for t in losing_trades))

        if gross_losses > 0:
            profit_factor = gross_wins / gross_losses
        elif gross_wins > 0:
            profit_factor = math.inf
        else:
            profit_factor = 0.0

        # Averages in USD
        avg_win_usd = (gross_wins / n_wins) if n_wins > 0 else 0.0
        avg_loss_usd = (gross_losses / n_losses) if n_losses > 0 else 0.0

        payoff_ratio = (avg_win_usd / avg_loss_usd) if avg_loss_usd > 0 else (math.inf if avg_win_usd > 0 else 0.0)

        # Expectancy USD: (WinRate * AvgWin) - (LossRate * AvgLoss)
        win_prob = n_wins / total_trades
        loss_prob = n_losses / total_trades
        expectancy_usd = (win_prob * avg_win_usd) - (loss_prob * avg_loss_usd)

        # Legacy hybrid R: grouped by net PnL, but using gross r_multiple.
        # Preserve its historical numeric contract; it is not a verified metric.
        r_wins = [t.r_multiple for t in winning_trades]
        r_losses = [abs(t.r_multiple) for t in losing_trades]
        avg_r_win = (sum(r_wins) / len(r_wins)) if r_wins else 0.0
        avg_r_loss = (sum(r_losses) / len(r_losses)) if r_losses else 0.0
        expectancy_r = (win_prob * avg_r_win) - (loss_prob * avg_r_loss)

        # MFE / MAE / Duration
        avg_mfe = sum(t.mfe_pct for t in trades) / total_trades
        avg_mae = sum(t.mae_pct for t in trades) / total_trades
        avg_bars = sum(t.bars_held for t in trades) / total_trades

        # Totals
        total_gross_pnl = sum(t.gross_pnl for t in trades)
        total_funding_fees = sum(t.funding_fees for t in trades)
        total_fees = sum(t.fee_entry + t.fee_exit + t.funding_fees for t in trades)
        total_net_pnl = sum(t.net_pnl for t in trades)
        return_on_capital = (total_net_pnl / initial_capital * 100.0) if initial_capital > 0 else 0.0

        # Sharpe & Calmar Ratios
        sharpe_ratio: float | None = None
        sharpe_reason = sharpe_unavailable_reason
        calmar_ratio: float | None = None

        if (periods_per_year is None or periods_per_year <= 0
                or expected_interval is None or expected_interval <= pd.Timedelta(0)):
            sharpe_reason = sharpe_reason or "Procedencia, calendario o intervalo no acreditado."
        elif len(equity_curve) < 4:
            sharpe_reason = "Se requieren al menos tres rendimientos periódicos."
        elif any(not math.isfinite(value) or value <= 0 for value in equity_values):
            sharpe_reason = "Equity no positiva o no finita para calcular rendimientos."
        else:
            timestamps = pd.to_datetime([point.timestamp for point in equity_curve], utc=True, errors="coerce")
            steps = timestamps.to_series().diff().iloc[1:]
            if timestamps.isna().any() or not (steps == expected_interval).all():
                sharpe_reason = "Timestamps duplicados, desordenados o frecuencia irregular."
            else:
                returns = pd.Series(equity_values).pct_change().iloc[1:]
                std = float(returns.std(ddof=1))
                if not math.isfinite(std) or std <= 1e-12:
                    sharpe_reason = "Variabilidad de rendimientos insuficiente."
                else:
                    # 0% risk-free rate, sample standard deviation, regular bars.
                    sharpe_ratio = float((returns.mean() / std) * math.sqrt(periods_per_year))
                    if not math.isfinite(sharpe_ratio):
                        sharpe_ratio = None
                        sharpe_reason = "Resultado Sharpe no finito."
                    else:
                        sharpe_reason = None

        if max_dd_pct > 0:
            calmar_ratio = float(return_on_capital / max_dd_pct)

        return {
            "total_trades": total_trades,
            "winning_trades": n_wins,
            "losing_trades": n_losses,
            "breakeven_trades": len(breakeven_trades),
            "win_rate_pct": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2) if profit_factor != math.inf else math.inf,
            "expectancy": round(expectancy_usd, 2),
            "expectancy_r": round(expectancy_r, 2),
            **verified_r,
            "payoff_ratio": round(payoff_ratio, 2) if payoff_ratio != math.inf else math.inf,
            "max_drawdown_pct": round(max_dd_pct, 2),
            "max_drawdown_usd": round(max_dd_usd, 2),
            "max_drawdown_duration_bars": max_dd_duration,
            "avg_mfe_pct": round(avg_mfe, 2),
            "avg_mae_pct": round(avg_mae, 2),
            "avg_bars_held": round(avg_bars, 2),
            "total_gross_pnl": round(total_gross_pnl, 2),
            "total_fees_paid": round(total_fees, 2),
            "total_funding_fees": round(total_funding_fees, 2),
            "total_net_pnl": round(total_net_pnl, 2),
            "return_on_capital_pct": round(return_on_capital, 2),
            "sharpe_ratio": round(sharpe_ratio, 2) if sharpe_ratio is not None else None,
            "sharpe_unavailable_reason": sharpe_reason,
            "calmar_ratio": round(calmar_ratio, 2) if calmar_ratio is not None else None,
        }
