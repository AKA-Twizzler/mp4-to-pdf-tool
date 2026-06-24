from __future__ import annotations

import sys
from pathlib import Path

# Ensure tools/ is on sys.path so mp4_to_pdf_lib imports work without install
_tools_root = Path(__file__).resolve().parents[2]
if str(_tools_root) not in sys.path:
    sys.path.insert(0, str(_tools_root))

_project_root = Path(__file__).resolve().parents[3]


def fixtures_root() -> Path:
    return _project_root / "fixtures"


def job_examples_root() -> Path:
    return fixtures_root() / "job_examples"
