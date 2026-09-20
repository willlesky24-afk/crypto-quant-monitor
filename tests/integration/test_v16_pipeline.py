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
        assert len(history.get_history()) == 1

        # The analytical stages are deterministic for the same closed candles.
        second_profile = VolumeProfile().calculate(enriched)
        second_analysis = MarketEngine().analyze(enriched, second_profile)
        assert second_profile == profile
        assert second_analysis == analysis
        assert db_path.exists()
    finally:
        history.db.connection.close()

