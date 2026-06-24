from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path

from mp4_to_pdf_lib.schema import MODE_TO_SELECTOR_KEY
from mp4_to_pdf_lib.schema import QUALITY_PROFILES


SUPPORTED_MODES = tuple(MODE_TO_SELECTOR_KEY.keys())
SUPPORTED_PROFILES = tuple(QUALITY_PROFILES)
MODE_SELECTOR_VALUES = {
    "every_frame": "selector_every_frame: true",
    "fps": "selector_fps: 2",
    "every_nth": "selector_every_nth: 2",
    "keyframes": "selector_keyframes: 0,2,4",
    "time_range": "selector_time_range: 1-4",
}


@dataclass(frozen=True)
class MatrixCaseResult:
    mode: str
    quality_profile: str
    status: str
    run1_exit: int
    run2_exit: int
    report_mode: str | None
    report_quality_profile: str | None
    hash_first: str | None
    hash_second: str | None
    hash_equal: bool
    detail: str


@dataclass(frozen=True)
class FailureCaseResult:
    name: str
    expected_error_code: str
    actual_error_code: str | None
    exit_code: int
    status: str
    detail: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_cli(cli_path: Path, args: list[str], env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(cli_path), *args]
    return subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )


def _extract_error_code(output: str) -> str | None:
    match = re.search(r"\b(E_[A-Z0-9_]+)\b", output)
    return match.group(1) if match else None


