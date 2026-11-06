"""v3.2 interface pieces: real values in, honest gaps shown, nothing injected."""

from __future__ import annotations

import pandas as pd
import pytest

from src.daily_summary import market_conditions
from src.ui_theme import (
    alert_row,
    bar_position,
    gauge_html,
    meter_card,
    value_area_position,
)


def test_value_area_position():
    assert value_area_position(100.0, 90.0, 110.0) == pytest.approx(50.0)
    assert value_area_position(85.0, 90.0, 110.0) == pytest.approx(-25.0)
    assert value_area_position(100.0, 110.0, 110.0) is None


def test_bar_position_stays_on_the_track():
    assert bar_position(-25.0) == 0.0
    assert bar_position(140.0) == 100.0
    assert bar_position(None) is None


def test_gauge_arc_length_matches_the_value():
    # The arc has pathLength 100, so a value of 25 draws 25 and leaves 75.
    assert 'stroke-dasharray="25.0 100"' in gauge_html(25.0)


def test_missing_value_draws_no_indicator():
    assert "stroke-dasharray" not in gauge_html(None)
    card = meter_card("Costo de operar", None, "Sin dato", "No disponible", bar=None)
    assert "N/D" in card
    assert "bar-fill" not in card


def test_card_escapes_provider_text():
    card = meter_card("Título", "1", "ok", "<script>x</script>")
    assert "<script>" not in card


def test_alert_row_escapes():
    assert "&lt;b&gt;X" in alert_row("<b>X", "texto")


def test_conditions_expose_their_percentiles():
    n = 100
    atr = [0.5 + (i % 11) * 0.1 for i in range(n - 1)] + [9.0]
    df = pd.DataFrame({"close": [100.0] * n, "atr": atr})
    c = market_conditions(df)
    assert c["volatility_percentile"] == pytest.approx(100.0)
    assert c["spread_percentile"] is None
