from __future__ import annotations

import pandas as pd

from src.candle_validator import CandleValidator
from src.dataset_manager import HistoricalDatasetManager
from src.parquet_store import ParquetStore


class MockHistoricalLoader:
    def __init__(self, synthetic_data_generator=None):
        self.calls = []
        self.synthetic_data_generator = synthetic_data_generator

    def get_historical_klines(
        self,
        symbol="BTCUSDT",
        interval="1h",
        start_time="2024-01-01",
        end_time=None,
        include_open_candle=False,
    ):
        self.calls.append(
            {
                "symbol": symbol,
                "interval": interval,
                "start_time": start_time,
                "end_time": end_time,
                "include_open_candle": include_open_candle,
            }
        )
        if self.synthetic_data_generator:
            return self.synthetic_data_generator(symbol, interval, start_time, end_time)
        return pd.DataFrame()


def test_dataset_manager_initial_sync(tmp_path, make_synthetic_candles):
    store = ParquetStore(base_dir=tmp_path / "historical")
    candles = make_synthetic_candles(start="2024-01-01", periods=20, freq="1h")

    loader = MockHistoricalLoader(synthetic_data_generator=lambda *args, **kwargs: candles)
    validator = CandleValidator()

    manager = HistoricalDatasetManager(
        store=store,
        data_loader=loader,
        validator=validator,
    )

    synced_df = manager.sync_dataset(
        symbol="BTCUSDT",
        interval="1h",
        start_time="2024-01-01",
    )

    assert len(synced_df) == 20
    assert len(loader.calls) == 1
    assert loader.calls[0]["symbol"] == "BTCUSDT"

    # Verify manifest and store
    manifest = store.get_manifest("BTCUSDT", "1h")
    assert manifest is not None
    assert manifest["total_candles"] == 20
    assert manifest["extra_metadata"]["gaps_count"] == 0


