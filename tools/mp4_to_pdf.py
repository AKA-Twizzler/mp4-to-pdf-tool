from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mp4_to_pdf_lib.benchmark import run_benchmark_job
from mp4_to_pdf_lib.errors import error_map_payload
from mp4_to_pdf_lib.errors import format_mapped_error
from mp4_to_pdf_lib.options_parser import parse_options_path
from mp4_to_pdf_lib.orchestrator import run_batch_jobs
from mp4_to_pdf_lib.orchestrator import run_orchestrated_job
from mp4_to_pdf_lib.orchestrator import verify_existing_job_output
from mp4_to_pdf_lib.preflight import run_preflight
from mp4_to_pdf_lib.quality import profile_map_payload
from mp4_to_pdf_lib.schema import E_CONFIG_MODE_CONFLICT
from mp4_to_pdf_lib.schema import E_CONFIG_MISSING_REQUIRED
from mp4_to_pdf_lib.schema import E_CONFIG_UNKNOWN_KEY
from mp4_to_pdf_lib.schema import SchemaError
from mp4_to_pdf_lib.schema import schema_lint
from mp4_to_pdf_lib.schema import schema_payload
from mp4_to_pdf_lib.selection import select_frame_indices


def run_schema_lint() -> int:
    errors = list(schema_lint())
    if errors:
        print("SCHEMA_LINT: FAIL")
        for item in errors:
            print(f"- {item}")
        return 1
    print("SCHEMA_LINT: PASS")
    return 0


def run_job_dir(
    job_dir: Path,
    keep_temp: bool = False,
    temp_dir: Path | None = None,
    pdf_nodate: bool = False,
    benchmark_runs: int | None = None,
    report_json: Path | None = None,
) -> int:
    if benchmark_runs is not None:
        summary = run_benchmark_job(
            job_dir,
            runs=benchmark_runs,
            keep_temp=keep_temp,
            temp_dir=temp_dir,
            pdf_nodate=pdf_nodate,
            report_path=report_json,
        )
        print(f"JOB_OK: {summary['job_name']}")
        print(f"BENCHMARK_REPORT: {summary['report_path']}")
        return 0

    summary = run_orchestrated_job(
        job_dir,
        keep_temp=keep_temp,
        temp_dir=temp_dir,
        pdf_nodate=pdf_nodate,
    )
    print(f"JOB_OK: {summary['job_name']}")
    print(f"OUTPUT_PDF: {summary['output_pdf']}")
    print(f"RUN_SUMMARY: {summary['report_path']}")
    return 0


def run_verify_job_dir(job_dir: Path) -> int:
    summary = verify_existing_job_output(job_dir)
    print(f"VERIFY_OK: {summary['job_name']}")
    print(f"OUTPUT_PDF: {summary['output_pdf']}")
    if summary["manifest_path"]:
        print(f"MANIFEST_PATH: {summary['manifest_path']}")
    print(json.dumps(summary["verify"], indent=2, sort_keys=True))
    return 0


def run_jobs_root_batch(
    jobs_root: Path,
    *,
    strict_batch: bool,
    keep_temp: bool,
    pdf_nodate: bool,
) -> int:
    batch_summary, halted_error = run_batch_jobs(
        jobs_root,
        strict_batch=strict_batch,
        keep_temp=keep_temp,
        pdf_nodate=pdf_nodate,
    )
    print(json.dumps(batch_summary, indent=2, sort_keys=True))
    if halted_error is not None:
        raise halted_error
    if strict_batch and batch_summary["failed_jobs"] > 0:
        return 1
    return 0


def run_parse_options(options_path: Path, print_config_json: bool) -> int:
    config = parse_options_path(options_path)
    if print_config_json:
        print(json.dumps(config, indent=2, sort_keys=True))
    else:
        print(f"CONFIG_OK: {options_path}")
    return 0


