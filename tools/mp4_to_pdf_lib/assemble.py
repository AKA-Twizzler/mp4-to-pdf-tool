from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


E_ASSEMBLY_FAILED = "E_ASSEMBLY_FAILED"
E_ASSEMBLY_INPUT_MISSING = "E_ASSEMBLY_INPUT_MISSING"


@dataclass(frozen=True)
class AssemblyError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def _resolve_img2pdf_command() -> list[str]:
    img2pdf_bin = shutil.which("img2pdf")
    if img2pdf_bin:
        return [img2pdf_bin]

    python3_bin = shutil.which("python3")
    if python3_bin:
        return [python3_bin, "-m", "img2pdf"]

    raise AssemblyError(
        E_ASSEMBLY_FAILED,
        "img2pdf not found and python3 unavailable for module fallback",
    )


def _manifest_entries(manifest_path: Path) -> tuple[str, ...]:
    if not manifest_path.exists():
        raise AssemblyError(E_ASSEMBLY_INPUT_MISSING, f"Missing manifest: {manifest_path}")

    lines = [line.strip() for line in manifest_path.read_text(encoding="utf-8").splitlines()]
    entries = tuple(line for line in lines if line)
    if not entries:
        raise AssemblyError(E_ASSEMBLY_INPUT_MISSING, f"Manifest has no frame entries: {manifest_path}")
    return entries


def assemble_manifest_to_pdf(manifest_path: Path, output_pdf: Path, pdf_nodate: bool = False) -> int:
    manifest_parent = manifest_path.parent
    entries = _manifest_entries(manifest_path)
    ordered_inputs: list[str] = []

    for rel_path in entries:
        frame_path = manifest_parent / rel_path
        if not frame_path.exists():
            raise AssemblyError(E_ASSEMBLY_INPUT_MISSING, f"Missing manifest input: {frame_path}")
        ordered_inputs.append(str(frame_path))

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    command = _resolve_img2pdf_command()
    if pdf_nodate:
        command.append("--nodate")
    command.extend(["-o", str(output_pdf), *ordered_inputs])

    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        output = completed.stdout.strip() or "<no img2pdf output>"
        raise AssemblyError(E_ASSEMBLY_FAILED, f"img2pdf failed with exit={completed.returncode}: {output}")

    return len(ordered_inputs)
