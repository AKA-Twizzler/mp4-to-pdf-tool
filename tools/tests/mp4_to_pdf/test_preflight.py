from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from mp4_to_pdf_lib.preflight import E_DEP_MISSING, PreflightError, run_preflight


def test_preflight_strict_raises_when_tool_missing() -> None:
    # Patch shutil.which to simulate missing ffmpeg
    with patch("mp4_to_pdf_lib.preflight.shutil.which", return_value=None):
        with pytest.raises(PreflightError) as exc_info:
            run_preflight(strict=True)
    assert exc_info.value.code == E_DEP_MISSING


def test_preflight_non_strict_returns_nonzero_when_tool_missing() -> None:
    with patch("mp4_to_pdf_lib.preflight.shutil.which", return_value=None):
        result = run_preflight(strict=False)
    assert result != 0


def test_preflight_error_str_format() -> None:
    error = PreflightError(E_DEP_MISSING, "ffmpeg", "missing on PATH")
    rendered = str(error)
    assert E_DEP_MISSING in rendered
    assert "ffmpeg" in rendered


def test_preflight_extra_tools_env_var(tmp_path: pytest.TempPathFactory) -> None:
    # Extra tool that definitely does not exist
    env = {**os.environ, "MP4_TO_PDF_PREFLIGHT_EXTRA_TOOLS": "no_such_tool_xyz_abc"}
    with patch.dict(os.environ, env, clear=True):
        with patch("mp4_to_pdf_lib.preflight.shutil.which") as mock_which:
            # Return a valid path for all standard tools, None for the extra one
            def which_side_effect(name: str) -> str | None:
                if name == "no_such_tool_xyz_abc":
                    return None
                return f"/usr/bin/{name}"

            mock_which.side_effect = which_side_effect
            with patch("mp4_to_pdf_lib.preflight.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "version 1.0"
                with patch("importlib.import_module"):
                    result = run_preflight(strict=False)
    assert result != 0
