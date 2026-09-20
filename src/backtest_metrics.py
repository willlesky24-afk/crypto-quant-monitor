from __future__ import annotations

import math
from typing import Any

import pandas as pd

from .backtest_models import EquityPoint, TradeResult


class BacktestMetricsCalculator:
    """Pure, deterministic calculator for quantitative trade performance, risk,

    drawdown dynamics, and trade excursion profiles (MFE/MAE).
    """

    @staticmethod
    def calculate_drawdown_series(equity_values: list[float]) -> tuple[list[float], float, float, int]:
        """Calculates running drawdown percentage, max drawdown %, max drawdown $ USD,

        and max drawdown duration in steps/bars.
        """
        if not equity_values:
            return [], 0.0, 0.0, 0

        peak = equity_values[0]
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
            dd_pct = (dd_usd / peak * 100.0) if peak > 0 else 0.0

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
        periods_per_year: int = 8760,  # 8760 hours in 1 year for 1h candles
    ) -> dict[str, Any]:
        """Calculates comprehensive performance and risk metrics across completed trades."""
        total_trades = len(trades)

        if total_trades == 0:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "expectancy_r": 0.0,
                "payoff_ratio": 0.0,
                "max_drawdown_pct": 0.0,
                "max_drawdown_usd": 0.0,
                "max_drawdown_duration_bars": 0,
                "avg_mfe_pct": 0.0,
                "avg_mae_pct": 0.0,
                "avg_bars_held": 0.0,
                "total_gross_pnl": 0.0,
                "total_fees_paid": 0.0,
                "total_net_pnl": 0.0,
                "return_on_capital_pct": 0.0,
                "sharpe_ratio": None,
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

        # Expectancy R-multiple
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

        # Drawdown calculations from equity curve
        if equity_curve:
            equity_values = [p.equity for p in equity_curve]
            _, max_dd_pct, max_dd_usd, max_dd_duration = cls.calculate_drawdown_series(equity_values)
        else:
            max_dd_pct, max_dd_usd, max_dd_duration = 0.0, 0.0, 0

        # Sharpe & Calmar Ratios
        sharpe_ratio: float | None = None
        calmar_ratio: float | None = None

        if len(equity_curve) > 2:
            eq_series = pd.Series([p.equity for p in equity_curve])
            returns = eq_series.pct_change().dropna()
            std = returns.std()
            if std > 1e-12:
                sharpe_ratio = float((returns.mean() / std) * math.sqrt(periods_per_year))

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
            "calmar_ratio": round(calmar_ratio, 2) if calmar_ratio is not None else None,
        }
