"""Price and ATR keep their precision: forex moves in the 4th decimal."""

from __future__ import annotations

import pandas as pd
import pytest

from src.engine import MarketEngine
from src.risk_engine import RiskEngine
from src.signal_engine import SignalEngine

PROFILE = {"poc": 1.0810, "vah": 1.0830, "val": 1.0790}


def _analysis(price=1.0812, atr=0.0012):
    df = pd.DataFrame(
        [
            {
                "close": price,
                "rsi": 55.123,
                "atr": atr,
                "volume": 100.0,
                "volume_average": 50.0,
                "ema_50": 1.0805,
                "ema_200": 1.0800,
            }
        ]
    )
    return MarketEngine().analyze(df, PROFILE)


def test_price_and_atr_are_not_rounded():
    a = _analysis()
    assert a["price"] == pytest.approx(1.0812)
    assert a["atr"] == pytest.approx(0.0012)
    assert a["rsi"] == pytest.approx(55.12)


def test_forex_near_poc_is_not_flagged_as_far():
    # Distance 0.0002 is below 2 x ATR = 0.0024. Rounded, ATR was 0 and it flagged.
    risk = RiskEngine().evaluate(_analysis(), PROFILE)
    assert "Precio alejado del POC." not in risk["risks"]


def test_forex_far_from_poc_is_flagged():
    # Distance 0.0040 is above 2 x ATR = 0.0024.
    risk = RiskEngine().evaluate(_analysis(price=1.0850), PROFILE)
    assert "Precio alejado del POC." in risk["risks"]


def test_signal_engine_sees_price_above_vah_in_fourth_decimal():
    # 1.0834 is above VAH 1.0830 and 1.0812 is inside; rounding made both 1.08.
    above = SignalEngine().evaluate(_analysis(price=1.0834), PROFILE)
    inside = SignalEngine().evaluate(_analysis(price=1.0812), PROFILE)
    assert above != inside


def test_volume_profile_keeps_forex_precision():
    from src.volume_profile import VolumeProfile

    # Prices around 1.1234: rounded to 2 decimals every level would be 1.12.
    close = [1.1230 + 0.0001 * (i % 9) for i in range(60)]
    df = pd.DataFrame(
        {
            "high": [c + 0.0002 for c in close],
            "low": [c - 0.0002 for c in close],
            "close": close,
            "volume": [100.0] * 60,
        }
    )
    profile = VolumeProfile().calculate(df)
    assert profile["vah"] > profile["val"]
    assert round(profile["poc"], 2) != profile["poc"]
