from __future__ import annotations

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
    )
    d = res.to_dict()
    assert d["symbol"] == "BTCUSDT"
    assert d["quant_score"] == 85.0
    assert d["confidence"] == 90.0


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
    )
    summary = scanner.format_scanner_summary_es([res])
    assert "SOLUSDT" in summary
    assert "MEJOR escenario" in summary
    assert "Puntaje Cuantitativo" in summary


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
        assert r.direction in ("LONG", "SHORT", "NEUTRAL")
