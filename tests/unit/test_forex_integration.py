from __future__ import annotations

import copy
import json
import urllib.error
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.forex_data_loader import (
    FOREX_PAIRS,
    ForexDataLoader,
    ForexInvalidDataError,
    ForexProviderUnavailableError,
)
from src.forex_sessions import get_forex_session_status
from src.market_scanner import MarketScanner
from src.notifications.models import SignalEvent
from src.notifications.tracker import AlertOutcomeTracker


@pytest.fixture
def forex_payload():
    return {
        "chart": {
            "result": [
                {
                    "timestamp": [1790071200, 1790074800],
                    "indicators": {
                        "quote": [
                            {
                                "open": [1.08, 1.081],
                                "high": [1.083, 1.084],
                                "low": [1.079, 1.080],
                                "close": [1.082, 1.083],
                                "volume": [0, 120],
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }


def mock_provider_response(monkeypatch, payload):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(payload).encode(
        "utf-8"
    )
    urlopen = MagicMock(return_value=response)
    monkeypatch.setattr("src.forex_data_loader.urllib.request.urlopen", urlopen)
    return urlopen


def test_forex_pairs_catalog():
    assert len(FOREX_PAIRS) >= 7
    assert any("EUR / USD" in k for k in FOREX_PAIRS)
    assert any("GBP / USD" in k for k in FOREX_PAIRS)
    assert any("USD / JPY" in k for k in FOREX_PAIRS)


def test_forex_data_loader_returns_only_provider_candles(monkeypatch, forex_payload):
    urlopen = mock_provider_response(monkeypatch, forex_payload)
    loader = ForexDataLoader()
    df = loader.get_forex_klines(symbol="EUR/USD", interval="1h", limit=50)
    assert len(df) == 2
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert df["close"].tolist() == [1.082, 1.083]
    assert df["volume"].tolist() == [0.0, 120.0]
    assert str(df["timestamp"].dt.tz) == "UTC"
    assert "EURUSD=X" in urlopen.call_args.args[0].full_url


def test_forex_http_error_is_explicit(monkeypatch):
    error = urllib.error.HTTPError(
        "https://example.invalid", 503, "unavailable", {}, None
    )
    monkeypatch.setattr(
        "src.forex_data_loader.urllib.request.urlopen", MagicMock(side_effect=error)
    )

    with pytest.raises(ForexProviderUnavailableError, match="EURUSD=X") as exc_info:
        ForexDataLoader().get_forex_klines(symbol="EURUSD=X")
    assert exc_info.value.__cause__ is error


def test_forex_timeout_is_explicit(monkeypatch):
    monkeypatch.setattr(
        "src.forex_data_loader.urllib.request.urlopen",
        MagicMock(side_effect=TimeoutError("timed out")),
    )

    with pytest.raises(ForexProviderUnavailableError, match="EURUSD=X"):
        ForexDataLoader().get_klines(symbol="EURUSD=X")


@pytest.mark.parametrize(
    "empty_result", [[], [{"timestamp": [], "indicators": {"quote": [{}]}}]]
)
def test_forex_empty_response_is_invalid(monkeypatch, forex_payload, empty_result):
    payload = copy.deepcopy(forex_payload)
    payload["chart"]["result"] = empty_result
    mock_provider_response(monkeypatch, payload)

    with pytest.raises(ForexInvalidDataError):
        ForexDataLoader().get_forex_klines(symbol="EURUSD=X")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("open", None),
        ("close", float("inf")),
        ("high", 1.07),
        ("volume", None),
    ],
)
def test_forex_invalid_candle_is_rejected(monkeypatch, forex_payload, field, value):
    payload = copy.deepcopy(forex_payload)
    payload["chart"]["result"][0]["indicators"]["quote"][0][field][0] = value
    mock_provider_response(monkeypatch, payload)

    with pytest.raises(ForexInvalidDataError, match="EURUSD=X"):
        ForexDataLoader().get_forex_klines(symbol="EURUSD=X")


def test_forex_provider_failure_cannot_reach_scanner_signal_engine(monkeypatch):
    monkeypatch.setattr(
        "src.forex_data_loader.urllib.request.urlopen",
        MagicMock(side_effect=TimeoutError("timed out")),
    )
    scanner = MarketScanner(data_loader=ForexDataLoader())
    scanner.signal_engine.evaluate = MagicMock()

    assert scanner.scan_market(symbols=["EURUSD=X"]) == []
    scanner.signal_engine.evaluate.assert_not_called()


def test_forex_provider_failure_leaves_alert_open(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "src.forex_data_loader.urllib.request.urlopen",
        MagicMock(side_effect=TimeoutError("timed out")),
    )
    tracker = AlertOutcomeTracker(db_path=tmp_path / "alerts.db")
    signal = SignalEvent(
        timestamp=pd.Timestamp("2026-09-23 10:00:00", tz="UTC"),
        symbol="EURUSD=X",
        timeframe="1h",
        action="BUY",
        direction="LONG",
        confidence=0.8,
        predictive_score=0.8,
        regime="TRENDING_BULL",
        reasoning="Recorded before the provider outage",
        price=1.08,
        quant_score=80.0,
        stop_loss=1.07,
        take_profit=1.09,
        signal_id="forex-outage-01",
    )
    tracker.record_alert(signal, is_forex=True, risk_reward=2.0)

    assert (
        tracker.update_alert_outcomes(
            forex_loader=ForexDataLoader(), crypto_loader=MagicMock()
        )
        == 0
    )
    assert tracker.get_all_alerts()[0]["status"] == "OPEN"


def test_forex_sessions_logic():
    # Test Saturday (closed)
    sat = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
    status_sat = get_forex_session_status(sat)
    assert status_sat.is_market_open is False
    assert "Cerrado" in status_sat.status_headline

    # Test Tuesday during London - NY overlap (14:00 UTC)
    tue = datetime(2026, 9, 22, 14, 0, tzinfo=timezone.utc)
    status_tue = get_forex_session_status(tue)
    assert status_tue.is_market_open is True
    assert "Solapamiento" in status_tue.status_headline
    assert "🇬🇧 Sesión Londres" in status_tue.active_sessions
    assert "🇺🇸 Sesión Nueva York" in status_tue.active_sessions
