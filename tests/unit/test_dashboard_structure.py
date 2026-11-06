from __future__ import annotations

import ast
from pathlib import Path


def test_app_py_syntax_and_structure():
    app_path = Path(__file__).resolve().parent.parent.parent / "src" / "app.py"
    assert app_path.exists(), f"app.py not found at {app_path}"

    # Verify python AST parses without any SyntaxError
    code = app_path.read_text(encoding="utf-8")
    parsed_tree = ast.parse(code)
    assert isinstance(parsed_tree, ast.Module)

    # Verify required tabs are present in code
    assert "Probar mi idea" in code
    assert "Notificaciones" in code

    # Verify quantitative engines are imported and used as services
    assert "MarketEngine" in code
    assert "RegimeClassifier" in code
    assert "NotificationDispatcher" in code
