from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mp4_to_pdf_lib.assemble import assemble_manifest_to_pdf
from mp4_to_pdf_lib.errors import error_message
from mp4_to_pdf_lib.errors import map_error_code
from mp4_to_pdf_lib.extract import extract_frames_with_manifest
from mp4_to_pdf_lib.options_parser import parse_options_path
from mp4_to_pdf_lib.preflight import run_preflight
from mp4_to_pdf_lib.quality import ffmpeg_args_for_profile
from mp4_to_pdf_lib.schema import E_CONFIG_BAD_INPUT_FORMAT
from mp4_to_pdf_lib.schema import SchemaError
from mp4_to_pdf_lib.selection import default_report_path
from mp4_to_pdf_lib.selection import ffmpeg_preselection_args
from mp4_to_pdf_lib.selection import select_frame_indices
from mp4_to_pdf_lib.verify import verify_pdf_output


E_JOB_INVALID = "E_JOB_INVALID"
_REPO_ROOT_RELATIVE_PREFIXES = ("fixtures", "jobs")


@dataclass(frozen=True)
class JobInvalidError(Exception):
    code: str
    job_name: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}:{self.job_name}: {self.message}"


@dataclass(frozen=True)
class VideoMetadata:
    source_fps: str
    duration_seconds: str | None


def _find_options_file(job_dir: Path, job_name: str) -> Path:
    txt_file = job_dir / "options.txt"
    md_file = job_dir / "options.md"
    txt_exists = txt_file.exists()
    md_exists = md_file.exists()
    if txt_exists and md_exists:
        raise JobInvalidError(E_JOB_INVALID, job_name, "Found both options.txt and options.md")
    if txt_exists:
        return txt_file
    if md_exists:
        return md_file
    raise JobInvalidError(E_JOB_INVALID, job_name, "Missing options.(txt|md)")


def _resolve_input_mp4(job_dir: Path, input_value: str) -> Path:
    return _resolve_job_or_repo_relative_path(job_dir, input_value)


def _resolve_output_pdf(job_dir: Path, output_value: str) -> Path:
    return _resolve_job_or_repo_relative_path(job_dir, output_value)


