from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .candle_validator import CandleValidator
from .historical_data_loader import HistoricalDataLoader
from .parquet_store import ParquetStore

logger = logging.getLogger(__name__)


class HistoricalDatasetManager:
    """Orchestrates historical dataset lifecycle: local disk cache via ParquetStore,

    paginated downloads via HistoricalDataLoader, and quality validation via CandleValidator.
    Supports incremental synchronization to avoid redundant API queries.
    """

    def __init__(
        self,
        base_dir: str | Path = "data/historical",
        data_loader: HistoricalDataLoader | None = None,
        validator: CandleValidator | None = None,
        store: ParquetStore | None = None,
    ):
        self.store = store or ParquetStore(base_dir=base_dir)
        self.loader = data_loader or HistoricalDataLoader()
        self.validator = validator or CandleValidator()

    def load_dataset(
        self,
        symbol: str,
        interval: str,
        start_time: str | datetime | pd.Timestamp | int | None = None,
        end_time: str | datetime | pd.Timestamp | int | None = None,
    ) -> pd.DataFrame:
        """Reads stored dataset from local Parquet cache, optionally slicing by date range."""
        return self.store.read_dataset(
            symbol=symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
        )

    def sync_dataset(
        self,
        symbol: str,
        interval: str,
        start_time: str | datetime | pd.Timestamp | int = "2024-01-01",
        end_time: str | datetime | pd.Timestamp | int | None = None,
        force_refresh: bool = False,
        repair_gaps: bool = False,
    ) -> pd.DataFrame:
        """Synchronizes dataset locally.

        If dataset already exists and force_refresh is False:
        - Detects cached range.
        - Only downloads missing subsequent range incrementally.
        - Merges, validates, and updates Parquet store + manifest.
        """
        sym = symbol.strip().upper()
        inv = interval.strip().lower()

        existing_df = pd.DataFrame()
        if not force_refresh:
            existing_df = self.store.read_dataset(symbol=sym, interval=inv)

        if not existing_df.empty:
            existing_df["timestamp"] = pd.to_datetime(existing_df["timestamp"], utc=True)
            last_cached_ts = existing_df["timestamp"].max()

            # Target start is next candle after last cached timestamp
            interval_ms = HistoricalDataLoader._interval_to_ms(inv)
            next_start_ms = int(last_cached_ts.value // 1_000_000) + interval_ms
            requested_end_ms = (
                HistoricalDataLoader._to_timestamp_ms(end_time)
                if end_time is not None
                else int(pd.Timestamp.now(tz="UTC").value // 1_000_000)
            )

            if next_start_ms > requested_end_ms:
                # Already up to date
                return self._slice_df(existing_df, start_time, end_time)

            logger.info("Incremental sync for %s %s from %s", sym, inv, pd.to_datetime(next_start_ms, unit="ms", utc=True))
            new_df = self.loader.get_historical_klines(
                symbol=sym,
                interval=inv,
                start_time=next_start_ms,
                end_time=end_time,
                include_open_candle=False,
            )

            if new_df.empty:
                return self._slice_df(existing_df, start_time, end_time)

            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            logger.info("Full sync for %s %s from %s", sym, inv, start_time)
            combined_df = self.loader.get_historical_klines(
                symbol=sym,
                interval=inv,
                start_time=start_time,
                end_time=end_time,
                include_open_candle=False,
            )

        if combined_df.empty:
            return pd.DataFrame()

        # Validate and clean data
        validated_df, report = self.validator.validate(
            combined_df,
            interval=inv,
            strict=False,
            repair=repair_gaps,
        )

        if not report.is_clean and report.gaps_count > 0:
            logger.warning("Dataset %s %s has %d gaps", sym, inv, report.gaps_count)

        # Write to Parquet store
        self.store.write_dataset(
            df=validated_df,
            symbol=sym,
            interval=inv,
            extra_manifest_metadata={
                "gaps_count": report.gaps_count,
                "duplicates_count": report.duplicates_dropped,
                "ohlcv_anomalies_count": report.ohlcv_anomalies_count,
            },
        )

        return self._slice_df(validated_df, start_time, end_time)

    def get_dataset_summary(self, symbol: str | None = None, interval: str | None = None) -> list[dict[str, Any]]:
        """Returns metadata summary of available datasets."""
        manifests = self.store.list_datasets()
        results = []
        for m in manifests:
            m_sym = m.get("symbol", "")
            m_inv = m.get("interval", "")
            if symbol and m_sym.upper() != symbol.strip().upper():
                continue
            if interval and m_inv.lower() != interval.strip().lower():
                continue
            results.append(
                {
                    "symbol": m_sym,
                    "interval": m_inv,
                    "dataset_version": m.get("dataset_version", "unknown"),
                    "total_rows": m.get("total_candles", 0),
                    "start_time": m.get("earliest_timestamp"),
                    "end_time": m.get("latest_timestamp"),
                    "source": m.get("source", "unknown"),
                    "updated_at": m.get("last_updated_at"),
                    "partitions_count": len(m.get("partitions", {})),
                }
            )
        return results

    @staticmethod
    def _slice_df(
        df: pd.DataFrame,
        start_time: str | datetime | pd.Timestamp | int | None = None,
        end_time: str | datetime | pd.Timestamp | int | None = None,
    ) -> pd.DataFrame:
        if df.empty:
            return df
        result = df.copy()
        result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True)
        if start_time is not None:
            start_ts = pd.to_datetime(start_time, utc=True)
            result = result[result["timestamp"] >= start_ts]
        if end_time is not None:
            end_ts = pd.to_datetime(end_time, utc=True)
            result = result[result["timestamp"] <= end_ts]
        return result.reset_index(drop=True)
