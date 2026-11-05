"""v3.1 market summary. Expected numbers are worked by hand from the stated bars."""

from __future__ import annotations

import pandas as pd
import pytest

from src.constants import (
    PROFILE_ABOVE_VALUE_AREA,
    VOLUME_ABOVE_AVERAGE,
)
from src.daily_summary import (
    atr_percentile,
    build_market_summary,
    format_price,
    market_conditions,
)
from src.regime_classifier import MarketRegime


def _df(n=100, spread=None):
    # 1h bars: close 100 flat except the last, ATR 1 flat except the last (2).
    close = [100.0] * (n - 1) + [103.0]
    atr = [1.0] * (n - 1) + [2.0]
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-11-01", periods=n, freq="1h", tz="UTC"),
            "close": close,
            "atr": atr,
        }
    )
    if spread is not None:
        df["spread"] = spread
    return df


ANALYSIS = {
    "profile": PROFILE_ABOVE_VALUE_AREA,
    "volume": VOLUME_ABOVE_AVERAGE,
}
PROFILE = {"poc": 100.0, "vah": 101.0, "val": 99.0}


def _summary(df):
    return build_market_summary(
        "BTCUSDT", df, ANALYSIS, PROFILE, MarketRegime.TRENDING_BULL
    )


def test_format_price():
    assert format_price(103.0) == "103.00"
    assert format_price(1.08123) == "1.08123"


def test_atr_percentile_counts_prior_bars_below_current():
    # ATR% 1.0 for 99 bars, then 2/103 = 1.94%: above all 99 prior values.
    assert atr_percentile(_df()) == pytest.approx(100.0)


def test_atr_percentile_uses_only_the_last_300_bars():
    df = _df(400)
    df.loc[0:50, "atr"] = 50.0  # outside the window, must not count
    assert atr_percentile(df) == pytest.approx(100.0)


def test_atr_percentile_unavailable_with_little_history():
    assert atr_percentile(_df(20)) is None


def test_summary_figures():
    s = _summary(_df())
    # 24h before the last bar closed at 100: (103-100)/100 = +3.00%.
    assert s["figures"]["change_24h_pct"] == pytest.approx(3.0)
    assert s["figures"]["atr_pct"] == pytest.approx(2 / 103 * 100)
    assert s["figures"]["spread_pct"] is None
    text = " ".join(s["lines"])
    assert "+3.00 %" in text
    assert "más agitado de lo normal" in text
    assert "por encima de su zona de valor" in text


def test_change_is_omitted_without_24h_of_history():
    s = _summary(_df(10))
    assert s["figures"]["change_24h_pct"] is None
    assert "24 h" not in " ".join(s["lines"])


def test_spread_is_reported_as_percent_of_price():
    # 0.103 on 103 = 0.100%.
    s = _summary(_df(spread=0.103))
    assert s["figures"]["spread_pct"] == pytest.approx(0.1)
    assert "0.100 %" in " ".join(s["lines"])


def test_no_action_words():
    text = " ".join(_summary(_df())["lines"]).lower()
    for word in ("compra", "vende", "oportunidad", "entra "):
        assert word not in text


def _conditions_df(atr_last=1.0, spread_last=None, n=100):
    # ATR% cycles 0.5..1.5 so the last value can sit low, mid or high.
    atr = [0.5 + (i % 11) * 0.1 for i in range(n - 1)] + [atr_last]
    df = pd.DataFrame({"close": [100.0] * n, "atr": atr})
    if spread_last is not None:
        df["spread"] = [0.01] * (n - 1) + [spread_last]
    return df


def test_conditions_green_when_nothing_is_elevated():
    # ATR 1.0 sits mid-cycle: about half the prior values are below it.
    c = market_conditions(_conditions_df(1.0))
    assert c["level"] == "VERDE"
    assert c["spread_checked"] is False


def test_conditions_yellow_with_high_volatility():
    assert market_conditions(_conditions_df(9.0))["level"] == "AMARILLO"


def test_conditions_red_when_volatility_and_spread_are_both_elevated():
    # ATR 9: above all prior. Spread/ATR 2/9 = 0.22: above all prior (max 0.02).
    c = market_conditions(_conditions_df(9.0, spread_last=2.0))
    assert c["level"] == "ROJO"
    assert c["spread_checked"] is True


def test_conditions_yellow_with_only_spread_elevated():
    assert (
        market_conditions(_conditions_df(1.0, spread_last=2.0))["level"] == "AMARILLO"
    )


def test_conditions_unavailable_with_little_history():
    assert market_conditions(_conditions_df(n=20))["level"] == "NO_DISPONIBLE"


def test_conditions_text_never_suggests_action():
    text = market_conditions(_conditions_df(9.0, spread_last=2.0))["text"].lower()
    for word in ("compra", "vende", "oportunidad"):
        assert word not in text
