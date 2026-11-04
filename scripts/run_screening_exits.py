"""v3.0 last screening round: three fixed exits on the four best entries.

Training period only, 4h; bars from 2024 on are cut before any calculation.
Declared before seeing results; this is the cut-off round approved by the
supervisor. 11 + 12 = 23 trials so far, so the CI level is 1 - 0.05/23.

Exits (project choices, not values from a publication):
- amplia_3a1: SL 2 ATR, TP 6 ATR, up to 120 bars (20 days).
- breakeven_2a1: SL 1 ATR, TP 2 ATR, 24 bars, stop to entry at +1R.
- tendencia_larga: SL 2 ATR, TP 12 ATR, 180 bars (30 days), stop to entry at +2R.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import replace
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
TOTAL_TRIALS = 23
CI_LEVEL = 1.0 - 0.05 / TOTAL_TRIALS
ENTRIES = ("trend_ema", "momentum_rsi", "volume_direction", "profile_value_area")
EXITS = {
    "amplia_3a1": {
        "sl_atr_multiple": 2.0,
        "tp_atr_multiple": 6.0,
        "max_holding_bars": 120,
    },
    "breakeven_2a1": {
        "sl_atr_multiple": 1.0,
        "tp_atr_multiple": 2.0,
        "max_holding_bars": 24,
        "enable_trailing_stop": True,
        "trailing_stop_activation_r": 1.0,
    },
    "tendencia_larga": {
        "sl_atr_multiple": 2.0,
        "tp_atr_multiple": 12.0,
        "max_holding_bars": 180,
        "enable_trailing_stop": True,
        "trailing_stop_activation_r": 2.0,
    },
}


def _stats(trades: list) -> dict:
    s = summarize_trades(trades)
    r = [t.net_r_multiple for t in trades if t.net_r_multiple is not None]
    s["ci_low"], s["ci_high"] = (
        bootstrap_mean_ci(r, level=CI_LEVEL) if r else (None, None)
    )
    return s


def main() -> int:
    end = pd.Timestamp(PERIODS["train"][1], tz="UTC")
    store = ParquetStore(EVIDENCE_DIR)
    keys = sorted(p.name for p in EVIDENCE_DIR.iterdir() if p.is_dir())
    combos = [(e, x) for e in ENTRIES for x in EXITS]
    trades = {c: {"crypto": [], "forex_metals": []} for c in combos}
    positive = {c: [] for c in combos}
    for key in keys:
        t0 = time.time()
        raw = store.load_dataset(key, INTERVAL)
        raw = raw[pd.to_datetime(raw["timestamp"], utc=True) < end]
        df = TechnicalIndicators().calculate_all(raw.copy()).reset_index(drop=True)
        df.attrs = {}
        group = "forex_metals" if key.endswith("_OANDA") else "crypto"
        symbol = key.rsplit("_", 1)[0]
        symbol = symbol if group == "crypto" else f"{symbol}=X"
        for entry in ENTRIES:
            events = signals_to_events(df, CANDIDATES[entry](df), symbol, INTERVAL)
            for name, params in EXITS.items():
                config = replace(_config(key), **params)
                result, _ = BacktestEngine(config=config).run(df, events)
                trades[(entry, name)][group].extend(result)
                positive[(entry, name)].append(sum(t.net_pnl for t in result) > 0)
        print(f"{key}: {time.time() - t0:.0f}s", flush=True)
    report = {"interval": INTERVAL, "ci_level": CI_LEVEL, "combos": {}}
    for combo, groups in trades.items():
        report["combos"][f"{combo[0]}|{combo[1]}"] = {
            "all": _stats(groups["crypto"] + groups["forex_metals"]),
            "crypto": _stats(groups["crypto"]),
            "forex_metals": _stats(groups["forex_metals"]),
            "positive_series_pct": 100.0 * sum(positive[combo]) / len(positive[combo]),
        }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / "screening_exits_train_4h.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
