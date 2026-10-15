from dataclasses import replace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.notifications.models import SignalEvent
from src.notifications.tracker import AlertOutcomeTracker


@pytest.fixture
def temp_tracker(tmp_path, monkeypatch):
    db_file = tmp_path / "test_alerts.db"
    monkeypatch.setattr(
        AlertOutcomeTracker,
        "_now_utc",
        staticmethod(lambda: pd.Timestamp("2026-09-23 10:00:00", tz="UTC")),
    )
    return AlertOutcomeTracker(db_path=db_file)


def make_signal(**changes):
    signal = SignalEvent(
        timestamp=pd.Timestamp("2026-09-23 10:00:00", tz="UTC"),
        symbol="BTCUSDT",
        timeframe="1h",
        action="BUY",
        direction="LONG",
        confidence=0.9,
        predictive_score=0.8,
        regime="TRENDING_BULL",
        reasoning="Fixture",
        price=60000.0,
        quant_score=90.0,
        stop_loss=59000.0,
        take_profit=62000.0,
        signal_id="verified-fixture",
        metadata={"signal_status": "ACTIVADA"},
    )
    return replace(signal, **changes)


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
    assert rec["risk_integrity_status"] == "VALIDATED"
    assert rec["risk_reward"] == pytest.approx(2.0)

    alerts = temp_tracker.get_all_alerts()
    assert len(alerts) == 1
    assert alerts[0]["symbol"] == "EURUSD=X"
    assert alerts[0]["entry_price"] == 1.0800
    assert alerts[0]["risk_integrity_status"] == "VALIDATED"


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
    assert alerts[0]["risk_reward"] == 2.0  # Plan, distinct from observed result.
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
        {"timestamp": pd.Timestamp("2026-09-23 11:00:00", tz="UTC"), "open": 3000.0, "high": 3150.0, "low": 2980.0, "close": 3120.0},
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


@pytest.mark.parametrize("missing_field", ["stop_loss", "take_profit"])
def test_missing_levels_are_rejected_without_fallback(temp_tracker, missing_field):
    signal = make_signal(**{missing_field: None})
    with pytest.raises(ValueError, match="Faltan entrada, Stop Loss o Take Profit"):
        temp_tracker.record_alert(signal, risk_reward=2.0)
    assert temp_tracker.get_all_alerts() == []


@pytest.mark.parametrize("reported_r", [None, 0.0, 1.5, float("nan"), float("inf")])
def test_missing_or_incorrect_r_is_rejected(temp_tracker, reported_r):
    with pytest.raises(ValueError, match="R bruto válido|R reportado no coincide"):
        temp_tracker.record_alert(make_signal(), risk_reward=reported_r)
    assert temp_tracker.get_all_alerts() == []


@pytest.mark.parametrize(
    "changes",
    [
        {"action": "WAIT"},
        {"action": "SELL"},
        {"direction": "SHORT"},
        {"metadata": {"signal_status": "CANDIDATA"}},
        {"metadata": {"signal_status": "ACTIVADA", "entry_confirmed": False}},
        {"metadata": {"signal_status": "ACTIVADA", "risk_reward_ratio": 3.0}},
    ],
)
def test_non_operable_or_inconsistent_alert_is_rejected(temp_tracker, changes):
    with pytest.raises(ValueError, match="Alerta no operable"):
        temp_tracker.record_alert(make_signal(**changes), risk_reward=2.0)
    assert temp_tracker.get_all_alerts() == []


def test_only_candles_after_recording_can_resolve_alert(temp_tracker, monkeypatch):
    monkeypatch.setattr(
        temp_tracker,
        "_now_utc",
        lambda: pd.Timestamp("2026-09-23 10:30:00", tz="UTC"),
    )
    temp_tracker.record_alert(make_signal(), risk_reward=2.0)
    loader = MagicMock()
    loader.get_klines.return_value = pd.DataFrame([
        {"timestamp": pd.Timestamp("2026-09-23 10:15:00", tz="UTC"), "high": 62500, "low": 60000, "close": 62200},
        {"timestamp": pd.Timestamp("2026-09-23 10:30:00", tz="UTC"), "high": 62500, "low": 60000, "close": 62200},
    ])
    assert temp_tracker.update_alert_outcomes(crypto_loader=loader) == 0
    assert temp_tracker.get_all_alerts()[0]["status"] == "OPEN"

    loader.get_klines.return_value = pd.DataFrame([
        {"timestamp": pd.Timestamp("2026-09-23 11:00:00", tz="UTC"), "high": 62500, "low": 60000, "close": 62200},
    ])
    assert temp_tracker.update_alert_outcomes(crypto_loader=loader) == 1
    row = temp_tracker.get_all_alerts()[0]
    assert row["status"] == "WIN"
    assert row["risk_reward"] == 2.0
    assert row["r_multiple"] == 2.0


