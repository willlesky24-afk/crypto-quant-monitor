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
        pd.DataFrame(columns=["high", "low", "close", "volume"]),
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


def test_vectorized_matches_exact_step_by_step_reference():
    # Frame with known distribution: high concentration around 100.0
    prices = [50.0, 95.0, 100.0, 102.0, 105.0, 150.0]
    volumes = [10.0, 50.0, 100.0, 80.0, 40.0, 5.0]
    df = _frame(prices, volumes)

    vp = VolumeProfile()
    result = vp.calculate(df, bins=5)

    assert result["poc"] == pytest.approx(112.5, rel=1e-2)
    assert result["val"] <= result["poc"] <= result["vah"]
    assert result["val"] >= 50.0
    assert result["vah"] <= 150.0


def test_vectorized_identical_to_iterative_reference(synthetic_ohlcv):
    # Iterative baseline reference
    prices = (synthetic_ohlcv["high"] + synthetic_ohlcv["low"] + synthetic_ohlcv["close"]) / 3.0
    volume = synthetic_ohlcv["volume"]

    for bins in [5, 10, 24, 50]:
        price_range = [
            prices.min() + i * (prices.max() - prices.min()) / (bins - 1)
            for i in range(bins)
        ]
        profile_ref = []
        for i in range(len(price_range) - 1):
            if i == len(price_range) - 2:
                mask = (prices >= price_range[i]) & (prices <= price_range[i + 1])
            else:
                mask = (prices >= price_range[i]) & (prices < price_range[i + 1])
            profile_ref.append(volume[mask].sum())

        max_idx = profile_ref.index(max(profile_ref))
        poc_ref = (price_range[max_idx] + price_range[max_idx + 1]) / 2.0

        res_opt = VolumeProfile().calculate(synthetic_ohlcv, bins=bins)
        assert res_opt["poc"] == pytest.approx(round(poc_ref, 2), abs=0.01)