def run_selection_dry_run(
    options_path: Path,
    *,
    frame_count: int | None,
    source_fps: str | None,
    duration_seconds: str | None,
    keyframe_indices: str | None,
    report_path: Path | None,
) -> int:
    if frame_count is None:
        raise SchemaError(E_CONFIG_MISSING_REQUIRED, "--selection-frame-count is required with --selection-dry-run")
    if source_fps is None:
        raise SchemaError(E_CONFIG_MISSING_REQUIRED, "--selection-source-fps is required with --selection-dry-run")

    config = parse_options_path(options_path)
    result = select_frame_indices(
        config,
        frame_count=frame_count,
        source_fps=source_fps,
        duration_seconds=duration_seconds,
        keyframe_indices_override=keyframe_indices,
    )

    output_path = Path(str(config["output_pdf"]))
    resolved_report_path = report_path if report_path is not None else output_path.with_suffix(output_path.suffix + ".run_report.json")
    resolved_report_path.parent.mkdir(parents=True, exist_ok=True)

    report_payload = {
        "selection": {
            "mode": result.mode,
            "frame_count": result.frame_count,
            "selected_count": len(result.selected_indices),
            "selected_indices": result.selected_indices,
            "source_fps": result.source_fps,
            "duration_seconds": result.duration_seconds,
        }
    }
    resolved_report_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        "SELECTION_OK: "
        f"mode={result.mode} selected_count={len(result.selected_indices)} "
        f"report_path={resolved_report_path}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mp4_to_pdf.py")
    parser.add_argument("--print-schema", action="store_true")
    parser.add_argument("--print-error-map", action="store_true")
    parser.add_argument("--print-profile-map", action="store_true")
    parser.add_argument("--schema-lint", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--quality-profile")
    parser.add_argument("--job-dir")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--jobs-root")
    parser.add_argument("--batch", action="store_true")
    parser.add_argument("--temp-dir")
    parser.add_argument("--keep-temp", action="store_true")
    parser.add_argument("--parse-options")
    parser.add_argument("--print-config-json", action="store_true")
    parser.add_argument("--selection-dry-run", action="store_true")
    parser.add_argument("--selection-frame-count", type=int)
    parser.add_argument("--selection-source-fps")
    parser.add_argument("--selection-duration-seconds")
    parser.add_argument("--selection-keyframe-indices")
    parser.add_argument("--selection-report-path")
    parser.add_argument("--pdf-nodate", action="store_true")
    parser.add_argument("--benchmark-runs", type=int)
    parser.add_argument("--report-json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.job_dir and args.parse_options:
        raise SchemaError(
            E_CONFIG_MODE_CONFLICT,
            "--job-dir uses folder options authority; do not combine with --parse-options",
        )
    if args.job_dir and args.jobs_root:
        raise SchemaError(E_CONFIG_MODE_CONFLICT, "Use exactly one of --job-dir or --jobs-root")
    if args.batch and not args.jobs_root:
        raise SchemaError(E_CONFIG_UNKNOWN_KEY, "--batch requires --jobs-root <dir>")
    if args.jobs_root and not args.batch:
        raise SchemaError(E_CONFIG_UNKNOWN_KEY, "--jobs-root requires --batch")
    if args.verify and not args.job_dir:
        raise SchemaError(E_CONFIG_UNKNOWN_KEY, "--verify requires --job-dir <dir>")
    if args.verify and args.jobs_root:
        raise SchemaError(E_CONFIG_MODE_CONFLICT, "Use --verify only with --job-dir")
    if args.print_config_json and not args.parse_options:
        raise SchemaError(
            E_CONFIG_UNKNOWN_KEY,
            "--print-config-json requires --parse-options <path>",
        )
    if args.selection_dry_run and not args.parse_options:
        raise SchemaError(
            E_CONFIG_UNKNOWN_KEY,
            "--selection-dry-run requires --parse-options <path>",
        )
    if args.benchmark_runs is not None and not args.job_dir:
        raise SchemaError(E_CONFIG_UNKNOWN_KEY, "--benchmark-runs requires --job-dir <dir>")
    if args.report_json and args.benchmark_runs is None:
        raise SchemaError(E_CONFIG_UNKNOWN_KEY, "--report-json requires --benchmark-runs <n>")

    should_run_something = False
    exit_code = 0

    if args.print_schema:
        should_run_something = True
        print(json.dumps(schema_payload(), indent=2, sort_keys=True))

    if args.print_error_map:
        should_run_something = True
        print(json.dumps(error_map_payload(), indent=2, sort_keys=True))

    if args.print_profile_map:
        should_run_something = True
        print(json.dumps(profile_map_payload(args.quality_profile), indent=2, sort_keys=True))

    if args.schema_lint:
        should_run_something = True
        lint_exit = run_schema_lint()
        exit_code = lint_exit if lint_exit != 0 else exit_code

    if args.preflight:
        should_run_something = True
        preflight_exit = run_preflight(strict=args.strict)
        exit_code = preflight_exit if preflight_exit != 0 else exit_code

    if args.job_dir:
        should_run_something = True
        if args.verify:
            job_exit = run_verify_job_dir(Path(args.job_dir))
        else:
            temp_dir = Path(args.temp_dir) if args.temp_dir else None
            job_exit = run_job_dir(
                Path(args.job_dir),
                keep_temp=args.keep_temp,
                temp_dir=temp_dir,
                pdf_nodate=args.pdf_nodate,
                benchmark_runs=args.benchmark_runs,
                report_json=Path(args.report_json) if args.report_json else None,
            )
        exit_code = job_exit if job_exit != 0 else exit_code

    if args.jobs_root and args.batch:
        should_run_something = True
        batch_exit = run_jobs_root_batch(
            Path(args.jobs_root),
            strict_batch=args.strict,
            keep_temp=args.keep_temp,
            pdf_nodate=args.pdf_nodate,
        )
        exit_code = batch_exit if batch_exit != 0 else exit_code

    if args.parse_options:
        should_run_something = True
        parse_exit = run_parse_options(Path(args.parse_options), print_config_json=args.print_config_json)
        exit_code = parse_exit if parse_exit != 0 else exit_code

    if args.selection_dry_run:
        should_run_something = True
        selection_exit = run_selection_dry_run(
            Path(args.parse_options),
            frame_count=args.selection_frame_count,
            source_fps=args.selection_source_fps,
            duration_seconds=args.selection_duration_seconds,
            keyframe_indices=args.selection_keyframe_indices,
            report_path=Path(args.selection_report_path) if args.selection_report_path else None,
        )
        exit_code = selection_exit if selection_exit != 0 else exit_code

    if not should_run_something:
        parser.print_help()
        return 2

    return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(format_mapped_error(error), file=sys.stderr)
        raise SystemExit(1)
