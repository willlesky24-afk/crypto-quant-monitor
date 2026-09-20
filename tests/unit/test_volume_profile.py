from __future__ import annotations

import math

import pandas as pd
import pytest

from src.volume_profile import VolumeProfile


def _frame(prices, volumes):
    return pd.DataFrame(
        {"high": prices, "low": prices, "close": prices, "volume": volumes}
    )


def test_maximum_price_is_included_in_last_bin():
    result = VolumeProfile().calculate(_frame([0.0, 10.0], [1.0, 100.0]), bins=3)
    assert result["poc"] == pytest.approx(7.5)


def test_constant_prices_return_finite_ordered_profile():
    result = VolumeProfile().calculate(_frame([42.0] * 5, [1, 2, 3, 4, 5]))
    assert all(math.isfinite(result[key]) for key in ("val", "poc", "vah"))
    assert result["val"] <= result["poc"] <= result["vah"]


@pytest.mark.parametrize(
    "frame",
    [
        pd.DataFrame(),
        pd.DataFrame({"high": [1], "low": [1], "close": [1]}),
    ],
)
def test_invalid_frames_raise_value_error(frame):
    with pytest.raises(ValueError):
        VolumeProfile().calculate(frame)


@pytest.mark.parametrize("bins", [0, 1, -1, True, 2.5])
def test_invalid_bin_count_raises_value_error(bins):
    with pytest.raises(ValueError):
        VolumeProfile().calculate(_frame([1, 2], [1, 1]), bins=bins)


def test_non_finite_values_raise_value_error():
    with pytest.raises(ValueError, match="finitos"):
        VolumeProfile().calculate(_frame([1.0, float("nan")], [1, 1]))


def test_normal_profile_is_finite_and_ordered(synthetic_ohlcv):
    result = VolumeProfile().calculate(synthetic_ohlcv)
    assert set(result) == {"poc", "vah", "val"}
    assert result["val"] <= result["poc"] <= result["vah"]
