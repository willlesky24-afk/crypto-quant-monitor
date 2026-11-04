from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .backtest_models import DatasetProvenance
from .candle_validator import INTERVAL_TIMEDELTAS, CandleValidator
from .historical_data_loader import (
    DEFAULT_BASE_URL,
    HistoricalDataLoader,
    RawHistoricalBatch,
)
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
        provenance = self.store.inspect_provenance(symbol, interval)
        result = self.store.read_dataset(
            symbol=symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
        )
        result.attrs["_controlled_provenance"] = provenance
        return result

    @staticmethod
    def _inspect_raw_batch(
        batch: RawHistoricalBatch, interval: str
    ) -> tuple[pd.DataFrame, str, str, dict[str, int]]:
        """Inspect arrival order and page boundaries before legacy normalization."""
        raw = batch.candles
        counts = {
            "within_page_duplicates": 0,
            "page_overlaps": 0,
            "conflicting_duplicates": 0,
            "within_page_disorder": 0,
            "combined_disorder": 0,
            "irregular_steps": 0,
            "misaligned_timestamps": 0,
            "partial_start_boundary": 0,
            "partial_end_boundary": 0,
        }
        issues: list[str] = []
        if sum(batch.page_sizes) != len(raw):
            issues.append("Límites de páginas inconsistentes.")
        timestamps = pd.to_datetime(raw["timestamp"], utc=True, errors="coerce")
        if timestamps.isna().any():
            issues.append("Timestamps inválidos.")
        seen: dict[pd.Timestamp, tuple[int, tuple]] = {}
        previous_combined: pd.Timestamp | None = None
        offset = 0
        for page_index, page_size in enumerate(batch.page_sizes):
            previous_in_page: pd.Timestamp | None = None
            for row_index in range(offset, min(offset + page_size, len(raw))):
                ts = timestamps.iloc[row_index]
                if pd.isna(ts):
                    continue
                values = tuple(
                    raw.iloc[row_index][["open", "high", "low", "close", "volume"]]
                )
                if previous_in_page is not None and ts <= previous_in_page:
                    counts["within_page_disorder"] += 1
                if ts in seen:
                    prior_page, prior_values = seen[ts]
                    if prior_page == page_index:
                        counts["within_page_duplicates"] += 1
                    else:
                        counts["page_overlaps"] += 1
                    if values != prior_values:
                        counts["conflicting_duplicates"] += 1
                elif previous_combined is not None and ts < previous_combined:
                    counts["combined_disorder"] += 1
                seen.setdefault(ts, (page_index, values))
                previous_in_page = ts
                previous_combined = ts
            offset += page_size
        if counts["within_page_duplicates"] or counts["within_page_disorder"]:
            issues.append("Duplicados o desorden dentro de una página.")
        if counts["conflicting_duplicates"]:
            issues.append("Velas con timestamp repetido y OHLCV diferente.")
        if counts["combined_disorder"]:
            issues.append("Desorden al combinar páginas.")
        normalized = (
            raw.drop_duplicates(subset=["timestamp"])
            .sort_values("timestamp")
            .reset_index(drop=True)
        )
        expected_step = INTERVAL_TIMEDELTAS.get(interval.lower())
        if expected_step is None:
            issues.append("Intervalo no reconocido.")
        else:
            # Requested boundaries need not be candle opens. Record them separately
            # from real gaps between consecutive observations.
            interval_ms = expected_step.value // 1_000_000
            counts["partial_start_boundary"] = int(
                batch.requested_start_ms is not None
                and batch.requested_start_ms % interval_ms != 0
            )
            counts["partial_end_boundary"] = int(
                batch.requested_end_ms is not None
                and batch.requested_end_ms % interval_ms != 0
            )
            normalized_ts = pd.to_datetime(normalized["timestamp"], utc=True)
            counts["misaligned_timestamps"] = int(
                (
                    normalized_ts.map(lambda ts: ts.value % expected_step.value != 0)
                ).sum()
            )
            if counts["misaligned_timestamps"]:
                issues.append("Apertura de vela no alineada al intervalo declarado.")
            if len(normalized) > 1:
                steps = normalized_ts.diff().iloc[1:]
                counts["irregular_steps"] = int((steps != expected_step).sum())
                if counts["irregular_steps"]:
                    issues.append(
                        "Huecos o frecuencia distinta del intervalo declarado."
                    )
        if counts["page_overlaps"]:
            # Identical page overlaps are recorded, not labeled as provider defects.
            issues.append("Solapamiento entre páginas: origen temporal no acreditado.")
        return (
            normalized,
            "VALID" if not issues else "UNVERIFIED",
            " ".join(issues),
            counts,
        )

    def _download_for_sync(self, symbol: str, interval: str, start_time, end_time):
        kwargs = dict(
            symbol=symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            include_open_candle=False,
        )
        if (
            type(self.loader) is HistoricalDataLoader
            and self.loader.base_url == DEFAULT_BASE_URL
        ):
            batch = self.loader.get_historical_klines(**kwargs, return_raw_batch=True)
            normalized, status, reason, counts = self._inspect_raw_batch(
                batch, interval
            )
            return normalized, batch, status, reason, counts
        return (
            self.loader.get_historical_klines(**kwargs),
            None,
            "UNKNOWN",
            "Cargador no acreditado.",
            {},
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
        had_existing = bool(
            self.store.read_manifest(sym, inv)
            or list(self.store.get_dataset_dir(sym, inv).glob("*.parquet"))
        )
        raw_batch = None
        temporal_status = "UNKNOWN"
        temporal_reason = ""
        raw_counts: dict[str, int] = {}

        existing_df = pd.DataFrame()
        if not force_refresh:
            existing_df = self.store.read_dataset(symbol=sym, interval=inv)

        if not existing_df.empty:
            existing_df["timestamp"] = pd.to_datetime(
                existing_df["timestamp"], utc=True
            )
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

            logger.info(
                "Incremental sync for %s %s from %s",
                sym,
                inv,
                pd.to_datetime(next_start_ms, unit="ms", utc=True),
            )
            new_df, raw_batch, temporal_status, temporal_reason, raw_counts = (
                self._download_for_sync(sym, inv, next_start_ms, end_time)
            )

            if new_df.empty:
                return self._slice_df(existing_df, start_time, end_time)

            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            logger.info("Full sync for %s %s from %s", sym, inv, start_time)
            combined_df, raw_batch, temporal_status, temporal_reason, raw_counts = (
                self._download_for_sync(sym, inv, start_time, end_time)
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
                "raw_temporal_validation": temporal_status,
                "raw_temporal_counts": raw_counts,
            },
        )

        if raw_batch is not None and not had_existing:
            is_valid = temporal_status == "VALID" and report.is_clean
            self.store._record_controlled_provenance(
                sym,
                inv,
                DatasetProvenance(
                    status="CONTROLLED_INGESTION",
                    reason=""
                    if is_valid
                    else (temporal_reason or "Calidad OHLCV no validada."),
                    provider="BINANCE_PUBLIC_SPOT_REST",
                    instrument_type="CRYPTO_SPOT",
                    calendar="24_7",
                    interval=inv,
                    acquired_at_utc=raw_batch.acquired_at_utc,
                    temporal_validation="VALID" if is_valid else "UNVERIFIED",
                    normalization=(
                        "ninguna"
                        if not raw_counts.get("page_overlaps")
                        else "solapamientos de páginas deduplicados"
                    ),
                ),
            )

        return self._slice_df(validated_df, start_time, end_time)

    def get_dataset_summary(
        self, symbol: str | None = None, interval: str | None = None
    ) -> list[dict[str, Any]]:
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
