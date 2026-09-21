from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from src.streaming.market_validator import (
    CheckResult,
    RealMarketValidator,
    ValidationReport,
)


def _generate_valid_df(bars: int = 250) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=bars, freq="1h", tz="UTC")
    base = 50000.0
    return pd.DataFrame({
        "timestamp": dates,
        "open": base + np.arange(bars) * 10,
        "high": base + np.arange(bars) * 10 + 50,
        "low": base + np.arange(bars) * 10 - 50,
        "close": base + np.arange(bars) * 10 + 20,
        "volume": np.full(bars, 100.0),
    })


def test_validator_non_autonomous_safety():
    validator = RealMarketValidator()
    check = validator.check_non_autonomous_safety()
    assert check.status == "PASS"
    assert "Zero automated trading" in check.message


def test_validator_non_autonomous_safety_detects_prohibited():
    validator = RealMarketValidator()
    with patch("builtins.__import__", return_value=MagicMock()):
        check = validator.check_non_autonomous_safety()
        assert check.status == "FAIL"


def test_validator_exchange_connectivity_success():
    validator = RealMarketValidator(timeout_sec=2.0)

    mock_ping_resp = MagicMock()
    mock_ping_resp.status = 200
    mock_ping_resp.__enter__.return_value = mock_ping_resp

    mock_time_resp = MagicMock()
    mock_time_resp.status = 200
    mock_time_resp.read.return_value = json.dumps({"serverTime": 1700000000000}).encode("utf-8")
    mock_time_resp.__enter__.return_value = mock_time_resp

    with patch("urllib.request.urlopen", side_effect=[mock_ping_resp, mock_time_resp]):
        with patch("time.time", return_value=1700000000.1):  # 100ms drift
            check = validator.check_exchange_connectivity()
            assert check.status == "PASS"
            assert check.details["drift_ms"] < 2000


def test_validator_exchange_connectivity_clock_drift_warn():
    validator = RealMarketValidator(timeout_sec=2.0)

    mock_ping_resp = MagicMock()
    mock_ping_resp.status = 200
    mock_ping_resp.__enter__.return_value = mock_ping_resp

    mock_time_resp = MagicMock()
    mock_time_resp.status = 200
    mock_time_resp.read.return_value = json.dumps({"serverTime": 1700000000000}).encode("utf-8")
    mock_time_resp.__enter__.return_value = mock_time_resp

    with patch("urllib.request.urlopen", side_effect=[mock_ping_resp, mock_time_resp]):
        with patch("time.time", return_value=1700000005.0):  # 5000ms drift
            check = validator.check_exchange_connectivity()
            assert check.status == "WARN"
            assert check.details["drift_ms"] == 5000


def test_validator_exchange_connectivity_failure():
    validator = RealMarketValidator(timeout_sec=2.0)
    with patch("urllib.request.urlopen", side_effect=RuntimeError("Connection refused")):
        check = validator.check_exchange_connectivity()
        assert check.status == "FAIL"


def test_validator_market_data_ingestion_valid():
    validator = RealMarketValidator()
    mock_loader = MagicMock()
    mock_df = _generate_valid_df(bars=250)
    mock_loader.get_klines.return_value = mock_df

    check, df = validator.check_market_data_ingestion(loader=mock_loader)
    assert check.status == "PASS"
    assert df is not None
    assert len(df) == 250


def test_validator_market_data_ingestion_insufficient_or_invalid():
    validator = RealMarketValidator()
    mock_loader = MagicMock()

    # Insufficient bars
    mock_loader.get_klines.return_value = _generate_valid_df(bars=30)
    check, df = validator.check_market_data_ingestion(loader=mock_loader)
    assert check.status == "FAIL"
    assert df is None

    # Invalid OHLC (high < low)
    bad_df = _generate_valid_df(bars=100)
    bad_df.loc[0, "high"] = 1000.0
    bad_df.loc[0, "low"] = 2000.0
    mock_loader.get_klines.return_value = bad_df
    check_bad, df_bad = validator.check_market_data_ingestion(loader=mock_loader)
    assert check_bad.status == "FAIL"
    assert df_bad is None

    # Exception
    mock_loader.get_klines.side_effect = RuntimeError("API rate limit exceeded")
    check_err, df_err = validator.check_market_data_ingestion(loader=mock_loader)
    assert check_err.status == "FAIL"
    assert df_err is None


