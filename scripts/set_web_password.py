"""Set the owner password of the web interface.

Asks for the password twice (it is not shown on screen), writes only its hash
(WEB_PASSWORD_HASH) and a new session secret (WEB_SESSION_SECRET) to .env.
Running it again changes the password and closes every open session.
"""

from __future__ import annotations

import getpass
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.operator_api.web_auth import hash_password  # noqa: E402

MIN_LENGTH = 12  # project choice: long passphrases beat complex short ones


def main() -> int:
    first = getpass.getpass("Nueva contraseña (mínimo 12 caracteres): ")
    if len(first) < MIN_LENGTH:
        print("Muy corta. No se cambió nada.")
        return 1
    if getpass.getpass("Repítela: ") != first:
        print("No coinciden. No se cambió nada.")
        return 1
    env = ROOT / ".env"
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    keep = [
        ln
        for ln in lines
        if not ln.startswith(("WEB_PASSWORD_HASH=", "WEB_SESSION_SECRET="))
    ]
    keep += [
        f"WEB_PASSWORD_HASH={hash_password(first)}",
        f"WEB_SESSION_SECRET={secrets.token_hex(32)}",
    ]
    env.write_text("\n".join(keep) + "\n", encoding="utf-8")
    print("Listo. Reinicia el servidor para que tome la contraseña.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
