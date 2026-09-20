from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

DEFAULT_HISTORICAL_DIR = Path("data/historical")
DATASET_SCHEMA_VERSION = "1.0"


class ParquetStore:
    """Manages structured, columnar storage for OHLCV datasets using Apache Parquet

    with dataset versioning, metadata tracking, and atomic file operations.
    """

    def __init__(self, base_dir: str | Path = DEFAULT_HISTORICAL_DIR):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_dataset_dir(self, symbol: str, interval: str) -> Path:
        target = self.base_dir / symbol.strip().upper() / interval.strip().lower()
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _manifest_path(self, symbol: str, interval: str) -> Path:
        return self.get_dataset_dir(symbol, interval) / "manifest.json"

    def read_manifest(self, symbol: str, interval: str) -> dict | None:
        path = self._manifest_path(symbol, interval)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_manifest(self, symbol: str, interval: str, manifest_data: dict):
        path = self._manifest_path(symbol, interval)
        temp_path = path.with_suffix(".tmp.json")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)
        temp_path.replace(path)

    def save_partition(
        self,
        df: pd.DataFrame,
        symbol: str,
        interval: str,
        partition_name: str,
        source: str = "binance_public_rest",
        dataset_version: str = DATASET_SCHEMA_VERSION,
    ) -> Path:
        """Saves a DataFrame partition as Parquet atomically and updates manifest."""
        if df.empty:
            raise ValueError("No se puede guardar un DataFrame vacío")

        if not partition_name.endswith(".parquet"):
            partition_name = f"{partition_name}.parquet"

        dataset_dir = self.get_dataset_dir(symbol, interval)
        target_file = dataset_dir / partition_name
        temp_file = dataset_dir / f"{partition_name}.tmp"

        # Prepare DataFrame formatting
        prepared = df.copy()
        if "timestamp" in prepared.columns:
            prepared["timestamp"] = pd.to_datetime(prepared["timestamp"], utc=True)
        if "close_time" in prepared.columns:
            prepared["close_time"] = pd.to_datetime(prepared["close_time"], utc=True)

        prepared.to_parquet(
            temp_file,
            engine="pyarrow",
            compression="snappy",
            index=False,
        )
        temp_file.replace(target_file)

        # Update Manifest
        self._update_manifest_after_save(
            symbol=symbol,
            interval=interval,
            partition_file=partition_name,
            df_partition=prepared,
            source=source,
            dataset_version=dataset_version,
        )

        return target_file

    def _update_manifest_after_save(
        self,
        symbol: str,
        interval: str,
        partition_file: str,
        df_partition: pd.DataFrame,
        source: str,
        dataset_version: str,
    ):
        manifest = self.read_manifest(symbol, interval)
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if manifest is None:
            manifest = {
                "symbol": symbol.strip().upper(),
                "interval": interval.strip().lower(),
                "dataset_version": dataset_version,
                "source": source,
                "created_at": now_iso,
                "last_updated_at": now_iso,
                "earliest_timestamp": None,
                "latest_timestamp": None,
                "total_candles": 0,
                "partitions": {},
            }

        earliest = (
            str(df_partition["timestamp"].min())
            if "timestamp" in df_partition.columns
            else None
        )
        latest = (
            str(df_partition["timestamp"].max())
            if "timestamp" in df_partition.columns
            else None
        )

        manifest["dataset_version"] = dataset_version
        manifest["source"] = source
        manifest["last_updated_at"] = now_iso
        manifest["partitions"][partition_file] = {
            "rows": len(df_partition),
            "earliest_timestamp": earliest,
            "latest_timestamp": latest,
            "updated_at": now_iso,
        }

        # Recalculate totals across partitions
        total_rows = sum(p["rows"] for p in manifest["partitions"].values())
        all_earliest = [
            p["earliest_timestamp"]
            for p in manifest["partitions"].values()
            if p["earliest_timestamp"]
        ]
        all_latest = [
            p["latest_timestamp"]
            for p in manifest["partitions"].values()
            if p["latest_timestamp"]
        ]

        manifest["total_candles"] = total_rows
        manifest["earliest_timestamp"] = min(all_earliest) if all_earliest else None
        manifest["latest_timestamp"] = max(all_latest) if all_latest else None

        self._write_manifest(symbol, interval, manifest)

    def load_dataset(
        self,
        symbol: str,
        interval: str,
        start_time: str | pd.Timestamp | None = None,
        end_time: str | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Loads all partition files for symbol and interval, combining and filtering by time."""
        dataset_dir = self.get_dataset_dir(symbol, interval)
        parquet_files = sorted(dataset_dir.glob("*.parquet"))

        if not parquet_files:
            return pd.DataFrame()

        dfs = [pd.read_parquet(f, engine="pyarrow") for f in parquet_files]
        combined = pd.concat(dfs, ignore_index=True)

        if "timestamp" in combined.columns:
            combined["timestamp"] = pd.to_datetime(combined["timestamp"], utc=True)
            combined = combined.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")

            if start_time is not None:
                start_ts = pd.to_datetime(start_time, utc=True)
                combined = combined[combined["timestamp"] >= start_ts]

            if end_time is not None:
                end_ts = pd.to_datetime(end_time, utc=True)
                combined = combined[combined["timestamp"] <= end_ts]

            combined = combined.reset_index(drop=True)

        return combined

    def list_available_datasets(self) -> list[dict]:
        """Scans the historical directory and returns summaries of available datasets."""
        datasets = []
        if not self.base_dir.exists():
            return datasets

        for symbol_dir in sorted(self.base_dir.iterdir()):
            if not symbol_dir.is_dir():
                continue
            for interval_dir in sorted(symbol_dir.iterdir()):
                if not interval_dir.is_dir():
                    continue
                manifest = self.read_manifest(symbol_dir.name, interval_dir.name)
                if manifest:
                    datasets.append(manifest)
                else:
                    parquet_count = len(list(interval_dir.glob("*.parquet")))
                    if parquet_count > 0:
                        datasets.append(
                            {
                                "symbol": symbol_dir.name,
                                "interval": interval_dir.name,
                                "total_partitions": parquet_count,
                                "dataset_version": "unknown",
                            }
                        )
        return datasets