def _resolve_job_or_repo_relative_path(job_dir: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    if candidate.parts and candidate.parts[0] in _REPO_ROOT_RELATIVE_PREFIXES:
        repo_root = Path(__file__).resolve().parents[2]
        return repo_root / candidate
    return job_dir / candidate


def _probe_video_metadata(input_mp4: Path) -> VideoMetadata:
    ffprobe_bin = shutil.which("ffprobe")
    if ffprobe_bin is None:
        return VideoMetadata(source_fps="1", duration_seconds=None)

    command = [
        ffprobe_bin,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=avg_frame_rate:format=duration",
        "-of",
        "json",
        str(input_mp4),
    ]
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return VideoMetadata(source_fps="1", duration_seconds=None)

    try:
        payload = json.loads(completed.stdout)
    except Exception:
        return VideoMetadata(source_fps="1", duration_seconds=None)

    streams = payload.get("streams") or []
    stream = streams[0] if streams else {}
    source_fps = str(stream.get("avg_frame_rate", "1")).strip() or "1"
    if source_fps in {"0/0", "0"}:
        source_fps = "1"

    format_payload = payload.get("format") or {}
    duration_value = format_payload.get("duration")
    duration_seconds = str(duration_value).strip() if duration_value is not None else None
    if duration_seconds == "":
        duration_seconds = None
    return VideoMetadata(source_fps=source_fps, duration_seconds=duration_seconds)


def _write_selected_manifest(workspace_dir: Path, selected_frames: tuple[Path, ...]) -> Path:
    manifest_path = workspace_dir / "manifest.selected.txt"
    lines = [str(frame_path.relative_to(workspace_dir)) for frame_path in selected_frames]
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest_path


def _selected_manifest_from_report(report_path: Path) -> Path | None:
    if not report_path.exists():
        return None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    assemble_payload = payload.get("assemble") if isinstance(payload, dict) else None
    if not isinstance(assemble_payload, dict):
        return None
    selected_manifest = assemble_payload.get("selected_manifest_path")
    if not isinstance(selected_manifest, str) or not selected_manifest.strip():
        return None
    return Path(selected_manifest)


def _job_failure_payload(job_name: str, job_dir: Path, error: Exception, preflight_exit: int) -> dict[str, Any]:
    mapped_error_code = map_error_code(error)
    mapped_error_message = error_message(error)
    if isinstance(error, JobInvalidError):
        mapped_error_message = f"{error.job_name}: {error.message}"

    return {
        "job_name": job_name,
        "job_dir": str(job_dir),
        "status": "FAIL",
        "error_code": mapped_error_code,
        "error_message": mapped_error_message,
        "preflight": {"exit_code": preflight_exit, "status": "PASS" if preflight_exit == 0 else "FAIL"},
    }


def verify_existing_job_output(job_dir: Path) -> dict[str, Any]:
    job_name = job_dir.name
    options_path = _find_options_file(job_dir, job_name)
    try:
        config = parse_options_path(options_path)
    except SchemaError as error:
        raise JobInvalidError(E_JOB_INVALID, job_name, str(error)) from error

    output_pdf = _resolve_output_pdf(job_dir, str(config["output_pdf"]))
    selected_manifest = job_dir / ".mp4_to_pdf_tmp" / "manifest.selected.txt"
    if not selected_manifest.exists():
        selected_manifest = _selected_manifest_from_report(default_report_path(str(output_pdf))) or selected_manifest

    verify_payload = verify_pdf_output(
        output_pdf,
        manifest_path=selected_manifest,
    )
    return {
        "job_name": job_name,
        "job_dir": str(job_dir),
        "output_pdf": str(output_pdf),
        "manifest_path": str(selected_manifest),
        "verify": verify_payload,
    }


def run_orchestrated_job(
    job_dir: Path,
    *,
    keep_temp: bool = False,
    temp_dir: Path | None = None,
    pdf_nodate: bool = False,
    preflight_exit: int | None = None,
) -> dict[str, Any]:
    total_started_at = time.perf_counter()
    job_name = job_dir.name
    effective_preflight_exit = run_preflight(strict=False) if preflight_exit is None else preflight_exit

    options_path = _find_options_file(job_dir, job_name)
    try:
        config = parse_options_path(options_path)
        quality_profile = str(config["quality_profile"]).strip()
        ffmpeg_args = ffmpeg_args_for_profile(quality_profile)
    except SchemaError as error:
        raise JobInvalidError(E_JOB_INVALID, job_name, str(error)) from error

    input_mp4 = _resolve_input_mp4(job_dir, str(config["input_mp4"]))
    if input_mp4.suffix.lower() != ".mp4":
        raise JobInvalidError(E_CONFIG_BAD_INPUT_FORMAT, job_name, f"input_mp4 must use .mp4 extension: {input_mp4}")
    if not input_mp4.exists():
        raise JobInvalidError(E_JOB_INVALID, job_name, f"input_mp4 not found: {input_mp4}")
    output_pdf = _resolve_output_pdf(job_dir, str(config["output_pdf"]))
    output_pdf_tmp = Path(f"{output_pdf}.tmp")
    if output_pdf_tmp.exists():
        output_pdf_tmp.unlink()
    workspace_dir = temp_dir if temp_dir else (job_dir / ".mp4_to_pdf_tmp")

    try:
        video_metadata = _probe_video_metadata(input_mp4)
        preselection_args = ffmpeg_preselection_args(config, source_fps=video_metadata.source_fps)
        optimized_preselection = bool(preselection_args)
        effective_ffmpeg_args = (*preselection_args, *ffmpeg_args)

        extract_started_at = time.perf_counter()
        extraction_result = extract_frames_with_manifest(
            input_mp4=input_mp4,
            workspace_dir=workspace_dir,
            keep_temp=keep_temp,
            ffmpeg_args=effective_ffmpeg_args,
        )
        extract_ms = round((time.perf_counter() - extract_started_at) * 1000, 3)

        if optimized_preselection:
            selection_result = select_frame_indices(
                {
                    "mode": "every_frame",
                    "selector_every_frame": "true",
                },
                frame_count=len(extraction_result.frame_paths),
                source_fps=str(config["selector_fps"]),
                duration_seconds=video_metadata.duration_seconds,
            )
        else:
            selection_result = select_frame_indices(
                config,
                frame_count=len(extraction_result.frame_paths),
                source_fps=video_metadata.source_fps,
                duration_seconds=video_metadata.duration_seconds,
            )
        selected_frames = tuple(extraction_result.frame_paths[index] for index in selection_result.selected_indices)
        selected_manifest = _write_selected_manifest(extraction_result.workspace_dir, selected_frames)

        assemble_started_at = time.perf_counter()
        assembled_pages = assemble_manifest_to_pdf(selected_manifest, output_pdf_tmp, pdf_nodate=pdf_nodate)
        assemble_ms = round((time.perf_counter() - assemble_started_at) * 1000, 3)
        verify_payload = verify_pdf_output(output_pdf_tmp, expected_pages=assembled_pages, manifest_path=selected_manifest)
        output_pdf_tmp.replace(output_pdf)
    except Exception:
        output_pdf_tmp.unlink(missing_ok=True)
        raise

    report_path = default_report_path(str(output_pdf))
    summary = {
        "job_name": job_name,
        "job_dir": str(job_dir),
        "status": "PASS" if verify_payload["status"] == "PASS" else "FAIL",
        "preflight": {
            "exit_code": effective_preflight_exit,
            "status": "PASS" if effective_preflight_exit == 0 else "FAIL",
        },
        "options_path": str(options_path),
        "input_mp4": str(input_mp4),
        "output_pdf": str(output_pdf),
        "quality_profile": quality_profile,
        "selection": {
            "mode": selection_result.mode,
            "frame_count": selection_result.frame_count,
            "selected_count": len(selection_result.selected_indices),
            "selected_indices": selection_result.selected_indices,
            "source_fps": selection_result.source_fps,
            "duration_seconds": selection_result.duration_seconds,
        },
        "extract": {
            "workspace_dir": str(extraction_result.workspace_dir),
            "manifest_path": str(extraction_result.manifest_path),
            "frames_extracted": len(extraction_result.frame_paths),
            "ffmpeg_preselection_args": list(preselection_args),
            "optimized_preselection": optimized_preselection,
        },
        "assemble": {
            "selected_manifest_path": str(selected_manifest),
            "pages_written": assembled_pages,
            "pdf_nodate": pdf_nodate,
            "output_pdf_tmp": str(output_pdf_tmp),
            "atomic_rename": f"{output_pdf_tmp} -> {output_pdf}",
        },
        "timing": {
            "extract_ms": extract_ms,
            "assemble_ms": assemble_ms,
            "total_ms": round((time.perf_counter() - total_started_at) * 1000, 3),
        },
        "verify": verify_payload,
        "report_path": str(report_path),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def run_batch_jobs(
    jobs_root: Path,
    *,
    strict_batch: bool,
    keep_temp: bool = False,
    pdf_nodate: bool = False,
) -> tuple[dict[str, Any], JobInvalidError | None]:
    if not jobs_root.exists() or not jobs_root.is_dir():
        raise JobInvalidError(E_JOB_INVALID, jobs_root.name, f"jobs root is not a directory: {jobs_root}")

    preflight_exit = run_preflight(strict=False)
    job_dirs = sorted(path for path in jobs_root.iterdir() if path.is_dir())
    results: list[dict[str, Any]] = []
    halted_error: JobInvalidError | None = None

    for job_dir in job_dirs:
        try:
            summary = run_orchestrated_job(
                job_dir,
                keep_temp=keep_temp,
                pdf_nodate=pdf_nodate,
                preflight_exit=preflight_exit,
            )
            results.append(summary)
        except Exception as error:
            failure_payload = _job_failure_payload(job_dir.name, job_dir, error, preflight_exit)
            results.append(failure_payload)
            if strict_batch and isinstance(error, JobInvalidError):
                halted_error = error
                break

    passed_jobs = sum(1 for item in results if item["status"] == "PASS")
    failed_jobs = sum(1 for item in results if item["status"] == "FAIL")
    summary_payload = {
        "jobs_root": str(jobs_root),
        "strict_batch": strict_batch,
        "preflight": {"exit_code": preflight_exit, "status": "PASS" if preflight_exit == 0 else "FAIL"},
        "total_jobs": len(job_dirs),
        "processed_jobs": len(results),
        "passed_jobs": passed_jobs,
        "failed_jobs": failed_jobs,
        "halted": halted_error is not None,
        "halted_job": halted_error.job_name if halted_error is not None else None,
        "jobs": results,
    }
    summary_path = jobs_root / "batch_run_summary.json"
    summary_path.write_text(json.dumps(summary_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_payload["batch_report_path"] = str(summary_path)
    return summary_payload, halted_error
