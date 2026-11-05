"""How often does the explosiveness test fire, and what followed?

4h, 17 markets, 2021-11 to 2024-12. The 2025-2026 test period is cut before any
calculation. Descriptive: no direction and no costs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.evidence_evaluation import PERIODS  # noqa: E402
from src.indicators import TechnicalIndicators  # noqa: E402
from src.parquet_store import ParquetStore  # noqa: E402
from src.stress_measures import (  # noqa: E402
    ALPHA,
    LOOKBACK_BARS,
    bsadf_series,
    critical_value,
    min_window,
)
from src.unusual_radar import HORIZON_BARS, history_from_mask  # noqa: E402

EVIDENCE_DIR = Path("data/evidence")
OUT = Path("reports/evidence/stress_study_4h.json")


def main() -> int:
    end = pd.Timestamp(PERIODS["validation"][1], tz="UTC")
    store = ParquetStore(EVIDENCE_DIR)
    keys = sorted(p.name for p in EVIDENCE_DIR.iterdir() if p.is_dir())
    critical = critical_value(LOOKBACK_BARS, 1.0 - ALPHA / len(keys))
    duration = int(np.log(LOOKBACK_BARS))
    per_market = {}
    totals = {"bars": 0, "flagged": 0, "cases": 0, "big_moves": 0, "base_sum": 0.0}
    for key in keys:
        raw = store.load_dataset(key, "4h")
        raw = raw[pd.to_datetime(raw["timestamp"], utc=True) < end]
        df = TechnicalIndicators().calculate_all(raw.copy()).reset_index(drop=True)
        stats = bsadf_series(
            np.log(df["close"]), LOOKBACK_BARS, min_window(LOOKBACK_BARS)
        )
        over = (stats > critical).astype(int)
        flagged = over.rolling(duration).sum() == duration
        valid = stats.notna()
        h = history_from_mask(flagged[valid], df["close"][valid], df["atr"][valid])
        per_market[key] = {"flagged_bars": int(flagged.sum()), **h}
        totals["bars"] += int(valid.sum())
        totals["flagged"] += int(flagged.sum())
        totals["cases"] += h["cases"]
        totals["big_moves"] += h["big_moves"]
        totals["base_sum"] += h["baseline_pct"]
        print(key, per_market[key], flush=True)
    report = {
        "critical_value": critical,
        "horizon_bars": HORIZON_BARS,
        "flagged_pct_of_bars": 100.0 * totals["flagged"] / totals["bars"],
        "cases": totals["cases"],
        "big_moves": totals["big_moves"],
        "baseline_pct": totals["base_sum"] / len(keys),
        "per_market": per_market,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print({k: v for k, v in report.items() if k != "per_market"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
