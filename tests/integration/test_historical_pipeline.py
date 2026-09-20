from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.candle_validator import CandleValidator
from src.dataset_manager import HistoricalDatasetManager
from src.engine import MarketEngine
from src.indicators import TechnicalIndicators
from src.parquet_store import ParquetStore
from src.volume_profile import VolumeProfile


class MultiYearMockLoader:
    def __init__(self, full_multi_year_df: pd.DataFrame):
        self.df = full_multi_year_df.copy()
        self.df["timestamp"] = pd.to_datetime(self.df["timestamp"], utc=True)
        self.calls = []

    def get_historical_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "1h",
        start_time: str | int = "2023-01-01",
        end_time: str | int | None = None,
        include_open_candle: bool = False,
    ) -> pd.DataFrame:
        self.calls.append({"start_time": start_time, "end_time": end_time})
        start_ts = pd.to_datetime(start_time, utc=True) if isinstance(start_time, str) else pd.to_datetime(start_time, unit="ms", utc=True)
        filtered = self.df[self.df["timestamp"] >= start_ts]

        if end_time is not None:
            end_ts = pd.to_datetime(end_time, utc=True) if isinstance(end_time, str) else pd.to_datetime(end_time, unit="ms", utc=True)
            filtered = filtered[filtered["timestamp"] <= end_ts]

        return filtered.reset_index(drop=True)


def test_multi_year_historical_pipeline_e2e(tmp_path: Path, make_synthetic_candles):
    """Verifies complete end-to-end flow:

    Synthetic multi-year klines -> Loader -> Validator -> ParquetStore (multi-year partitions)
    -> Manifest metadata -> Technical indicators & MarketEngine.
    """
    # 1. Generate 3 years of synthetic hourly data (2023 to 2025)
    candles_2023 = make_synthetic_candles(start="2023-12-01", periods=500, freq="1h", base_price=30000.0)
    candles_2024 = make_synthetic_candles(start="2024-01-01", periods=500, freq="1h", base_price=42000.0)
    candles_2025 = make_synthetic_candles(start="2025-01-01", periods=500, freq="1h", base_price=60000.0)

    combined_synthetic = pd.concat([candles_2023, candles_2024, candles_2025], ignore_index=True)
    loader = MultiYearMockLoader(combined_synthetic)

    store = ParquetStore(base_dir=tmp_path / "historical_e2e")
    validator = CandleValidator()
    manager = HistoricalDatasetManager(store=store, data_loader=loader, validator=validator)

    # 2. Sync dataset
    synced_df = manager.sync_dataset(
        symbol="BTCUSDT",
        interval="1h",
        start_time="2023-12-01",
        end_time="2025-01-21 20:00:00",
    )

    assert len(synced_df) == 1500
    assert len(loader.calls) == 1

    # 3. Verify Parquet files and partitioning on disk
    dataset_dir = store.get_dataset_dir("BTCUSDT", "1h")
    parquet_files = sorted([f.name for f in dataset_dir.glob("*.parquet")])
    assert "2023.parquet" in parquet_files
    assert "2024.parquet" in parquet_files
    assert "2025.parquet" in parquet_files

    # 4. Verify manifest
    manifest = store.get_manifest("BTCUSDT", "1h")
    assert manifest is not None
    assert manifest["total_candles"] == 1500
    assert manifest["dataset_version"] == "1.0"
    assert len(manifest["partitions"]) == 3
    assert manifest["partitions"]["2023.parquet"]["rows"] == 500
    assert manifest["partitions"]["2024.parquet"]["rows"] == 500
    assert manifest["partitions"]["2025.parquet"]["rows"] == 500

    # 5. Load slice from Parquet cache
    cached_2024 = manager.load_dataset(
        symbol="BTCUSDT",
        interval="1h",
        start_time="2024-01-01",
        end_time="2024-01-10",
    )
    assert len(cached_2024) > 0
    assert cached_2024["timestamp"].min() >= pd.to_datetime("2024-01-01", utc=True)
    assert cached_2024["timestamp"].max() <= pd.to_datetime("2024-01-10", utc=True)

    # 6. Execute technical indicators and quantitative engines on cached dataset
    loaded_all = manager.load_dataset("BTCUSDT", "1h")
    assert len(loaded_all) == 1500

    enriched = TechnicalIndicators().calculate_all(loaded_all.copy())
    assert "ema_50" in enriched.columns
    assert "ema_200" in enriched.columns
    assert "rsi" in enriched.columns
    assert "atr" in enriched.columns

    profile = VolumeProfile().calculate(enriched)
    assert "poc" in profile
    assert "vah" in profile
    assert "val" in profile
    assert profile["poc"] > 0

    analysis = MarketEngine().analyze(enriched, profile)
    assert "trend" in analysis
    assert "momentum" in analysis
    assert "volatility" in analysis
    assert "volume" in analysis
    assert "score" in analysis
    assert "market_context" in analysis
    assert 0 <= analysis["score"] <= 5


def test_multi_year_incremental_sync_preserves_partitions(tmp_path: Path, make_synthetic_candles):
    """Verifies that an incremental sync adds new data correctly without corrupting prior partitions."""
    store = ParquetStore(base_dir=tmp_path / "historical_incremental")

    # Initial sync for 2024 only
    candles_2024 = make_synthetic_candles(start="2024-01-01", periods=200, freq="1h")
    candles_2025 = make_synthetic_candles(start="2025-01-01", periods=200, freq="1h")
    full_dataset = pd.concat([candles_2024, candles_2025], ignore_index=True)

    loader = MultiYearMockLoader(full_dataset)
    manager = HistoricalDatasetManager(store=store, data_loader=loader)

    # First sync: 2024 data only
    manager.sync_dataset("ETHUSDT", "1h", start_time="2024-01-01", end_time="2024-01-09 08:00:00")
    manifest1 = store.get_manifest("ETHUSDT", "1h")
    assert manifest1["total_candles"] == 200
    assert len(manifest1["partitions"]) == 1
    assert "2024.parquet" in manifest1["partitions"]

    # Second sync: incremental into 2025
    manager.sync_dataset("ETHUSDT", "1h", start_time="2024-01-01", end_time="2025-01-09 08:00:00")
    manifest2 = store.get_manifest("ETHUSDT", "1h")
    assert manifest2["total_candles"] == 400
    assert len(manifest2["partitions"]) == 2
    assert "2024.parquet" in manifest2["partitions"]
    assert "2025.parquet" in manifest2["partitions"]
