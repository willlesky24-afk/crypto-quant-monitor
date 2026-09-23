from __future__ import annotations

from datetime import datetime, timezone

from src.forex_data_loader import FOREX_PAIRS, ForexDataLoader
from src.forex_sessions import get_forex_session_status


def test_forex_pairs_catalog():
    assert len(FOREX_PAIRS) >= 7
    assert any("EUR / USD" in k for k in FOREX_PAIRS)
    assert any("GBP / USD" in k for k in FOREX_PAIRS)
    assert any("USD / JPY" in k for k in FOREX_PAIRS)


def test_forex_data_loader_df_structure():
    loader = ForexDataLoader()
    df = loader.get_forex_klines(symbol="EURUSD=X", interval="1h", limit=50)
    assert not df.empty
    assert len(df) <= 50
    expected_cols = {"timestamp", "open", "high", "low", "close", "volume"}
    assert expected_cols.issubset(set(df.columns))
    assert df["close"].iloc[-1] > 0.0


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
