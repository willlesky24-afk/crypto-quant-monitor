from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.resolve()
SRC_DIR = ROOT_DIR / "src"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

target_app = SRC_DIR / "app.py"
with open(target_app, encoding="utf-8") as f:
    code = compile(f.read(), str(target_app), "exec")
    exec(code, globals())
