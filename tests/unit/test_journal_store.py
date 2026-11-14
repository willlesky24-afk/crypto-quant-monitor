"""v5 journal: hand-computed references for R, summaries and discipline limits."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.journal_store import Journal, JournalError, breaches, summary, trade_r


@pytest.fixture
def j(tmp_path):
    return Journal(tmp_path / "diario.db")


def test_trade_r_by_hand():
    # LONG 2 units 100 -> 110, costs 0.40, planned risk 10.40:
    # pnl = 2*10 - 0.40 = 19.60; R = 19.60 / 10.40 = 1.884615...
    assert trade_r("LONG", 100, 110, 2, 0.40, 10.40) == pytest.approx(
        1.8846154, rel=1e-6
    )
    # SHORT 1 unit 50 -> 52, costs 0.10, risk 3.10: pnl = -2.10; R = -0.677419...
    assert trade_r("SHORT", 50, 52, 1, 0.10, 3.10) == pytest.approx(
        -0.6774194, rel=1e-6
    )


def test_hitting_the_stop_is_minus_one_r(j):
    # Plan risk includes costs, as in position_sizing: 2 units * 5 + 0.40 = 10.40.
    t = j.open_trade("BTCUSDT", "LONG", 100, 95, 2, 10.40, 0.40, "ruptura")
    closed = j.close_trade(t.id, 95, moved_stop=False, size_respected=True)
    assert closed.r == pytest.approx(-1.0)
    assert closed.followed_plan is True


def test_plan_validation(j):
    with pytest.raises(JournalError):
        j.open_trade("X", "LONG", 100, 101, 1, 1, 0, "stop arriba en largo")
    with pytest.raises(JournalError):
        j.open_trade("X", "LONG", 100, 95, 1, 5, 0, "   ")
    t = j.open_trade("X", "LONG", 100, 95, 1, 5, 0, "ok")
    j.close_trade(t.id, 101, False, True)
    with pytest.raises(JournalError):
        j.close_trade(t.id, 102, False, True)


def test_summary_empty_is_none_not_zero():
    s = summary([])
    assert s["closed"] == 0 and s["mean_r"] is None and s["plan_pct"] is None


def test_summary_by_hand(j):
    # Three trades, risk 10 each, no costs:
    #  A +20 (R +2, in plan); B -10 (R -1, moved stop); C -10 (R -1, in plan)
    a = j.open_trade("X", "LONG", 100, 90, 1, 10, 0, "a")
    b = j.open_trade("X", "LONG", 100, 90, 1, 10, 0, "b")
    c = j.open_trade("X", "LONG", 100, 90, 1, 10, 0, "c")
    j.close_trade(a.id, 120, False, True)
    j.close_trade(b.id, 90, True, True)
    j.close_trade(c.id, 90, False, True)
    s = summary(j.trades())
    assert s["closed"] == 3
    assert s["mean_r"] == pytest.approx(0.0)  # (2 - 1 - 1) / 3
    assert s["plan_pct"] == pytest.approx(200 / 3)
    assert s["r_in_plan"] == pytest.approx(0.5)  # (2 - 1) / 2
    assert s["r_off_plan"] == pytest.approx(-1.0)
    assert s["worst_streak"] == 2
    assert s["pnl_usd"] == pytest.approx(0.0)


def test_attempts_survive_a_new_instance(tmp_path):
    path = tmp_path / "d.db"
    assert Journal(path).next_attempt("ip:1") == 1
    assert Journal(path).next_attempt("ip:1") == 2  # a restart does not reset it
    assert Journal(path).attempts("ip:2") == 0


def test_holdout_is_single_use(j):
    assert j.holdout_used_at("BTCUSDT|1h|trend_ema|LONG|2|6|120") is None
    j.use_holdout("BTCUSDT|1h|trend_ema|LONG|2|6|120")
    with pytest.raises(JournalError):
        j.use_holdout("BTCUSDT|1h|trend_ema|LONG|2|6|120")


def test_rules_have_no_defaults_and_reject_nonsense(j):
    assert j.rules() == {}
    assert j.set_rules({"capital": 1000, "pause_after_losses": 3}) == {
        "capital": 1000.0,
        "pause_after_losses": 3.0,
    }
    assert j.set_rules({"pause_after_losses": None}) == {"capital": 1000.0}
    with pytest.raises(JournalError):
        j.set_rules({"capital": -5})
    with pytest.raises(JournalError):
        j.set_rules({"inventada": 1})


def test_breaches_by_hand(j):
    # Capital 1000, daily limit 2 % = $20. Two losses of $10 today -> breached.
    rules = {
        "capital": 1000,
        "max_daily_loss_pct": 2,
        "pause_after_losses": 2,
        "max_open_risk_pct": 1,
    }
    for _ in range(2):
        t = j.open_trade("X", "LONG", 100, 90, 1, 10, 0, "x")
        j.close_trade(t.id, 90, False, True)
    j.open_trade("X", "LONG", 100, 90, 1, 10, 0, "abierta")  # $10 open = 1 % of 1000
    out = breaches(j.trades(), rules, now=datetime.now(UTC))
    assert len(out) == 3
    assert any("día" in m for m in out)
    assert any("seguidas" in m or "seguida" in m for m in out)
    assert any("riesgo abierto" in m for m in out)


def test_no_rules_no_breaches(j):
    t = j.open_trade("X", "LONG", 100, 90, 1, 10, 0, "x")
    j.close_trade(t.id, 50, False, True)
    assert breaches(j.trades(), {}) == []


def test_eligibility_for_reserved_data(j):
    assert not j.is_eligible("k")
    j.mark_eligible("k")
    assert j.is_eligible("k")