def test_dataset_manager_incremental_sync(tmp_path, make_synthetic_candles):
    store = ParquetStore(base_dir=tmp_path / "historical")

    # Initial 10 candles
    initial_candles = make_synthetic_candles(start="2024-01-01 00:00:00", periods=10, freq="1h")
    store.write_dataset(initial_candles, "BTCUSDT", "1h")

    # Next 10 candles
    next_candles = make_synthetic_candles(start="2024-01-01 10:00:00", periods=10, freq="1h")

    loader = MockHistoricalLoader(synthetic_data_generator=lambda *args, **kwargs: next_candles)
    manager = HistoricalDatasetManager(store=store, data_loader=loader)

    synced_df = manager.sync_dataset(
        symbol="BTCUSDT",
        interval="1h",
        start_time="2024-01-01 00:00:00",
        end_time="2024-01-01 19:00:00",
    )

    assert len(loader.calls) == 1
    # Check start_time passed to loader is next candle in ms
    expected_start_ms = int(initial_candles["timestamp"].max().value // 1_000_000) + 3_600_000
    assert loader.calls[0]["start_time"] == expected_start_ms

    assert len(synced_df) == 20
    assert store.get_manifest("BTCUSDT", "1h")["total_candles"] == 20


def test_dataset_manager_already_up_to_date(tmp_path, make_synthetic_candles):
    store = ParquetStore(base_dir=tmp_path / "historical")
    candles = make_synthetic_candles(start="2024-01-01 00:00:00", periods=10, freq="1h")
    store.write_dataset(candles, "BTCUSDT", "1h")

    loader = MockHistoricalLoader()
    manager = HistoricalDatasetManager(store=store, data_loader=loader)

    # Sync requested up to an end_time already covered in cache
    df = manager.sync_dataset(
        symbol="BTCUSDT",
        interval="1h",
        start_time="2024-01-01 00:00:00",
        end_time="2024-01-01 05:00:00",
    )

    assert len(loader.calls) == 0  # No network calls needed
    assert len(df) == 6  # 00:00 to 05:00 inclusive


def test_dataset_manager_force_refresh(tmp_path, make_synthetic_candles):
    store = ParquetStore(base_dir=tmp_path / "historical")
    initial_candles = make_synthetic_candles(start="2024-01-01 00:00:00", periods=5, freq="1h")
    store.write_dataset(initial_candles, "BTCUSDT", "1h")

    refreshed_candles = make_synthetic_candles(start="2024-01-01 00:00:00", periods=15, freq="1h")
    loader = MockHistoricalLoader(synthetic_data_generator=lambda *args, **kwargs: refreshed_candles)
    manager = HistoricalDatasetManager(store=store, data_loader=loader)

    df = manager.sync_dataset(
        symbol="BTCUSDT",
        interval="1h",
        start_time="2024-01-01 00:00:00",
        force_refresh=True,
    )

    assert len(loader.calls) == 1
    assert loader.calls[0]["start_time"] == "2024-01-01 00:00:00"
    assert len(df) == 15
    assert store.get_manifest("BTCUSDT", "1h")["total_candles"] == 15


def test_dataset_manager_empty_download_returns_cached_or_empty(tmp_path, make_synthetic_candles):
    store = ParquetStore(base_dir=tmp_path / "historical")
    loader = MockHistoricalLoader(synthetic_data_generator=lambda *args, **kwargs: pd.DataFrame())
    manager = HistoricalDatasetManager(store=store, data_loader=loader)

    # Completely empty
    df = manager.sync_dataset("SOLUSDT", "1h", start_time="2024-01-01")
    assert df.empty

    # Cached data exists, but incremental return empty
    cached_candles = make_synthetic_candles(start="2024-01-01 00:00:00", periods=5, freq="1h")
    store.write_dataset(cached_candles, "SOLUSDT", "1h")

    df2 = manager.sync_dataset("SOLUSDT", "1h", start_time="2024-01-01 00:00:00", end_time="2024-01-02 00:00:00")
    assert len(df2) == 5


def test_dataset_manager_load_dataset_and_summary(tmp_path, make_synthetic_candles):
    store = ParquetStore(base_dir=tmp_path / "historical")
    btc_candles = make_synthetic_candles(start="2024-01-01", periods=10, freq="1h")
    eth_candles = make_synthetic_candles(start="2024-01-01", periods=10, freq="1D")

    store.write_dataset(btc_candles, "BTCUSDT", "1h")
    store.write_dataset(eth_candles, "ETHUSDT", "1D")

    manager = HistoricalDatasetManager(store=store)

    # Read slice
    sliced = manager.load_dataset(
        "BTCUSDT",
        "1h",
        start_time="2024-01-01 02:00:00",
        end_time="2024-01-01 04:00:00",
    )
    assert len(sliced) == 3

    # Summary
    all_summaries = manager.get_dataset_summary()
    assert len(all_summaries) == 2

    btc_summary = manager.get_dataset_summary(symbol="BTCUSDT")
    assert len(btc_summary) == 1
    assert btc_summary[0]["symbol"] == "BTCUSDT"
    assert btc_summary[0]["interval"] == "1h"

    eth_summary = manager.get_dataset_summary(interval="1D")
    assert len(eth_summary) == 1
    assert eth_summary[0]["symbol"] == "ETHUSDT"


def test_dataset_manager_gap_warning(tmp_path, make_synthetic_candles):
    store = ParquetStore(base_dir=tmp_path / "historical")
    candles = make_synthetic_candles(start="2024-01-01", periods=10, freq="1h")
    # Induce gap by dropping row 3
    candles_with_gap = pd.concat([candles.iloc[:3], candles.iloc[4:]], ignore_index=True)

    loader = MockHistoricalLoader(synthetic_data_generator=lambda *args, **kwargs: candles_with_gap)
    manager = HistoricalDatasetManager(store=store, data_loader=loader)

    df = manager.sync_dataset("BTCUSDT", "1h")
    assert len(df) == 9

    manifest = store.get_manifest("BTCUSDT", "1h")
    assert manifest["extra_metadata"]["gaps_count"] == 1


def test_dataset_manager_slice_empty_df():
    empty = pd.DataFrame()
    sliced = HistoricalDatasetManager._slice_df(empty, start_time="2024-01-01")
    assert sliced.empty
