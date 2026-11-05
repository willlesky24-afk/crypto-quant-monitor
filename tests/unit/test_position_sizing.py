"""v3.1 risk calculator. Every expected value is worked by hand in the comments."""

from __future__ import annotations

import math

import pytest

from src.position_sizing import (
    PositionSizingError,
    compute_position_plan,
    quote_to_usd,
    stop_from_atr,
)


def _plan(**kw):
    base = {"capital": 10_000.0, "risk_pct": 1.0, "side": "LONG", "spread": 0.0}
    base.update(kw)
    base.setdefault("fee_pct", 0.0)
    return compute_position_plan(**base)


def test_crypto_with_fees():
    # Risk per unit: 1000 + 0.1% x (50000 + 49000) = 1000 + 99 = 1099.
    # Units: 100 / 1099 = 0.0909918. Notional: 4549.59. Costs: 0.0909918 x 99 = 9.008.
    p = _plan(
        entry_price=50_000.0,
        stop_price=49_000.0,
        fee_pct=0.1,
        quote_to_account=1.0,
    )
    assert p.units == pytest.approx(100.0 / 1099.0)
    assert p.notional == pytest.approx(4549.59, abs=0.01)
    assert p.max_loss == pytest.approx(100.0)
    assert p.costs == pytest.approx(9.008, abs=0.001)
    assert not p.limited_by_capital


def test_gold_with_spread():
    # Risk per unit 20 + 0.5 = 20.5. Units 100/20.5 = 4.87805. Notional 9756.10.
    # Spread cost 4.87805 x 0.5 = 2.439.
    p = _plan(entry_price=2000.0, stop_price=1980.0, spread=0.5, quote_to_account=1.0)
    assert p.units == pytest.approx(4.87805, abs=1e-5)
    assert p.notional == pytest.approx(9756.10, abs=0.01)
    assert p.costs == pytest.approx(2.439, abs=0.001)
    assert p.max_loss == pytest.approx(100.0)


def test_small_account_is_capped_without_leverage():
    # Risk per unit 0.005 + 0.0002 = 0.0052, wanted units 10/0.0052 = 1923 cost
    # 2115 USD, above 1000. Capped: 1000/1.1 = 909.09 units, loss 4.727.
    p = _plan(
        capital=1000.0,
        entry_price=1.1,
        stop_price=1.095,
        spread=0.0002,
        quote_to_account=1.0,
    )
    assert p.limited_by_capital
    assert p.units == pytest.approx(909.0909, abs=1e-3)
    assert p.notional == pytest.approx(1000.0)
    assert p.max_loss == pytest.approx(4.727, abs=0.001)


def test_short_in_yen_is_converted_to_usd():
    # Rate 1/150. Risk per unit (5 + 0.02)/150 = 0.0334667 USD.
    # Units 100/0.0334667 = 2988.05. Notional = units x 150 x 1/150 = 2988.05.
    p = _plan(
        side="SHORT",
        entry_price=150.0,
        stop_price=155.0,
        spread=0.02,
        quote_to_account=1.0 / 150.0,
    )
    assert p.units == pytest.approx(2988.05, abs=0.01)
    assert p.notional == pytest.approx(2988.05, abs=0.01)
    assert p.max_loss == pytest.approx(100.0)


@pytest.mark.parametrize(
    "symbol,price,rate",
    [
        ("BTCUSDT", 50_000.0, 1.0),
        ("EURUSD=X", 1.1, 1.0),
        ("XAUUSD=X", 2000.0, 1.0),
        ("SPX500=X", 7000.0, 1.0),
        ("USDJPY=X", 150.0, 1.0 / 150.0),
        ("USDCHF=X", 0.8, 1.25),
    ],
)
def test_quote_to_usd(symbol, price, rate):
    assert quote_to_usd(symbol, price) == pytest.approx(rate)


def test_cross_pair_needs_a_rate_we_do_not_invent():
    with pytest.raises(PositionSizingError):
        quote_to_usd("ETHBTC", 0.05)


def test_stop_from_atr():
    assert stop_from_atr(100.0, 2.0, 1.5, "LONG") == pytest.approx(97.0)
    assert stop_from_atr(100.0, 2.0, 1.5, "SHORT") == pytest.approx(103.0)


def test_stop_from_atr_never_reaches_zero():
    with pytest.raises(PositionSizingError):
        stop_from_atr(1.0, 2.0, 1.0, "LONG")


@pytest.mark.parametrize(
    "kw",
    [
        {"stop_price": 101.0},  # LONG stop above entry
        {"stop_price": 100.0},
        {"side": "SHORT", "stop_price": 99.0},
        {"side": "COMPRA", "stop_price": 99.0},
        {"capital": 0.0, "stop_price": 99.0},
        {"risk_pct": 0.0, "stop_price": 99.0},
        {"risk_pct": 100.1, "stop_price": 99.0},
        {"spread": -1.0, "stop_price": 99.0},
        {"fee_pct": -0.1, "stop_price": 99.0},
        {"stop_price": math.nan},
        {"stop_price": 99.0, "quote_to_account": 0.0},
    ],
)
def test_invalid_inputs_fail_loudly(kw):
    args = {"entry_price": 100.0, "quote_to_account": 1.0}
    args.update(kw)
    with pytest.raises(PositionSizingError):
        _plan(**args)