def _matrix_env(repo_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    fake_bin = repo_root / ".sisyphus" / "evidence" / "fake_bin"
    fake_ffmpeg_ok = repo_root / ".sisyphus" / "evidence" / "fake_ffmpeg_ok.py"

    if fake_bin.exists():
        current_path = env.get("PATH", "")
        env["PATH"] = f"{fake_bin}{os.pathsep}{current_path}" if current_path else str(fake_bin)
    if fake_ffmpeg_ok.exists():
        env["MP4_TO_PDF_FFMPEG_BIN"] = str(fake_ffmpeg_ok)
    return env


def _write_options(job_dir: Path, mode: str, quality_profile: str) -> Path:
    selector_line = MODE_SELECTOR_VALUES.get(mode)
    if selector_line is None:
        raise ValueError(f"No selector fixture value configured for mode '{mode}'")

    options_path = job_dir / "options.txt"
    options_body = "\n".join(
        [
            f"mode: {mode}",
            f"quality_profile: {quality_profile}",
            "input_mp4: input.mp4",
            "output_pdf: output.pdf",
            selector_line,
            "",
        ]
    )
    options_path.write_text(options_body, encoding="utf-8")
    return options_path


def _read_run_report(report_path: Path) -> tuple[str | None, str | None]:
    if not report_path.exists():
        return None, None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return None, None

    report_mode = None
    report_quality_profile = None
    if isinstance(payload, dict):
        selection_payload = payload.get("selection")
        if isinstance(selection_payload, dict):
            mode_value = selection_payload.get("mode")
            if isinstance(mode_value, str):
                report_mode = mode_value
        quality_value = payload.get("quality_profile")
        if isinstance(quality_value, str):
            report_quality_profile = quality_value

    return report_mode, report_quality_profile


def _run_matrix_case(
    *,
    repo_root: Path,
    cli_path: Path,
    fixtures_dir: Path,
    env: dict[str, str],
    jobs_root: Path,
    mode: str,
    quality_profile: str,
) -> MatrixCaseResult:
    input_fixture = fixtures_dir / "cfr10_3s.mp4"
    if not input_fixture.exists():
        return MatrixCaseResult(
            mode=mode,
            quality_profile=quality_profile,
            status="FAIL",
            run1_exit=1,
            run2_exit=1,
            report_mode=None,
            report_quality_profile=None,
            hash_first=None,
            hash_second=None,
            hash_equal=False,
            detail=f"missing fixture input: {input_fixture}",
        )

    job_dir = jobs_root / f"job_{mode}__{quality_profile}"
    job_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(input_fixture, job_dir / "input.mp4")
    _write_options(job_dir, mode, quality_profile)

    run1 = _run_cli(cli_path, ["--job-dir", str(job_dir), "--pdf-nodate"], env, repo_root)
    output_pdf = job_dir / "output.pdf"
    report_path = output_pdf.with_suffix(output_pdf.suffix + ".run_report.json")
    report_mode, report_quality_profile = _read_run_report(report_path)

    if run1.returncode != 0:
        return MatrixCaseResult(
            mode=mode,
            quality_profile=quality_profile,
            status="FAIL",
            run1_exit=run1.returncode,
            run2_exit=1,
            report_mode=report_mode,
            report_quality_profile=report_quality_profile,
            hash_first=None,
            hash_second=None,
            hash_equal=False,
            detail=f"run1 failed: {run1.stdout.strip() or '<no output>'}",
        )
    if not output_pdf.exists():
        return MatrixCaseResult(
            mode=mode,
            quality_profile=quality_profile,
            status="FAIL",
            run1_exit=run1.returncode,
            run2_exit=1,
            report_mode=report_mode,
            report_quality_profile=report_quality_profile,
            hash_first=None,
            hash_second=None,
            hash_equal=False,
            detail=f"run1 missing output PDF: {output_pdf}",
        )

    hash_first = _sha256(output_pdf)
    run2 = _run_cli(cli_path, ["--job-dir", str(job_dir), "--pdf-nodate"], env, repo_root)
    report_mode, report_quality_profile = _read_run_report(report_path)

    if run2.returncode != 0:
        return MatrixCaseResult(
            mode=mode,
            quality_profile=quality_profile,
            status="FAIL",
            run1_exit=run1.returncode,
            run2_exit=run2.returncode,
            report_mode=report_mode,
            report_quality_profile=report_quality_profile,
            hash_first=hash_first,
            hash_second=None,
            hash_equal=False,
            detail=f"run2 failed: {run2.stdout.strip() or '<no output>'}",
        )
    if not output_pdf.exists():
        return MatrixCaseResult(
            mode=mode,
            quality_profile=quality_profile,
            status="FAIL",
            run1_exit=run1.returncode,
            run2_exit=run2.returncode,
            report_mode=report_mode,
            report_quality_profile=report_quality_profile,
            hash_first=hash_first,
            hash_second=None,
            hash_equal=False,
            detail=f"run2 missing output PDF: {output_pdf}",
        )

    hash_second = _sha256(output_pdf)
    hash_equal = hash_first == hash_second
    mode_ok = report_mode == mode
    profile_ok = report_quality_profile == quality_profile

    status = "PASS" if hash_equal and mode_ok and profile_ok else "FAIL"
    detail_parts = []
    if not hash_equal:
        detail_parts.append("hash mismatch across deterministic reruns")
    if not mode_ok:
        detail_parts.append(f"report mode mismatch: expected={mode} actual={report_mode}")
    if not profile_ok:
        detail_parts.append(
            f"report quality profile mismatch: expected={quality_profile} actual={report_quality_profile}"
        )
    detail = "; ".join(detail_parts) if detail_parts else "ok"

    return MatrixCaseResult(
        mode=mode,
        quality_profile=quality_profile,
        status=status,
        run1_exit=run1.returncode,
        run2_exit=run2.returncode,
        report_mode=report_mode,
        report_quality_profile=report_quality_profile,
        hash_first=hash_first,
        hash_second=hash_second,
        hash_equal=hash_equal,
        detail=detail,
    )


def _run_failure_cases(repo_root: Path, cli_path: Path, fixtures_dir: Path, env: dict[str, str]) -> list[FailureCaseResult]:
    failure_cases: list[FailureCaseResult] = []
    conflict_fixture = fixtures_dir / "job_conflict_selectors" / "options.txt"

    run = _run_cli(cli_path, ["--parse-options", str(conflict_fixture)], env, repo_root)
    actual_code = _extract_error_code(run.stdout)
    expected_code = "E_CONFIG_MODE_CONFLICT"
    status = "PASS" if run.returncode != 0 and actual_code == expected_code else "FAIL"
    detail = "ok" if status == "PASS" else f"output={run.stdout.strip() or '<no output>'}"

    failure_cases.append(
        FailureCaseResult(
            name="selector_conflict_fixture",
            expected_error_code=expected_code,
            actual_error_code=actual_code,
            exit_code=run.returncode,
            status=status,
            detail=detail,
        )
    )
    return failure_cases


def _print_results(matrix_results: list[MatrixCaseResult], failure_results: list[FailureCaseResult], strict: bool) -> int:
    matrix_total = len(matrix_results)
    matrix_passed = sum(1 for item in matrix_results if item.status == "PASS")
    matrix_failed = matrix_total - matrix_passed
    reproducibility_total = matrix_total
    reproducibility_passed = sum(1 for item in matrix_results if item.hash_equal)

    failure_total = len(failure_results)
    failure_passed = sum(1 for item in failure_results if item.status == "PASS")
    failure_failed = failure_total - failure_passed

    overall_pass = matrix_failed == 0 and failure_failed == 0

    print("INTEGRATION_MATRIX: START")
    for item in matrix_results:
        print(
            "MATRIX_CASE: "
            f"mode={item.mode} "
            f"quality_profile={item.quality_profile} "
            f"status={item.status} "
            f"hash_equal={item.hash_equal} "
            f"run1_exit={item.run1_exit} "
            f"run2_exit={item.run2_exit}"
        )

    for item in failure_results:
        print(
            "FAILURE_CASE: "
            f"name={item.name} "
            f"status={item.status} "
            f"expected_error_code={item.expected_error_code} "
            f"actual_error_code={item.actual_error_code} "
            f"exit_code={item.exit_code}"
        )

    summary = {
        "status": "PASS" if overall_pass else "FAIL",
        "strict": strict,
        "supported_modes": list(SUPPORTED_MODES),
        "supported_quality_profiles": list(SUPPORTED_PROFILES),
        "matrix_total": matrix_total,
        "matrix_passed": matrix_passed,
        "matrix_failed": matrix_failed,
        "reproducibility_total": reproducibility_total,
        "reproducibility_passed": reproducibility_passed,
        "failure_total": failure_total,
        "failure_passed": failure_passed,
        "failure_failed": failure_failed,
        "matrix_results": [asdict(item) for item in matrix_results],
        "failure_results": [asdict(item) for item in failure_results],
    }

    print("SUMMARY_JSON_START")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("SUMMARY_JSON_END")
    print(f"INTEGRATION_MATRIX: {'PASS' if overall_pass else 'FAIL'}")

    if not overall_pass and strict:
        return 1
    return 0


def _validate_mode_fixture_map() -> None:
    missing_modes = [mode for mode in SUPPORTED_MODES if mode not in MODE_SELECTOR_VALUES]
    extra_modes = [mode for mode in MODE_SELECTOR_VALUES if mode not in SUPPORTED_MODES]
    if missing_modes or extra_modes:
        parts = []
        if missing_modes:
            parts.append(f"missing selector fixture values for modes: {', '.join(missing_modes)}")
        if extra_modes:
            parts.append(f"unknown selector fixture modes configured: {', '.join(extra_modes)}")
        raise ValueError("; ".join(parts))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run_integration_matrix.py")
    parser.add_argument("--fixtures", default="fixtures")
    parser.add_argument("--strict", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _validate_mode_fixture_map()

    repo_root = _repo_root()
    fixtures_dir = Path(args.fixtures)
    if not fixtures_dir.is_absolute():
        fixtures_dir = (repo_root / fixtures_dir).resolve()

    cli_path = repo_root / "tools" / "mp4_to_pdf.py"
    env = _matrix_env(repo_root)

    matrix_results: list[MatrixCaseResult] = []
    with tempfile.TemporaryDirectory(prefix="integration_matrix_", dir=str(repo_root / ".sisyphus" / "evidence")) as temp_dir:
        jobs_root = Path(temp_dir)
        for mode in SUPPORTED_MODES:
            for quality_profile in SUPPORTED_PROFILES:
                matrix_results.append(
                    _run_matrix_case(
                        repo_root=repo_root,
                        cli_path=cli_path,
                        fixtures_dir=fixtures_dir,
                        env=env,
                        jobs_root=jobs_root,
                        mode=mode,
                        quality_profile=quality_profile,
                    )
                )

        failure_results = _run_failure_cases(repo_root, cli_path, fixtures_dir, env)
    return _print_results(matrix_results, failure_results, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
