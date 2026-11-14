"""v5 login: one owner password, a signed session cookie, no hidden way around it."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src import market_service
from src.operator_api import web_auth
from src.operator_api.app import create_app
from src.operator_api.config import APISecurityConfig
from src.operator_api.dependencies import reset_security_config

SECRET = "ab" * 32


def test_pbkdf2_matches_rfc7914_vector():
    # RFC 7914 section 11: PBKDF2-HMAC-SHA256, P="passwd", S="salt", c=1.
    # First 32 bytes of the published 64-byte output.
    expected = "55ac046e56e3089fec1691c22544b605f94185216dde0465e68b9d57c20dacbc"
    assert web_auth.derive("passwd", bytes.fromhex("73616c74"), 1).hex() == expected


def test_hash_round_trip_and_wrong_password():
    stored = web_auth.hash_password("correcta larga", iterations=1000)
    assert stored.startswith("pbkdf2_sha256$1000$")
    assert web_auth.check_password("correcta larga", stored)
    assert not web_auth.check_password("otra", stored)


def test_malformed_hash_is_an_error_not_a_pass():
    with pytest.raises(web_auth.WebAuthError):
        web_auth.check_password("x", "texto-cualquiera")


def test_session_token_expires_and_rejects_tampering():
    token = web_auth.make_token(SECRET, now=1000, ttl=60)
    assert web_auth.token_valid(token, SECRET, now=1059)
    assert not web_auth.token_valid(token, SECRET, now=1061)
    exp, sig = token.split(".")
    assert not web_auth.token_valid(f"{int(exp) + 999}.{sig}", SECRET, now=1000)
    assert not web_auth.token_valid(token, "cd" * 32, now=1000)
    assert not web_auth.token_valid("basura", SECRET, now=1000)


@pytest.fixture
def app_client(monkeypatch):
    reset_security_config()
    web_auth.reset_failures()
    monkeypatch.delenv("WEB_LOGIN_DISABLED", raising=False)
    monkeypatch.setenv(
        "WEB_PASSWORD_HASH", web_auth.hash_password("clave-de-prueba", iterations=1000)
    )
    monkeypatch.setenv("WEB_SESSION_SECRET", SECRET)
    monkeypatch.setattr(
        market_service,
        "markets",
        lambda: {"crypto": [], "other": [], "other_error": None, "intervals": []},
    )
    app = create_app(config=APISecurityConfig(security_enabled=False))
    yield TestClient(app), monkeypatch
    reset_security_config()


def test_data_needs_a_session(app_client):
    c, _ = app_client
    r = c.get("/api/v1/mercados")
    assert r.status_code == 401
    assert c.get("/api/v1/sesion").json() == {
        "authenticated": False,
        "configured": True,
    }


def test_login_opens_and_logout_closes(app_client):
    c, _ = app_client
    r = c.post("/api/v1/sesion", json={"password": "clave-de-prueba"})
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert c.get("/api/v1/mercados").status_code == 200
    assert c.get("/api/v1/sesion").json()["authenticated"] is True
    c.delete("/api/v1/sesion")
    assert c.get("/api/v1/mercados").status_code == 401


def test_wrong_password_and_lockout(app_client):
    c, _ = app_client
    for _ in range(web_auth.MAX_FAILURES):
        assert c.post("/api/v1/sesion", json={"password": "mala"}).status_code == 401
    r = c.post("/api/v1/sesion", json={"password": "clave-de-prueba"})
    assert r.status_code == 429  # locked even with the right password


def test_without_password_configured_nothing_is_served(app_client):
    c, mp = app_client
    mp.delenv("WEB_PASSWORD_HASH")
    r = c.get("/api/v1/mercados")
    assert r.status_code == 503
    assert "set_web_password" in r.json()["detail"]
    assert c.get("/api/v1/sesion").json() == {
        "authenticated": False,
        "configured": False,
    }


def test_explicit_disable_is_the_only_bypass(app_client):
    c, mp = app_client
    mp.setenv("WEB_LOGIN_DISABLED", "true")
    assert c.get("/api/v1/mercados").status_code == 200
    assert c.get("/api/v1/sesion").json()["authenticated"] is True
