from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.notifications.models import SignalEvent
from src.notifications.tracker import AlertOutcomeTracker


@pytest.fixture
def temp_tracker(tmp_path):
    db_file = tmp_path / "test_alerts.db"
    return AlertOutcomeTracker(db_path=db_file)


def test_record_and_get_alert(temp_tracker):
    sig = SignalEvent(
        timestamp=pd.Timestamp("2026-09-23 10:00:00", tz="UTC"),
        symbol="EURUSD=X",
        timeframe="1h",
        action="BUY",
        direction="LONG",
        confidence=0.85,
        predictive_score=0.80,
        regime="TRENDING_BULL",
        reasoning="Test signal",
        price=1.0800,
        quant_score=85.0,
        stop_loss=1.0750,
        take_profit=1.0900,
        signal_id="sig-test-01",
    )

    rec = temp_tracker.record_alert(sig, is_forex=True, risk_reward=2.0)
    assert rec["id"] == "sig-test-01"
    assert rec["status"] == "OPEN"

    alerts = temp_tracker.get_all_alerts()
    assert len(alerts) == 1
    assert alerts[0]["symbol"] == "EURUSD=X"
    assert alerts[0]["entry_price"] == 1.0800


def test_evaluate_long_win(temp_tracker):
    sig = SignalEvent(
        timestamp=pd.Timestamp("2026-09-23 10:00:00", tz="UTC"),
        symbol="BTCUSDT",
        timeframe="1h",
        action="BUY",
        direction="LONG",
        confidence=0.90,
        predictive_score=0.85,
        regime="TRENDING_BULL",
        reasoning="Bull breakout",
        price=60000.0,
        quant_score=90.0,
        stop_loss=59000.0,
        take_profit=62000.0,
        signal_id="btc-win-01",
    )
    temp_tracker.record_alert(sig, is_forex=False, risk_reward=2.0)

    # Mock candles that hit TP
    mock_loader = MagicMock()
    mock_candles = pd.DataFrame([
        {"timestamp": pd.Timestamp("2026-09-23 10:00:00", tz="UTC"), "open": 60000.0, "high": 60500.0, "low": 59800.0, "close": 60400.0},
        {"timestamp": pd.Timestamp("2026-09-23 11:00:00", tz="UTC"), "open": 60400.0, "high": 62500.0, "low": 60300.0, "close": 62200.0},
    ])
    mock_loader.get_klines.return_value = mock_candles

    updated = temp_tracker.update_alert_outcomes(crypto_loader=mock_loader)
    assert updated == 1

    alerts = temp_tracker.get_all_alerts()
    assert alerts[0]["status"] == "WIN"
    assert alerts[0]["r_multiple"] == 2.0
    assert alerts[0]["current_or_exit_price"] == 62000.0

    stats = temp_tracker.compute_statistics()
    assert stats["win_rate"] == 100.0
    assert stats["wins"] == 1
    assert stats["losses"] == 0


def test_evaluate_short_loss(temp_tracker):
    sig = SignalEvent(
        timestamp=pd.Timestamp("2026-09-23 10:00:00", tz="UTC"),
        symbol="ETHUSDT",
        timeframe="1h",
        action="SELL",
        direction="SHORT",
        confidence=0.85,
        predictive_score=0.75,
        regime="TRENDING_BEAR",
        reasoning="Bear breakdown",
        price=3000.0,
        quant_score=80.0,
        stop_loss=3100.0,
        take_profit=2800.0,
        signal_id="eth-loss-01",
    )
    temp_tracker.record_alert(sig, is_forex=False, risk_reward=2.0)

    # Mock candles that hit SL
    mock_loader = MagicMock()
    mock_candles = pd.DataFrame([
        {"timestamp": pd.Timestamp("2026-09-23 10:00:00", tz="UTC"), "open": 3000.0, "high": 3150.0, "low": 2980.0, "close": 3120.0},
    ])
    mock_loader.get_klines.return_value = mock_candles

    updated = temp_tracker.update_alert_outcomes(crypto_loader=mock_loader)
    assert updated == 1

    alerts = temp_tracker.get_all_alerts()
    assert alerts[0]["status"] == "LOSS"
    assert alerts[0]["r_multiple"] == -1.0

    stats = temp_tracker.compute_statistics()
    assert stats["win_rate"] == 0.0
    assert stats["losses"] == 1
