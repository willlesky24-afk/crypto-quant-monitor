"""v5 journal and verifier routes: discipline is enforced and recorded."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src import idea_verifier
from src.operator_api import web_router
from src.operator_api.app import create_app
from src.operator_api.config import APISecurityConfig
from src.operator_api.dependencies import reset_security_config

PLAN = {
    "symbol": "BTCUSDT",
    "side": "LONG",
    "entry": 100.0,
    "stop": 90.0,
    "units": 1.0,
    "risk_usd": 10.0,
    "costs_usd": 0.0,
    "reason": "ruptura del máximo de 20 velas",
}


@pytest.fixture
def c(monkeypatch, fresh_journal):
    reset_security_config()
    monkeypatch.setenv("WEB_LOGIN_DISABLED", "true")
    yield TestClient(create_app(config=APISecurityConfig(security_enabled=False)))
    reset_security_config()


def test_empty_journal_shows_none_not_zero(c):
    d = c.get("/api/v1/diario").json()
    assert d["trades"] == [] and d["semana"]["mean_r"] is None and d["breaches"] == []


def test_open_close_and_r_by_hand(c):
    t = c.post("/api/v1/diario", json=PLAN).json()
    assert t["status"] == "abierta"
    closed = c.post(
        f"/api/v1/diario/{t['id']}/cerrar",
        json={"exit": 115, "moved_stop": False, "size_respected": True},
    ).json()
    assert closed["r"] == pytest.approx(1.5)  # (115 - 100) * 1 / 10
    d = c.get("/api/v1/diario").json()
    assert d["semana"]["closed"] == 1 and d["semana"]["plan_pct"] == pytest.approx(
        100.0
    )


def test_rules_block_until_acknowledged(c):
    c.put("/api/v1/diario/reglas", json={"capital": 1000, "pause_after_losses": 1})
    t = c.post("/api/v1/diario", json=PLAN).json()
    c.post(
        f"/api/v1/diario/{t['id']}/cerrar",
        json={"exit": 90, "moved_stop": False, "size_respected": True},
    )
    r = c.post("/api/v1/diario", json=PLAN)
    assert r.status_code == 409 and "pausa" in r.json()["detail"]["breaches"][0]
    ok = c.post("/api/v1/diario", json={**PLAN, "acknowledged": True}).json()
    assert ok["outside_rules"] is True


def test_rules_can_be_removed(c):
    assert c.put("/api/v1/diario/reglas", json={"capital": 1000}).json() == {
        "capital": 1000.0
    }
    assert c.put("/api/v1/diario/reglas", json={"capital": None}).json() == {}
    assert c.put("/api/v1/diario/reglas", json={"capital": -1}).status_code == 422


def test_bad_plan_is_422(c):
    assert c.post("/api/v1/diario", json={**PLAN, "stop": 120}).status_code == 422


def test_reserved_data_needs_eligibility_and_is_single_use(c, monkeypatch):
    calls = []

    def fake_holdout(df, spec, **kw):
        calls.append(spec)
        return {
            "code": "NO_SE_DISTINGUE",
            "text": "x",
            "trades": 0,
            "attempts": 1,
            "key": idea_verifier.spec_key(spec),
        }

    monkeypatch.setattr(web_router, "load_history", lambda s, i: object())
    monkeypatch.setattr(web_router, "verify_holdout", fake_holdout)
    body = {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "entry": "trend_ema",
        "sl_atr": 2,
        "tp_atr": 6,
        "max_bars": 120,
    }
    assert c.post("/api/v1/verificar/reservado", json=body).status_code == 409
    web_router.journal().mark_eligible("BTCUSDT|1h|trend_ema|LONG|2|6|120")
    assert c.post("/api/v1/verificar/reservado", json=body).status_code == 200
    second = c.post("/api/v1/verificar/reservado", json=body)
    assert second.status_code == 409 and "ya se usaron" in second.json()["detail"]
    assert len(calls) == 1
