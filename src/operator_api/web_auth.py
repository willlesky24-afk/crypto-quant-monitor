"""v5 login for the web interface: one owner password and a signed session cookie.

Why this shape:
- One owner, no user table: the password hash lives in ``.env``
  (WEB_PASSWORD_HASH), written by ``scripts/set_web_password.py``; the
  password itself is never stored or sent anywhere.
- PBKDF2-HMAC-SHA256 from the standard library (hashlib.pbkdf2_hmac), checked
  against the RFC 7914 test vector. 600 000 iterations follows the OWASP
  Password Storage Cheat Sheet recommendation for PBKDF2-HMAC-SHA256.
- The session is a cookie "expiry.signature" signed with HMAC-SHA256 and
  WEB_SESSION_SECRET: nothing to keep on the server, and changing the secret
  closes every session. 7 days and 5 failures / 15 min are project choices.
- No hidden way around it: without a configured password the data endpoints
  answer 503. Only WEB_LOGIN_DISABLED=true turns the login off, explicitly.
  A localhost exemption would be unsafe: ``tailscale serve`` forwards remote
  visitors from 127.0.0.1.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from src.operator_api.security import get_client_identifier

ITERATIONS = 600_000
SESSION_TTL = 7 * 24 * 3600
MAX_FAILURES = 5
LOCK_SECONDS = 15 * 60
COOKIE = "cqm_session"
SETUP_HINT = (
    "El inicio de sesión no está configurado. En la carpeta del proyecto ejecuta: "
    "python scripts/set_web_password.py"
)

_failures: dict[str, list[float]] = defaultdict(list)


class WebAuthError(ValueError):
    """The stored hash cannot be read; never treated as a valid login."""


def reset_failures() -> None:
    _failures.clear()


def derive(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, 32)


def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${derive(password, salt, iterations).hex()}"


def check_password(password: str, stored: str) -> bool:
    parts = stored.split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256" or not parts[1].isdigit():
        raise WebAuthError("WEB_PASSWORD_HASH no tiene el formato esperado.")
    digest = derive(password, bytes.fromhex(parts[2]), int(parts[1]))
    return hmac.compare_digest(digest.hex(), parts[3])


def _sign(expiry: str, secret: str) -> str:
    return hmac.new(secret.encode(), expiry.encode(), hashlib.sha256).hexdigest()


def make_token(secret: str, now: float | None = None, ttl: int = SESSION_TTL) -> str:
    expiry = str(int((time.time() if now is None else now) + ttl))
    return f"{expiry}.{_sign(expiry, secret)}"


def token_valid(token: str, secret: str, now: float | None = None) -> bool:
    expiry, _, signature = token.partition(".")
    if not expiry.isdigit() or not hmac.compare_digest(
        _sign(expiry, secret), signature
    ):
        return False
    return int(expiry) >= (time.time() if now is None else now)


def _disabled() -> bool:
    return os.getenv("WEB_LOGIN_DISABLED", "").strip().lower() == "true"


def _settings() -> tuple[str, str] | None:
    stored, secret = os.getenv("WEB_PASSWORD_HASH"), os.getenv("WEB_SESSION_SECRET")
    return (stored, secret) if stored and secret else None


def _has_session(request: Request) -> bool:
    if _disabled():
        return True
    settings = _settings()
    token = request.cookies.get(COOKIE)
    return bool(settings and token and token_valid(token, settings[1]))


def require_session(request: Request) -> None:
    """Dependency on every data endpoint of the web interface."""
    if _disabled():
        return
    if _settings() is None:
        raise HTTPException(503, SETUP_HINT)
    if not _has_session(request):
        raise HTTPException(401, "Inicia sesión para ver los datos.")


router = APIRouter(prefix="/api/v1", tags=["Sesión"])


class LoginBody(BaseModel):
    password: str


@router.get("/sesion")
def session_state(request: Request) -> dict[str, bool]:
    return {
        "authenticated": _has_session(request),
        "configured": _disabled() or _settings() is not None,
    }


@router.post("/sesion")
def login(body: LoginBody, request: Request, response: Response) -> dict[str, bool]:
    settings = _settings()
    if settings is None:
        raise HTTPException(503, SETUP_HINT)
    client = get_client_identifier(request)
    now = time.time()
    recent = [t for t in _failures[client] if now - t < LOCK_SECONDS]
    _failures[client] = recent
    if len(recent) >= MAX_FAILURES:
        raise HTTPException(429, "Demasiados intentos. Espera 15 minutos.")
    if not check_password(body.password, settings[0]):
        recent.append(now)
        raise HTTPException(401, "Contraseña incorrecta.")
    _failures.pop(client, None)
    response.set_cookie(
        COOKIE,
        make_token(settings[1]),
        max_age=SESSION_TTL,
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
    )
    return {"authenticated": True}


@router.delete("/sesion")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(COOKIE)
    return {"authenticated": False}
