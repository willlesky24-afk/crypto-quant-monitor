from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.candle_validator import CandleValidator, ValidationError


def test_validator_clean_dataset_returns_is_clean(make_synthetic_candles):
    validator = CandleValidator()
    df = make_synthetic_candles(start="2024-01-01", periods=100, freq="1h")

    clean_df, report = validator.validate(df, interval="1h")
    assert report.is_clean is True
    assert report.total_candles == 100
    assert report.gaps_count == 0
    assert report.duplicates_dropped == 0
    assert report.ohlcv_anomalies_count == 0
    assert len(clean_df) == 100
    assert report.to_dict()["is_clean"] is True


def test_validator_detects_temporal_gaps(make_synthetic_candles):
    validator = CandleValidator()
    df = make_synthetic_candles(start="2024-01-01", periods=50, freq="1h")

    # Drop bars at indices 10 to 14 (5 missing bars)
    df_with_gap = pd.concat([df.iloc[:10], df.iloc[15:]], ignore_index=True)

    clean_df, report = validator.validate(df_with_gap, interval="1h")
    assert report.is_clean is False
    assert report.gaps_count == 1
    assert report.missing_candles_estimated == 5
    assert len(report.gaps) == 1
    assert "missing_candles" in report.gaps[0]


def test_validator_strict_mode_raises_on_gaps(make_synthetic_candles):
    validator = CandleValidator()
    df = make_synthetic_candles(start="2024-01-01", periods=20, freq="1h")
    df_with_gap = pd.concat([df.iloc[:5], df.iloc[10:]], ignore_index=True)

    with pytest.raises(ValidationError, match="huecos temporales"):
        validator.validate(df_with_gap, interval="1h", strict=True)


def test_validator_detects_and_drops_duplicates(make_synthetic_candles):
    validator = CandleValidator()
    df = make_synthetic_candles(start="2024-01-01", periods=10, freq="1h")

    # Duplicate row at index 3
    df_with_dups = pd.concat([df, df.iloc[[3]]], ignore_index=True)

    clean_df, report = validator.validate(df_with_dups, interval="1h", repair=True)
    assert report.duplicates_dropped == 1
    assert len(clean_df) == 10
    assert report.is_clean is False


def test_validator_strict_mode_raises_on_duplicates(make_synthetic_candles):
    validator = CandleValidator()
    df = make_synthetic_candles(start="2024-01-01", periods=5, freq="1h")
    df_with_dups = pd.concat([df, df.iloc[[0]]], ignore_index=True)

    with pytest.raises(ValidationError, match="duplicadas"):
        validator.validate(df_with_dups, interval="1h", strict=True)


def test_validator_detects_and_repairs_ohlcv_anomalies(make_synthetic_candles):
    validator = CandleValidator()
    df = make_synthetic_candles(start="2024-01-01", periods=10, freq="1h")

    # Introduce invalid high/low and negative volume
    df.loc[2, "high"] = 50.0  # open/close are ~100 -> high < close
    df.loc[3, "low"] = 150.0  # low > high
    df.loc[4, "volume"] = -10.0

    clean_df, report = validator.validate(df, interval="1h", repair=True)
    assert report.ohlcv_anomalies_count == 3
    assert report.is_clean is False
    # Check that high >= max(open, close) after repair
    assert clean_df.loc[2, "high"] >= clean_df.loc[2, "close"]
    assert clean_df.loc[3, "low"] <= clean_df.loc[3, "open"]
    assert clean_df.loc[4, "volume"] == 0.0


def test_validator_strict_mode_raises_on_ohlcv_anomalies(make_synthetic_candles):
    validator = CandleValidator()
    df = make_synthetic_candles(start="2024-01-01", periods=5, freq="1h")
    df.loc[0, "high"] = 10.0  # anomaly

    with pytest.raises(ValidationError, match="anomalías lógicas"):
        validator.validate(df, interval="1h", strict=True)


def test_validator_handles_nan_values(make_synthetic_candles):
    validator = CandleValidator()
    df = make_synthetic_candles(start="2024-01-01", periods=10, freq="1h")
    df.loc[1, "close"] = np.nan

    # In repair mode, drops the NaN row
    clean_df, report = validator.validate(df, interval="1h", repair=True)
    assert len(clean_df) == 9
    assert report.ohlcv_anomalies_count == 1


def test_validator_strict_mode_raises_on_nan(make_synthetic_candles):
    validator = CandleValidator()
    df = make_synthetic_candles(start="2024-01-01", periods=5, freq="1h")
    df.loc[0, "open"] = np.nan

    with pytest.raises(ValidationError, match="valores NaN"):
        validator.validate(df, interval="1h", strict=True)


def test_validator_unsupported_interval_raises_value_error(make_synthetic_candles):
    validator = CandleValidator()
    df = make_synthetic_candles(periods=5)
    with pytest.raises(ValueError, match="Intervalo '99h' no soportado"):
        validator.validate(df, interval="99h")


def test_validator_missing_columns_raises_value_error():
    validator = CandleValidator()
    df = pd.DataFrame({"timestamp": [1, 2], "open": [10, 11]})
    with pytest.raises(ValueError, match="Faltan columnas"):
        validator.validate(df, interval="1h")


def test_validator_empty_df_returns_empty():
    validator = CandleValidator()
    clean_df, report = validator.validate(pd.DataFrame(), interval="1h")
    assert clean_df.empty
    assert report.total_candles == 0
    assert report.is_clean is True
