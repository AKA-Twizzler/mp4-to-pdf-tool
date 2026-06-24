from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mp4_to_pdf_lib.errors import E_PDF_VALIDATE


@dataclass(frozen=True)
class VerificationError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def _run_checked(command: list[str], *, label: str) -> str:
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    output = completed.stdout.strip()
    if completed.returncode != 0:
        rendered_output = output if output else "<no output>"
        raise VerificationError(
            E_PDF_VALIDATE,
            f"{label} failed with exit={completed.returncode}: {rendered_output}",
        )
    return output


def _parse_pdfinfo_pages(pdfinfo_output: str) -> int:
    for line in pdfinfo_output.splitlines():
        cleaned = line.strip()
        if not cleaned.lower().startswith("pages:"):
            continue
        raw_value = cleaned.split(":", 1)[1].strip()
        try:
            return int(raw_value)
        except ValueError as exc:
            raise VerificationError(E_PDF_VALIDATE, f"pdfinfo returned non-integer page count: {raw_value}") from exc
    raise VerificationError(E_PDF_VALIDATE, "pdfinfo output did not include 'Pages:'")


def _manifest_frame_count(manifest_path: Path) -> int:
    lines = manifest_path.read_text(encoding="utf-8").splitlines()
    return len([line for line in lines if line.strip()])


def verify_pdf_output(
    output_pdf: Path,
    *,
    expected_pages: int | None = None,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    if not output_pdf.exists():
        raise VerificationError(E_PDF_VALIDATE, f"Output PDF is missing: {output_pdf}")
    if output_pdf.stat().st_size <= 0:
        raise VerificationError(E_PDF_VALIDATE, f"Output PDF is empty: {output_pdf}")

    pdfinfo_bin = shutil.which("pdfinfo")
    if pdfinfo_bin is None:
        raise VerificationError(E_PDF_VALIDATE, "pdfinfo not found on PATH")
    pdfinfo_output = _run_checked([pdfinfo_bin, str(output_pdf)], label="pdfinfo")
    pages = _parse_pdfinfo_pages(pdfinfo_output)

    gs_bin = shutil.which("gs")
    if gs_bin is None:
        raise VerificationError(E_PDF_VALIDATE, "gs not found on PATH")
    _run_checked(
        [
            gs_bin,
            "-o",
            "/dev/null",
            "-sDEVICE=nullpage",
            "-dPDFSTOPONERROR",
            "-dPDFSTOPONWARNING",
            "-dBATCH",
            "-dNOPAUSE",
            str(output_pdf),
        ],
        label="gs",
    )

    checks: dict[str, Any] = {
        "pdf_path": str(output_pdf),
        "pdf_size_bytes": output_pdf.stat().st_size,
        "pdfinfo_readable": True,
        "gs_parse_ok": True,
        "pdfinfo_pages": pages,
    }

    if expected_pages is not None:
        checks["expected_pages"] = expected_pages
        checks["pages_match_expected"] = pages == expected_pages
        if pages != expected_pages:
            raise VerificationError(
                E_PDF_VALIDATE,
                f"Page mismatch: pdfinfo_pages={pages}, expected_pages={expected_pages}",
            )

    if manifest_path is not None and manifest_path.exists():
        frame_count = _manifest_frame_count(manifest_path)
        checks["manifest_path"] = str(manifest_path)
        checks["manifest_frames"] = frame_count
        checks["pages_match_manifest"] = pages == frame_count
        if pages != frame_count:
            raise VerificationError(
                E_PDF_VALIDATE,
                f"Page/frame mismatch: pdfinfo_pages={pages}, manifest_frames={frame_count}",
            )
    elif manifest_path is not None:
        raise VerificationError(E_PDF_VALIDATE, f"Manifest missing for verify: {manifest_path}")

    return {"status": "PASS", "checks": checks}
