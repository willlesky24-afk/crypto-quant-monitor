"""Do the radar's similar cases precede big moves more often than usual?

Training period only, 4h, 17 markets. Episodes are pooled per measure and compared
with the pooled baseline. Reference, not proof: no direction and no costs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src.evidence_evaluation import PERIODS  # noqa: E402
from src.indicators import TechnicalIndicators  # noqa: E402
from src.parquet_store import ParquetStore  # noqa: E402
from src.unusual_radar import case_history, iter_measures  # noqa: E402

EVIDENCE_DIR = Path("data/evidence")
OUT = Path("reports/evidence/radar_study_train_4h.json")
PAIRS = [
    ("BTCUSDT", "ETHUSDT"),
    ("XAUUSD", "XAGUSD"),
    ("AUDUSD", "NZDUSD"),
    ("EURUSD", "GBPUSD"),
]


def main() -> int:
    end = pd.Timestamp(PERIODS["train"][1], tz="UTC")
    store = ParquetStore(EVIDENCE_DIR)
    markets: dict[str, pd.DataFrame] = {}
    crypto, forex = [], []
    for path in sorted(EVIDENCE_DIR.iterdir()):
        raw = store.load_dataset(path.name, "4h")
        raw = raw[pd.to_datetime(raw["timestamp"], utc=True) < end]
        df = TechnicalIndicators().calculate_all(raw.copy()).reset_index(drop=True)
        name = path.name.rsplit("_", 1)[0]
        markets[name] = df.iloc[200:][["timestamp", "close", "atr"]]
        (forex if path.name.endswith("_OANDA") else crypto).append(name)

    frames = {k: v.set_index("timestamp") for k, v in markets.items()}
    totals: dict[str, dict[str, float]] = {}
    groups = [crypto, forex]
    for market, measure, series, side in iter_measures(markets, groups, PAIRS):
        h = case_history(series, side, frames[market.split("/")[0]])
        t = totals.setdefault(
            measure, {"cases": 0, "big_moves": 0, "base_sum": 0.0, "series": 0}
        )
        t["cases"] += h["cases"]
        t["big_moves"] += h["big_moves"]
        t["base_sum"] += h["baseline_pct"]
        t["series"] += 1
    report = {
        m: {
            "cases": t["cases"],
            "big_moves": t["big_moves"],
            "hit_pct": 100.0 * t["big_moves"] / t["cases"],
            "baseline_pct": t["base_sum"] / t["series"],
        }
        for m, t in totals.items()
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
