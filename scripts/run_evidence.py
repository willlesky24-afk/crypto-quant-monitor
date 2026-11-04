"""Run the v3.0 evidence protocol on the downloaded dataset.

Usage:
    python scripts/run_evidence.py validation
    python scripts/run_evidence.py test        # only once; refuses if a report exists

Each series is backtested causally over its whole history with the system's
own configuration (crypto: SPOT LONG with the default fees/slippage; forex and
metals: MARGIN_1X BOTH, no commission, real per-candle spread). Trades are
assigned to periods by entry time; the selected period is summarised against
the pre-registered success criteria. Simplification (declared): Monte Carlo
treats all trades of the period as one sequence of returns on committed capital.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from src.backtest_models import BacktestConfig  # noqa: E402
from src.backtest_runner import BacktestRunner  # noqa: E402
from src.evidence_evaluation import (  # noqa: E402
    SuccessCriteria,
    assign_period,
    bootstrap_mean_ci,
    evaluate_criteria,
    monte_carlo_drawdown,
    summarize_trades,
)
from src.parquet_store import ParquetStore  # noqa: E402

EVIDENCE_DIR = Path("data/evidence")
REPORT_DIR = Path("reports/evidence")


def _series() -> list[tuple[str, str]]:
    out = []
    for sym_dir in sorted(p for p in EVIDENCE_DIR.iterdir() if p.is_dir()):
        for iv_dir in sorted(p for p in sym_dir.iterdir() if p.is_dir()):
            out.append((sym_dir.name, iv_dir.name))
    return out


def _config(key: str) -> BacktestConfig:
    if key.endswith("_OANDA"):
        return BacktestConfig(
            market_type="MARGIN_1X",
            direction="BOTH",
            taker_fee_pct=0.0,
            slippage_pct=0.0,
        )
    return BacktestConfig()


def _stats(trades: list) -> dict:
    s = summarize_trades(trades)
    r = [
        t.net_r_multiple
        for t in trades
        if t.net_r_multiple is not None and np.isfinite(t.net_r_multiple)
    ]
    rets = [t.net_return_pct for t in trades]
    s["expectancy_ci_low"], s["expectancy_ci_high"] = (
        bootstrap_mean_ci(r) if r else (None, None)
    )
    s["mc_drawdown_p95_pct"] = monte_carlo_drawdown(rets) if rets else None
    return s


def main(period: str) -> int:
    if period not in ("validation", "test", "train"):
        raise SystemExit("periodo debe ser train, validation o test")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORT_DIR / f"evidence_{period}.json"
    if period == "test" and out_path.exists():
        raise SystemExit(
            "El periodo de prueba ya se ejecuto (protocolo: una sola vez). "
            f"Resultado existente: {out_path}"
        )
    store = ParquetStore(EVIDENCE_DIR)
    per_series = {}
    all_trades = []
    for key, interval in _series():
        t0 = time.time()
        df = store.load_dataset(key, interval)
        symbol = key.rsplit("_", 1)[0]
        symbol = symbol if key.endswith("_BINANCE") else f"{symbol}=X"
        report = BacktestRunner(config=_config(key)).run_backtest(
            symbol=symbol, interval=interval, df=df, predictive_mode=True
        )
        trades = [
            t for t in report.trades if assign_period(t.entry_timestamp) == period
        ]
        all_trades.extend(trades)
        s = summarize_trades(trades)
        s["sides"] = {
            side: sum(t.side == side for t in trades) for side in ("LONG", "SHORT")
        }
        per_series[f"{key}:{interval}"] = s
        print(
            f"{key} {interval}: {s['trades']} trades, PF {s['profit_factor']}, "
            f"net {s['net_pnl']:.2f} ({time.time() - t0:.0f}s)",
            flush=True,
        )
    agg = _stats(all_trades)
    active = [v for v in per_series.values() if v["trades"] > 0]
    agg["positive_instruments_pct"] = (
        100.0 * sum(v["net_pnl"] > 0 for v in active) / len(active) if active else None
    )
    criteria = SuccessCriteria()
    passed, reasons = evaluate_criteria(agg, criteria)
    result = {
        "period": period,
        "criteria": criteria.to_dict(),
        "aggregate": agg,
        "passed": passed,
        "failed_reasons": reasons,
        "per_series": per_series,
    }
    out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {k: result[k] for k in ("aggregate", "passed", "failed_reasons")},
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "validation"))
