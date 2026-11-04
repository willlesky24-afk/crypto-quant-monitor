"""Download the fixed v3.0 evidence dataset (pre-registered universe and dates).

Universe and period were approved before looking at any result:
- Crypto (Binance public REST, SPOT): BTC, ETH, SOL, BNB, XRP, ADA, AVAX, LINK.
- Forex majors and spot metals (OANDA v20, mid + bid/ask spread): EUR/USD,
  GBP/USD, USD/JPY, USD/CHF, AUD/USD, USD/CAD, NZD/USD, XAU/USD, XAG/USD.
- Intervals: 1h and 4h. Period: 2021-11-01 to 2026-11-01 (UTC).

Each series is stored with ParquetStore under data/evidence/<SYMBOL>_<SOURCE>/
<interval>/ and its manifest records the provider. Re-running skips series
already present. Usage:  python scripts/download_evidence_dataset.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

from src.historical_data_loader import HistoricalDataLoader  # noqa: E402
from src.market_data_providers import OandaProvider  # noqa: E402
from src.parquet_store import ParquetStore  # noqa: E402

START = "2021-11-01T00:00:00Z"
END = "2026-11-01T00:00:00Z"
INTERVALS = ("1h", "4h")
CRYPTO = (
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "LINKUSDT",
)
FX_METALS = (
    "EURUSD=X",
    "GBPUSD=X",
    "USDJPY=X",
    "USDCHF=X",
    "AUDUSD=X",
    "USDCAD=X",
    "NZDUSD=X",
    "XAUUSD=X",
    "XAGUSD=X",
)
EVIDENCE_DIR = Path("data/evidence")


def main() -> int:
    load_dotenv(".env")
    store = ParquetStore(EVIDENCE_DIR)
    oanda = OandaProvider(
        token=os.getenv("OANDA_API_TOKEN", "").strip(),
        environment=os.getenv("OANDA_ENVIRONMENT", "practice"),
        timeout_seconds=30.0,
    )
    binance = HistoricalDataLoader()
    jobs = [(s, "BINANCE", iv) for s in CRYPTO for iv in INTERVALS] + [
        (s, "OANDA", iv) for s in FX_METALS for iv in INTERVALS
    ]
    for symbol, source, interval in jobs:
        key = f"{symbol.replace('=X', '')}_{source}"
        if store.load_dataset(key, interval).shape[0] > 0:
            print(f"[skip] {key} {interval}", flush=True)
            continue
        if source == "BINANCE":
            df = binance.get_historical_klines(symbol, interval, START, END)
            df = df[["timestamp", "open", "high", "low", "close", "volume"]]
            meta = {"provider": "binance", "volume_kind": "reported"}
        else:
            df = oanda.get_history(symbol, interval, START, END)
            meta = {
                "provider": "oanda",
                "volume_kind": "tick",
                "spread_kind": df.attrs.get("spread_kind"),
                "weekend_bars_removed": df.attrs.get("weekend_bars_removed"),
            }
        store.save_dataset(
            df,
            key,
            interval,
            source=meta["provider"],
            extra_manifest_metadata={**meta, "start": START, "end": END},
        )
        print(
            f"[ok] {key} {interval}: {len(df)} velas "
            f"{df['timestamp'].iloc[0]} -> {df['timestamp'].iloc[-1]}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
