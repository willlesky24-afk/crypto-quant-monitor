from __future__ import annotations

from src.engine import MarketEngine
from src.indicators import TechnicalIndicators
from src.volume_profile import VolumeProfile
from tests.unit.test_report import make_history, make_report


def test_complete_v16_pipeline_is_offline_and_deterministic(
    tmp_path, synthetic_ohlcv
):
    assert len(synthetic_ohlcv) >= 240
    enriched = TechnicalIndicators().calculate_all(synthetic_ohlcv.copy())
    profile = VolumeProfile().calculate(enriched)
    analysis = MarketEngine().analyze(enriched, profile)

    history = make_history(tmp_path)
    report_engine = make_report(history)
    db_path = tmp_path / "report.db"
    try:
        first = report_engine.generate("BTCUSDT", analysis, profile)
        assert first["symbol"] == "BTCUSDT"
        assert first["price"] == analysis["price"]
        # Generate is pure
        assert len(history.get_history()) == 0

        # Explicit persistence per closed candle
        latest_candle = enriched.iloc[-1]
        saved = history.save(
            symbol="BTCUSDT",
            analysis=analysis,
            decision=first["decision"],
            quant_score=first["quant_score"],
            risk=first["risk_engine"],
            signal=first["signal"],
            timeframe="1h",
            candle_timestamp=str(latest_candle["timestamp"]),
            open=float(latest_candle["open"]),
            high=float(latest_candle["high"]),
            low=float(latest_candle["low"]),
            close=float(latest_candle["close"]),
            volume=float(latest_candle["volume"]),
        )
        assert saved["inserted"] is True
        assert len(history.get_history()) == 1

        # The analytical stages are deterministic for the same closed candles.
        second_profile = VolumeProfile().calculate(enriched)
        second_analysis = MarketEngine().analyze(enriched, second_profile)
        assert second_profile == profile
        assert second_analysis == analysis
        assert db_path.exists()
    finally:
        history.db.connection.close()


