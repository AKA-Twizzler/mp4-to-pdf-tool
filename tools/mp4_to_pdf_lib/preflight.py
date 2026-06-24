from __future__ import annotations

import importlib
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass


E_DEP_MISSING = "E_DEP_MISSING"


@dataclass(frozen=True)
class PreflightError(Exception):
    code: str
    dependency: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}:{self.dependency}: {self.message}"


@dataclass(frozen=True)
class Requirement:
    name: str
    install_hint: str
    version_args: tuple[str, ...]


@dataclass(frozen=True)
class PythonRequirement:
    module_name: str
    install_hint: str


REQUIRED_TOOLS = (
    Requirement("ffmpeg", "Install ffmpeg package (apt/brew/choco).", ("-version",)),
    Requirement("ffprobe", "Install ffmpeg package (apt/brew/choco).", ("-version",)),
    Requirement("img2pdf", "Install via pip: python3 -m pip install img2pdf", ("--version",)),
    Requirement("gs", "Install ghostscript package (apt/brew/choco).", ("--version",)),
    Requirement("pdfinfo", "Install poppler-utils package (apt) or poppler (brew).", ("-v",)),
)

REQUIRED_PYTHON_MODULES = (
    PythonRequirement("img2pdf", "Install via pip: python3 -m pip install img2pdf"),
)


def _first_non_empty_line(text: str) -> str:
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned
    return "<no version output>"


def _probe_command_version(requirement: Requirement) -> str:
    output = subprocess.run(
        [requirement.name, *requirement.version_args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if output.returncode != 0 and not output.stdout:
        return f"<version probe failed exit={output.returncode}>"
    return _first_non_empty_line(output.stdout)


def _iter_extra_tool_requirements() -> tuple[Requirement, ...]:
    raw = os.environ.get("MP4_TO_PDF_PREFLIGHT_EXTRA_TOOLS", "").strip()
    if not raw:
        return ()
    names = [part.strip() for part in raw.split(",") if part.strip()]
    requirements = []
    for name in names:
        requirements.append(
            Requirement(
                name=name,
                install_hint=f"Install '{name}' and ensure it is on PATH.",
                version_args=("--version",),
            )
        )
    return tuple(requirements)


def run_preflight(strict: bool = False) -> int:
    print("PREFLIGHT: START")
    print(f"PYTHON_RUNTIME: {platform.python_version()}")
    print("TOOLS:")

    all_requirements = REQUIRED_TOOLS + _iter_extra_tool_requirements()
    missing = []

    for requirement in all_requirements:
        resolved = shutil.which(requirement.name)
        if not resolved:
            message = f"missing on PATH. Hint: {requirement.install_hint}"
            print(f"- {requirement.name}: MISSING ({message})")
            missing.append((requirement.name, message))
            if strict:
                raise PreflightError(E_DEP_MISSING, requirement.name, message)
            continue
        version_line = _probe_command_version(requirement)
        print(f"- {requirement.name}: OK ({version_line})")

    print("PYTHON_MODULES:")
    for module_requirement in REQUIRED_PYTHON_MODULES:
        try:
            module = importlib.import_module(module_requirement.module_name)
        except Exception:
            message = f"python module missing. Hint: {module_requirement.install_hint}"
            print(f"- {module_requirement.module_name}: MISSING ({message})")
            missing.append((module_requirement.module_name, message))
            if strict:
                raise PreflightError(E_DEP_MISSING, module_requirement.module_name, message)
            continue

        version = getattr(module, "__version__", "<no __version__>")
        print(f"- {module_requirement.module_name}: OK ({version})")

    if missing:
        print("PREFLIGHT: FAIL")
        return 1

    print("PREFLIGHT: PASS")
    return 0
