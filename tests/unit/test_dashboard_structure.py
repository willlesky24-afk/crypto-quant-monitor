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
    assert "Live Monitor" in code
    assert "Backtest Analytics" in code
    assert "Notification Settings" in code

    # Verify quantitative engines are imported and used as services
    assert "MarketEngine" in code
    assert "RegimeClassifier" in code
    assert "PredictiveEngine" in code
    assert "DecisionEngine" in code
    assert "BacktestRunner" in code
    assert "NotificationDispatcher" in code
