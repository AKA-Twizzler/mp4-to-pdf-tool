from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any

from mp4_to_pdf_lib.orchestrator import run_orchestrated_job
from mp4_to_pdf_lib.schema import E_CONFIG_INVALID_BENCHMARK_RUNS
from mp4_to_pdf_lib.schema import SchemaError


def _validate_benchmark_runs(runs: int) -> None:
    if runs <= 0:
        raise SchemaError(
            E_CONFIG_INVALID_BENCHMARK_RUNS,
            f"--benchmark-runs must be >= 1 (received {runs})",
        )


def run_benchmark_job(
    job_dir: Path,
    *,
    runs: int,
    keep_temp: bool = False,
    temp_dir: Path | None = None,
    pdf_nodate: bool = False,
    report_path: Path | None = None,
) -> dict[str, Any]:
    _validate_benchmark_runs(runs)

    run_payloads: list[dict[str, Any]] = []
    latest_summary: dict[str, Any] | None = None
    total_ms_values: list[float] = []

    for run_index in range(1, runs + 1):
        started_at = time.perf_counter()
        summary = run_orchestrated_job(
            job_dir,
            keep_temp=keep_temp,
            temp_dir=temp_dir,
            pdf_nodate=pdf_nodate,
        )
        latest_summary = summary

        timed_total_ms = round((time.perf_counter() - started_at) * 1000, 3)
        timing_payload = summary.get("timing", {})
        output_pdf = Path(str(summary["output_pdf"]))
        run_payload = {
            "run": run_index,
            "extract_ms": float(timing_payload.get("extract_ms", 0.0)),
            "assemble_ms": float(timing_payload.get("assemble_ms", 0.0)),
            "total_ms": timed_total_ms,
            "frames_selected": int(summary["selection"]["selected_count"]),
            "pdf_bytes": output_pdf.stat().st_size,
            "mode": str(summary["selection"]["mode"]),
            "quality_profile": str(summary["quality_profile"]),
        }
        run_payloads.append(run_payload)
        total_ms_values.append(timed_total_ms)

    assert latest_summary is not None
    baseline = run_payloads[-1]

    output_pdf_path = Path(str(latest_summary["output_pdf"]))
    resolved_report_path = (
        report_path
        if report_path is not None
        else output_pdf_path.with_suffix(output_pdf_path.suffix + ".benchmark_report.json")
    )
    resolved_report_path.parent.mkdir(parents=True, exist_ok=True)

    benchmark_payload: dict[str, Any] = {
        "job_name": str(latest_summary["job_name"]),
        "job_dir": str(job_dir),
        "benchmark_runs": runs,
        "extract_ms": baseline["extract_ms"],
        "assemble_ms": baseline["assemble_ms"],
        "total_ms": baseline["total_ms"],
        "frames_selected": baseline["frames_selected"],
        "pdf_bytes": baseline["pdf_bytes"],
        "mode": baseline["mode"],
        "quality_profile": baseline["quality_profile"],
        "runs": run_payloads,
        "report_path": str(resolved_report_path),
    }
    if runs > 1:
        benchmark_payload["median_total_ms"] = round(statistics.median(total_ms_values), 3)

    resolved_report_path.write_text(json.dumps(benchmark_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return benchmark_payload
