from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


E_EXTRACT_FAILED = "E_EXTRACT_FAILED"
E_EXTRACT_BINARY_MISSING = "E_EXTRACT_BINARY_MISSING"
E_NO_FRAMES_EXTRACTED = "E_NO_FRAMES_EXTRACTED"

FRAME_FILE_TEMPLATE = "frame_%08d.png"
FRAME_FILE_GLOB = "frame_*.png"
MANIFEST_FILENAME = "manifest.txt"


@dataclass(frozen=True)
class ExtractionError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class ExtractionResult:
    workspace_dir: Path
    frames_dir: Path
    manifest_path: Path
    frame_paths: tuple[Path, ...]


def _resolve_ffmpeg_bin() -> str:
    candidate = os.environ.get("MP4_TO_PDF_FFMPEG_BIN", "").strip()
    return candidate if candidate else "ffmpeg"


def _sorted_frames(frames_dir: Path) -> tuple[Path, ...]:
    return tuple(sorted((path for path in frames_dir.glob(FRAME_FILE_GLOB) if path.is_file()), key=lambda item: item.name))


def _write_manifest(manifest_path: Path, frame_paths: tuple[Path, ...], workspace_dir: Path) -> None:
    rel_lines = [str(path.relative_to(workspace_dir)) for path in frame_paths]
    manifest_path.write_text("\n".join(rel_lines) + "\n", encoding="utf-8")


def extract_frames_with_manifest(
    input_mp4: Path,
    workspace_dir: Path,
    keep_temp: bool = False,
    ffmpeg_args: tuple[str, ...] = (),
) -> ExtractionResult:
    frames_dir = workspace_dir / "frames"
    manifest_path = workspace_dir / MANIFEST_FILENAME
    ffmpeg_bin = _resolve_ffmpeg_bin()

    if workspace_dir.exists():
        shutil.rmtree(workspace_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)

    command = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_mp4),
        *ffmpeg_args,
        str(frames_dir / FRAME_FILE_TEMPLATE),
    ]

    try:
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        except FileNotFoundError as error:
            raise ExtractionError(E_EXTRACT_BINARY_MISSING, f"ffmpeg binary not found: {ffmpeg_bin}") from error
        if completed.returncode != 0:
            output = completed.stdout.strip() or "<no ffmpeg output>"
            raise ExtractionError(E_EXTRACT_FAILED, f"ffmpeg failed with exit={completed.returncode}: {output}")

        frame_paths = _sorted_frames(frames_dir)
        if not frame_paths:
            raise ExtractionError(E_NO_FRAMES_EXTRACTED, "No frames matched extraction pattern frame_%08d")

        _write_manifest(manifest_path, frame_paths, workspace_dir)
        return ExtractionResult(
            workspace_dir=workspace_dir,
            frames_dir=frames_dir,
            manifest_path=manifest_path,
            frame_paths=frame_paths,
        )
    except Exception:
        if not keep_temp:
            shutil.rmtree(workspace_dir, ignore_errors=True)
        raise
