from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.parquet_store import DATASET_SCHEMA_VERSION, ParquetStore


def test_parquet_store_saves_and_loads_partition(tmp_path: Path, make_synthetic_candles):
    store = ParquetStore(base_dir=tmp_path)
    df = make_synthetic_candles(start="2024-01-01", periods=100, freq="1h")

    saved_file = store.save_partition(
        df=df,
        symbol="BTCUSDT",
        interval="1h",
        partition_name="2024",
        source="binance_public_rest",
    )

    assert saved_file.exists()
    assert saved_file.suffix == ".parquet"

    # Load back
    loaded = store.load_dataset(symbol="BTCUSDT", interval="1h")
    assert len(loaded) == 100
    assert list(loaded.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert loaded["timestamp"].dt.tz is not None
    assert loaded.loc[0, "close"] == pytest.approx(df.loc[0, "close"])


def test_parquet_store_creates_and_updates_manifest_with_version_and_source(
    tmp_path: Path, make_synthetic_candles
):
    store = ParquetStore(base_dir=tmp_path)
    df1 = make_synthetic_candles(start="2024-01-01", periods=100, freq="1h")
    df2 = make_synthetic_candles(start="2025-01-01", periods=100, freq="1h")

    store.save_partition(
        df=df1,
        symbol="ETHUSDT",
        interval="4h",
        partition_name="2024.parquet",
        source="binance_public_rest",
        dataset_version="1.0",
    )
    store.save_partition(
        df=df2,
        symbol="ETHUSDT",
        interval="4h",
        partition_name="2025.parquet",
        source="binance_public_rest",
        dataset_version="1.0",
    )

    manifest = store.read_manifest("ETHUSDT", "4h")
    assert manifest is not None
    assert manifest["symbol"] == "ETHUSDT"
    assert manifest["interval"] == "4h"
    assert manifest["dataset_version"] == DATASET_SCHEMA_VERSION
    assert manifest["source"] == "binance_public_rest"
    assert manifest["total_candles"] == 200
    assert len(manifest["partitions"]) == 2
    assert "2024.parquet" in manifest["partitions"]
    assert "2025.parquet" in manifest["partitions"]


def test_parquet_store_time_filtering(tmp_path: Path, make_synthetic_candles):
    store = ParquetStore(base_dir=tmp_path)
    df = make_synthetic_candles(start="2024-01-01 00:00:00", periods=24, freq="1h")
    store.save_partition(df, "BTCUSDT", "1h", "2024-01")

    # Filter a 6-hour window
    filtered = store.load_dataset(
        "BTCUSDT",
        "1h",
        start_time="2024-01-01 05:00:00",
        end_time="2024-01-01 10:00:00",
    )
    assert len(filtered) == 6
    assert filtered.iloc[0]["timestamp"] == pd.to_datetime("2024-01-01 05:00:00", utc=True)
    assert filtered.iloc[-1]["timestamp"] == pd.to_datetime("2024-01-01 10:00:00", utc=True)


def test_parquet_store_empty_df_raises_error(tmp_path: Path):
    store = ParquetStore(base_dir=tmp_path)
    with pytest.raises(ValueError, match="vacío"):
        store.save_partition(pd.DataFrame(), "BTCUSDT", "1h", "empty")


def test_parquet_store_atomic_write_leaves_no_temp_files(tmp_path: Path, make_synthetic_candles):
    store = ParquetStore(base_dir=tmp_path)
    df = make_synthetic_candles(start="2024-01-01", periods=10)
    store.save_partition(df, "BTCUSDT", "1h", "atomic")

    dataset_dir = store.get_dataset_dir("BTCUSDT", "1h")
    temp_files = list(dataset_dir.glob("*.tmp*"))
    assert len(temp_files) == 0


def test_parquet_store_formats_close_time_if_present(tmp_path: Path, make_synthetic_candles):
    store = ParquetStore(base_dir=tmp_path)
    df = make_synthetic_candles(start="2024-01-01", periods=10)
    df["close_time"] = df["timestamp"] + pd.Timedelta(hours=1) - pd.Timedelta(milliseconds=1)

    store.save_partition(df, "BTCUSDT", "1h", "2024")
    loaded = store.load_dataset("BTCUSDT", "1h")
    assert "close_time" in loaded.columns
    assert loaded["close_time"].dt.tz is not None


def test_parquet_store_load_dataset_returns_empty_when_no_files(tmp_path: Path):
    store = ParquetStore(base_dir=tmp_path)
    loaded = store.load_dataset("UNKNOWN", "1h")
    assert loaded.empty


def test_parquet_store_lists_datasets_without_manifest(tmp_path: Path, make_synthetic_candles):
    store = ParquetStore(base_dir=tmp_path)
    # Create non-directory in base_dir to test filter
    (tmp_path / "dummy.txt").write_text("ignore", encoding="utf-8")

    # Create directory with parquet but delete manifest
    df = make_synthetic_candles(periods=5)
    store.save_partition(df, "SOLUSDT", "1d", "2024")
    manifest_path = store._manifest_path("SOLUSDT", "1d")
    if manifest_path.exists():
        manifest_path.unlink()

    datasets = store.list_available_datasets()
    sol_dataset = next(d for d in datasets if d["symbol"] == "SOLUSDT")
    assert sol_dataset["interval"] == "1d"
    assert sol_dataset["dataset_version"] == "unknown"

