"""v3.0 screening on the training period only (4h, 2021-11-01..2023-12-31).

Bars from 2024 on are cut BEFORE any calculation, so validation and test data
cannot reach a candidate. All candidates share the engine, exit and costs.

Pre-registered reading: 11 candidates were tried, so a 99.55% bootstrap CI
(Bonferroni, 1 - 0.05/11) must lie above 0 for a candidate to count as having
signal. Below that it is at most "promising" and may be luck.

Declared limit: the exit (SL 1 ATR, TP 2 ATR, 24 bars) is the model's own, and
does not suit every method; slow methods such as momentum are normally held
longer, so a poor result here rejects the entry WITH this exit only.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from scripts.run_evidence import EVIDENCE_DIR, REPORT_DIR, _config  # noqa: E402
from src.backtest_engine import BacktestEngine  # noqa: E402
from src.evidence_evaluation import (  # noqa: E402
    PERIODS,
    bootstrap_mean_ci,
    summarize_trades,
)
from src.indicators import TechnicalIndicators  # noqa: E402
from src.parquet_store import ParquetStore  # noqa: E402
from src.signal_candidates import CANDIDATES, signals_to_events  # noqa: E402

INTERVAL = "4h"
CI_LEVEL = 1.0 - 0.05 / len(CANDIDATES)


def _group_stats(trades: list) -> dict:
    s = summarize_trades(trades)
    r = [t.net_r_multiple for t in trades if t.net_r_multiple is not None]
    s["ci_low"], s["ci_high"] = (
        bootstrap_mean_ci(r, level=CI_LEVEL) if r else (None, None)
    )
    s["long"] = sum(t.side == "LONG" for t in trades)
    s["short"] = sum(t.side == "SHORT" for t in trades)
    return s


def main() -> int:
    end = pd.Timestamp(PERIODS["train"][1], tz="UTC")
    store = ParquetStore(EVIDENCE_DIR)
    keys = sorted(p.name for p in EVIDENCE_DIR.iterdir() if p.is_dir())
    trades = {n: {"crypto": [], "forex_metals": []} for n in CANDIDATES}
    positive = {n: [] for n in CANDIDATES}
    for key in keys:
        t0 = time.time()
        raw = store.load_dataset(key, INTERVAL)
        raw = raw[pd.to_datetime(raw["timestamp"], utc=True) < end]
        df = TechnicalIndicators().calculate_all(raw.copy()).reset_index(drop=True)
        df.attrs = {}
        group = "forex_metals" if key.endswith("_OANDA") else "crypto"
        symbol = key.rsplit("_", 1)[0]
        symbol = symbol if group == "crypto" else f"{symbol}=X"
        for name, fn in CANDIDATES.items():
            events = signals_to_events(df, fn(df), symbol, INTERVAL)
            result, _ = BacktestEngine(config=_config(key)).run(df, events)
            trades[name][group].extend(result)
            positive[name].append(sum(t.net_pnl for t in result) > 0)
        print(f"{key}: {time.time() - t0:.0f}s", flush=True)
    report = {"interval": INTERVAL, "ci_level": CI_LEVEL, "candidates": {}}
    for name, groups in trades.items():
        report["candidates"][name] = {
            "all": _group_stats(groups["crypto"] + groups["forex_metals"]),
            "crypto": _group_stats(groups["crypto"]),
            "forex_metals": _group_stats(groups["forex_metals"]),
            "positive_series_pct": 100.0 * sum(positive[name]) / len(positive[name]),
        }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / "screening_train_4h.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
