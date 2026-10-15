from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.constants import DECISION_FAVORABLE, DECISION_WAIT_CONFIRMATION
from src.market_scanner import MarketScanner, ScannedPairResult


def test_scanned_pair_result_to_dict():
    res = ScannedPairResult(
        symbol="BTCUSDT",
        price=65000.0,
        regime="TRENDING_BULL",
        action="BUY",
        direction="LONG",
        quant_score=85.0,
        predictive_score=0.80,
        confidence=0.90,
        risk_reward=2.5,
        stop_loss=63000.0,
        take_profit=70000.0,
        primary_reason="POC Breakout",
        ranking_score=82.5,
        timeframe="1h",
        status="CANDIDATA",
        entry_price=65000.0,
        risk_distance=2000.0,
        reward_distance=5000.0,
        risk_methodology="ATR",
    )
    d = res.to_dict()
    assert d["symbol"] == "BTCUSDT"
    assert d["quant_score"] == 85.0
    assert d["confidence"] == 90.0
    assert d["risk_reward"] == 2.5
    assert d["risk_reward_basis"] == "bruto_sin_costes"
    assert d["stop_loss"] == 63000.0
    assert d["status"] == "CANDIDATA"
    assert res.is_operable() is False


def test_market_scanner_format_summary_es():
    scanner = MarketScanner()
    empty_summary = scanner.format_scanner_summary_es([])
    assert "No se pudieron obtener datos" in empty_summary

    res = ScannedPairResult(
        symbol="SOLUSDT",
        price=150.0,
        regime="TRENDING_BULL",
        action="BUY",
        direction="LONG",
        quant_score=88.0,
        predictive_score=0.75,
        confidence=0.85,
        risk_reward=2.2,
        stop_loss=140.0,
        take_profit=172.0,
        primary_reason="Tendencia alcista con volumen",
        ranking_score=85.0,
        status="CANDIDATA",
        entry_price=150.0,
        risk_distance=10.0,
        reward_distance=22.0,
        risk_methodology="ATR",
        risk_reason="Entrada propuesta; falta confirmación.",
    )
    summary = scanner.format_scanner_summary_es([res])
    assert "SOLUSDT" in summary
    assert "Escenario técnico destacado" in summary
    assert "R bruto indicativo: 1:2.20" in summary
    assert "entrada no confirmada" in summary


def test_market_scanner_pipeline_integration():
    from unittest.mock import MagicMock

    import numpy as np
    import pandas as pd

    mock_loader = MagicMock()
    rng = np.random.default_rng(42)
    now = pd.Timestamp.now(tz="UTC")
    dates = [now - pd.Timedelta(hours=50 - i) for i in range(50)]
    closes = 100.0 + np.cumsum(rng.normal(0.1, 0.5, 50))
    sample_df = pd.DataFrame({
        "timestamp": dates,
        "open": closes - 0.2,
        "high": closes + 0.5,
        "low": closes - 0.5,
        "close": closes,
        "volume": rng.integers(100, 1000, 50),
    })
    mock_loader.get_klines.return_value = sample_df

    scanner = MarketScanner(data_loader=mock_loader)
    results = scanner.scan_market(symbols=["BTCUSDT", "ETHUSDT"])
    assert len(results) == 2
    for r in results:
        assert r.symbol in ("BTCUSDT", "ETHUSDT")
        assert r.price > 0
        assert r.quant_score >= 0.0
        assert r.confidence >= 0.0
        assert r.action != ""
        assert r.direction in ("LONG", "SHORT", "SIN OPERACIÓN")
        assert r.entry_confirmed is False
        assert r.is_operable() is False
        if r.status == "CANDIDATA":
            assert r.risk_reward == pytest.approx(r.reward_distance / r.risk_distance)
            assert r.entry_price == r.price
        else:
            assert r.risk_reward is None
            assert r.stop_loss is None
            assert r.take_profit is None


@pytest.mark.parametrize(
    ("decision_name", "expected_status"),
    [
        (DECISION_FAVORABLE, "CANDIDATA"),
        (DECISION_WAIT_CONFIRMATION, "ESPERANDO CONFIRMACIÓN"),
    ],
)
def test_scanner_reuses_risk_engine_plan_and_exposes_status(
    synthetic_ohlcv, decision_name, expected_status
):
    loader = MagicMock()
    loader.get_klines.return_value = synthetic_ohlcv.copy()
    scanner = MarketScanner(data_loader=loader)
    scanner.decision_engine.evaluate = MagicMock(return_value=SimpleNamespace(
        decision=decision_name,
        direction="SHORT",
        tp_multiplier=3.0,
        sl_multiplier=1.5,
        confidence=80.0,
    ))

    results = scanner.scan_market(symbols=["BTCUSDT"], timeframe="1h")

    assert len(results) == 1
    item = results[0]
    assert item.status == expected_status
    assert item.timeframe == "1h"
    assert item.entry_confirmed is False
    assert item.is_operable() is False
    if decision_name == DECISION_FAVORABLE:
        assert item.direction == "SHORT"
        assert item.stop_loss > item.entry_price > item.take_profit
        assert item.risk_reward == pytest.approx(
            (item.entry_price - item.take_profit) / (item.stop_loss - item.entry_price)
        )
        assert item.risk_reward == pytest.approx(item.reward_distance / item.risk_distance)
        assert "bruto" in scanner.format_scanner_summary_es(results)
    else:
        assert item.direction == "SIN OPERACIÓN"
        assert item.entry_price is None
        assert item.stop_loss is None
        assert item.take_profit is None
        assert item.risk_reward is None
        assert "No disponible" in scanner.format_scanner_summary_es(results)


def test_only_complete_confirmed_activated_result_is_operable():
    base = dict(
        symbol="BTCUSDT", price=100.0, regime="TRENDING_BULL",
        action="BUY", direction="LONG", quant_score=85.0,
        predictive_score=0.8, confidence=0.9, risk_reward=2.0,
        stop_loss=95.0, take_profit=110.0, primary_reason="ATR",
        ranking_score=80.0, status="ACTIVADA", entry_price=100.0,
        entry_confirmed=True, risk_distance=5.0, reward_distance=10.0,
        risk_methodology="ATR",
    )
    assert ScannedPairResult(**base).is_operable() is True
    assert ScannedPairResult(**{**base, "risk_reward": 1.5}).is_operable() is False
    assert ScannedPairResult(**{**base, "stop_loss": 101.0}).is_operable() is False
    assert ScannedPairResult(**{**base, "entry_confirmed": False}).is_operable() is False
