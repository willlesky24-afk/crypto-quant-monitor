import pytest

from src.market_zone import get_market_zone
from src.visuals import score_to_confidence


@pytest.mark.parametrize(
    ("score", "label", "percent"),
    [
        (5, "Alta", 90),
        (3, "Moderada", 60),
        (1, "Baja", 40),
        (0, "Débil", 20),
    ],
)
def test_score_to_confidence_boundaries(score, label, percent):
    result = score_to_confidence(score)
    assert result["label"] == label
    assert result["percent"] == percent


def test_market_zone_preserves_profile_values():
    profile = {"poc": 100.0, "vah": 110.0, "val": 90.0, "extra": "ignored"}
    assert get_market_zone(profile) == {
        "poc": 100.0,
        "vah": 110.0,
        "val": 90.0,
    }