def test_missing_candle_timestamps_cannot_resolve_alert(temp_tracker):
    temp_tracker.record_alert(make_signal(), risk_reward=2.0)
    loader = MagicMock()
    loader.get_klines.return_value = pd.DataFrame([
        {"high": 62500, "low": 60000, "close": 62200},
    ])
    assert temp_tracker.update_alert_outcomes(crypto_loader=loader) == 0
    assert temp_tracker.get_all_alerts()[0]["status"] == "OPEN"


def test_planned_r_and_observed_floating_r_stay_separate(temp_tracker):
    temp_tracker.record_alert(make_signal(), risk_reward=2.0)
    loader = MagicMock()
    loader.get_klines.return_value = pd.DataFrame([
        {"timestamp": pd.Timestamp("2026-09-23 11:00:00", tz="UTC"), "high": 60700, "low": 60000, "close": 60500},
    ])
    assert temp_tracker.update_alert_outcomes(crypto_loader=loader) == 1
    row = temp_tracker.get_all_alerts()[0]
    assert row["status"] == "OPEN"
    assert row["risk_reward"] == 2.0
    assert row["r_multiple"] == pytest.approx(0.5)


def test_legacy_rows_are_preserved_classified_and_excluded_from_stats(temp_tracker):
    with temp_tracker._get_connection() as conn:
        conn.execute(
            """INSERT INTO dispatched_alerts (
                id, timestamp, symbol, direction, timeframe, entry_price,
                stop_loss, take_profit, quant_score, risk_reward, status,
                current_or_exit_price, exit_time, pnl_percent, r_multiple, is_forex
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "legacy-01", "2026-09-22 10:00:00", "BTCUSDT", "LONG", "1h",
                60000.0, 58800.0, 62400.0, 90.0, 2.0, "WIN",
                62400.0, "2026-09-22 11:00:00", 4.0, 2.0, 0,
            ),
        )
        before = tuple(conn.execute("SELECT * FROM dispatched_alerts WHERE id = 'legacy-01'").fetchone())

    row = temp_tracker.get_all_alerts()[0]
    assert row["risk_integrity_status"] == "LEGACY_UNVERIFIED"
    assert row["risk_integrity_reason"]
    stats = temp_tracker.compute_statistics()
    assert stats["total_alerts"] == 0
    assert stats["wins"] == 0
    assert stats["total_r"] == 0.0
    assert stats["all_recorded_alerts"] == 1
    assert stats["excluded_unverified_alerts"] == 1
    with temp_tracker._get_connection() as conn:
        after = tuple(conn.execute("SELECT * FROM dispatched_alerts WHERE id = 'legacy-01'").fetchone())
        assert conn.execute("SELECT COUNT(*) FROM validated_alert_plans").fetchone()[0] == 0
    assert after == before


def test_legacy_open_alert_is_never_evaluated_or_revalidated_on_duplicate(temp_tracker):
    with temp_tracker._get_connection() as conn:
        conn.execute(
            """INSERT INTO dispatched_alerts (
                id, timestamp, symbol, direction, timeframe, entry_price,
                stop_loss, take_profit, quant_score, risk_reward, status,
                current_or_exit_price, exit_time, pnl_percent, r_multiple, is_forex
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "verified-fixture", "2026-09-23 10:00:00", "BTCUSDT", "LONG", "1h",
                60000.0, 59000.0, 62000.0, 90.0, 2.0, "OPEN",
                60000.0, None, 0.0, 0.0, 0,
            ),
        )
    duplicate = temp_tracker.record_alert(make_signal(), risk_reward=2.0)
    assert duplicate["risk_integrity_status"] == "LEGACY_UNVERIFIED"
    loader = MagicMock()
    loader.get_klines.return_value = pd.DataFrame([
        {"timestamp": pd.Timestamp("2026-09-23 11:00:00", tz="UTC"), "high": 62500, "low": 60000, "close": 62200},
    ])
    assert temp_tracker.update_alert_outcomes(crypto_loader=loader) == 0
    loader.get_klines.assert_not_called()
    row = temp_tracker.get_all_alerts()[0]
    assert row["status"] == "OPEN"
    assert row["risk_integrity_status"] == "LEGACY_UNVERIFIED"
    with temp_tracker._get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM validated_alert_plans").fetchone()[0] == 0


def test_invalid_persisted_plan_is_not_evaluated_or_counted(temp_tracker):
    temp_tracker.record_alert(make_signal(), risk_reward=2.0)
    with temp_tracker._get_connection() as conn:
        conn.execute("UPDATE dispatched_alerts SET risk_reward = 99 WHERE id = ?", ("verified-fixture",))
    row = temp_tracker.get_all_alerts()[0]
    assert row["risk_integrity_status"] == "INVALID_PLAN"
    assert temp_tracker.compute_statistics()["excluded_unverified_alerts"] == 1
    loader = MagicMock()
    loader.get_klines.return_value = pd.DataFrame([
        {"timestamp": pd.Timestamp("2026-09-23 11:00:00", tz="UTC"), "high": 62500, "low": 60000, "close": 62200},
    ])
    assert temp_tracker.update_alert_outcomes(crypto_loader=loader) == 0
    loader.get_klines.assert_not_called()
    assert temp_tracker.get_all_alerts()[0]["status"] == "OPEN"
