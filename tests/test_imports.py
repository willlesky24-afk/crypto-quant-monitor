from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run_import(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_report_imports_as_package():
    result = _run_import("import src.report")
    assert result.returncode == 0, result.stderr


def test_report_imports_from_streamlit_style_src_path():
    result = _run_import(
        "import sys; sys.path.insert(0, 'src'); import report; assert report.MarketReport"
    )
    assert result.returncode == 0, result.stderr