def test_validator_quantitative_pipeline_and_persistence():
    validator = RealMarketValidator(db_path=":memory:")
    df = _generate_valid_df(bars=250)

    pipe_check, sig_event = validator.check_quantitative_pipeline(df)
    assert pipe_check.status == "PASS"
    assert sig_event is not None
    assert sig_event.symbol == "BTCUSDT"

    persist_check = validator.check_persistence_and_copilot(sig_event)
    assert persist_check.status == "PASS"
    assert persist_check.details.get("disclaimer_present") is True


def test_validator_run_full_validation_flow():
    validator = RealMarketValidator(db_path=":memory:")
    mock_loader = MagicMock()
    mock_loader.get_klines.return_value = _generate_valid_df(bars=250)

    report = validator.run_full_validation(loader=mock_loader, dry_run=True)
    assert report.overall_status == "PASS"
    assert len(report.checks) == 5
    d = report.to_dict()
    assert d["overall_status"] == "PASS"
    assert len(d["checks"]) == 5


def test_validator_exchange_ping_http_error():
    validator = RealMarketValidator(timeout_sec=2.0)
    mock_ping_resp = MagicMock()
    mock_ping_resp.status = 502
    mock_ping_resp.__enter__.return_value = mock_ping_resp

    with patch("urllib.request.urlopen", return_value=mock_ping_resp):
        check = validator.check_exchange_connectivity()
        assert check.status == "FAIL"
        assert "502" in check.message


def test_validator_quantitative_pipeline_error():
    validator = RealMarketValidator(db_path=":memory:")
    with patch("src.streaming.market_validator.TechnicalIndicators", side_effect=RuntimeError("Pipeline crash")):
        check, sig = validator.check_quantitative_pipeline(pd.DataFrame())
        assert check.status == "FAIL"
        assert sig is None


def test_validator_persistence_read_back_none_and_exceptions():
    validator = RealMarketValidator(db_path=":memory:")
    sig = MagicMock()
    sig.price = 50000.0

    # Read back None
    with patch("src.streaming.market_validator.ContextBuilder.build_from_signal_event"):
        with patch.object(validator, "check_persistence_and_copilot") as mock_persist:
            mock_persist.return_value = CheckResult(
                name="persistence_and_copilot",
                status="FAIL",
                message="Failed to read back saved market context from SQLite",
            )
            res = validator.check_persistence_and_copilot(sig)
            assert res.status == "FAIL"

    # Exception during persistence
    with patch("src.streaming.market_validator.ContextBuilder.build_from_signal_event", side_effect=RuntimeError("Storage crash")):
        res_err = validator.check_persistence_and_copilot(sig)
        assert res_err.status == "FAIL"
        assert "Storage crash" in res_err.message


def test_validator_copilot_missing_disclaimer_warn():
    validator = RealMarketValidator(db_path=":memory:")
    mock_sig = MagicMock()
    mock_sig.symbol = "BTCUSDT"
    mock_sig.timeframe = "1h"
    mock_sig.price = 50000.0
    mock_sig.metadata = {}

    mock_resp = MagicMock()
    mock_resp.disclaimer = ""
    mock_resp.answer = "Explanation text"

    with patch("src.streaming.market_validator.ContextBuilder.build_from_signal_event"):
        with patch("src.streaming.market_validator.SQLiteMarketContextProvider"):
            with patch("src.streaming.market_validator.OperatorAssistant.ask", return_value=mock_resp):
                check = validator.check_persistence_and_copilot(mock_sig)
                assert check.status == "WARN"


def test_validator_run_full_validation_missing_data_branches():
    validator = RealMarketValidator(db_path=":memory:")
    mock_loader = MagicMock()
    mock_loader.get_klines.return_value = pd.DataFrame()  # empty

    report = validator.run_full_validation(loader=mock_loader, dry_run=True)
    assert report.overall_status == "FAIL"


def test_scripts_validate_live_deployment_main():
    from datetime import datetime, timezone

    from scripts.validate_live_deployment import main as val_main

    with patch("sys.argv", ["validate_live_deployment.py", "--dry-run"]):
        with patch("src.streaming.market_validator.RealMarketValidator.run_full_validation") as mock_run:
            mock_run.return_value = ValidationReport(
                timestamp=datetime.now(timezone.utc),
                overall_status="PASS",
                checks=[],
                summary="All checks passed.",
            )
            rc = val_main()
            assert rc == 0

    # Test JSON output mode
    with patch("sys.argv", ["validate_live_deployment.py", "--dry-run", "--json"]):
        with patch("src.streaming.market_validator.RealMarketValidator.run_full_validation") as mock_run:
            mock_run.return_value = ValidationReport(
                timestamp=datetime.now(timezone.utc),
                overall_status="WARN",
                checks=[],
                summary="Checks passed with warning.",
            )
            rc_json = val_main()
            assert rc_json == 0


